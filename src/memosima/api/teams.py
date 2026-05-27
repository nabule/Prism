"""REST endpoints for the team knowledge base feature.

These routes are registered onto the main FastAPI app via
`register_team_routes(app)`. They share state with the rest of the sidecar:

* `app.state.store`   — SQLite-backed `Store`
* `app.state.config`  — `AppConfig` (used for `workspace_id` & vector search settings)
* `app.state.admin_token` — global admin bearer token

Routes are split into two groups:

1. **Admin-only** (`/admin/teams/...`) — protected by the global admin token,
   for creating teams, generating invites, listing members, etc.
2. **Member-scoped** (`/teams/{slug}/...`) — protected by team member tokens
   issued via invite redemption. Admin tokens are also accepted.

Vector search reuses `EmbeddingClient` from `memosima.llm.provider` (already
shared by the personal knowledge base) and gracefully falls back to substring
matching when the embedding key is absent or the vector index is empty.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from memosima.api.security import require_admin
from memosima.api.team_security import (
    TeamPrincipal,
    get_team_principal,
    require_team_role,
)
from memosima.db.store import (
    Store,
    TEAM_ROLES,
    TeamEntryRecord,
    TeamInviteRecord,
    TeamMemberRecord,
    TeamRecord,
)
from memosima.llm.provider import EmbeddingClient, LLMClientError

LOGGER = logging.getLogger("memosima.api.teams")

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")

TeamRole = Literal["owner", "editor", "viewer"]


# ----- Request / Response models -----


class TeamCreateRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    owner_display_name: str = Field(default="管理员", min_length=1, max_length=80)


class TeamUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class TeamView(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    member_count: int
    entry_count: int
    created_at: str
    updated_at: str


class TeamWithOwnerTokenView(BaseModel):
    team: TeamView
    owner_member_id: int
    owner_token: str


class TeamListResponse(BaseModel):
    teams: list[TeamView]


class TeamMemberView(BaseModel):
    id: int
    display_name: str
    role: TeamRole
    created_at: str
    updated_at: str
    last_active_at: str | None


class TeamMembersResponse(BaseModel):
    members: list[TeamMemberView]


class TeamMemberRoleUpdateRequest(BaseModel):
    role: TeamRole


class TeamInviteCreateRequest(BaseModel):
    role: TeamRole = "editor"
    max_uses: int = Field(default=0, ge=0, le=1000)
    expires_at: str | None = Field(default=None, max_length=40)


class TeamInviteView(BaseModel):
    id: int
    code: str
    role: TeamRole
    max_uses: int
    uses: int
    expires_at: str | None
    revoked_at: str | None
    created_at: str


class TeamInvitesResponse(BaseModel):
    invites: list[TeamInviteView]


class TeamJoinRequest(BaseModel):
    code: str = Field(min_length=4, max_length=80)
    display_name: str = Field(min_length=1, max_length=80)


class TeamJoinResponse(BaseModel):
    team: TeamView
    member: TeamMemberView
    token: str


class TeamEntryCreateRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    body: str = Field(min_length=1, max_length=50000)
    tags: list[str] = Field(default_factory=list, max_length=30)


class TeamEntryUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=50000)
    tags: list[str] | None = Field(default=None, max_length=30)


class TeamEntryView(BaseModel):
    uid: str
    title: str
    body: str
    tags: list[str]
    author_display_name: str | None
    created_at: str
    updated_at: str


class TeamEntriesResponse(BaseModel):
    entries: list[TeamEntryView]
    total: int


class TeamSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    tag: str | None = Field(default=None, max_length=80)
    top_k: int = Field(default=10, ge=1, le=50)
    use_vector: bool = True


class TeamSearchHit(BaseModel):
    entry: TeamEntryView
    score: float
    snippet: str


class TeamSearchResponse(BaseModel):
    hits: list[TeamSearchHit]
    retrieval_mode: str


class TeamPromptRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    system_prompt: str = Field(default="", max_length=4000)
    tag: str | None = Field(default=None, max_length=80)
    top_k: int = Field(default=10, ge=1, le=50)
    use_vector: bool = True


class TeamPromptResponse(BaseModel):
    assembled_prompt: str
    retrieved_count: int
    retrieval_mode: str
    sources: list[TeamEntryView]


# ----- Helpers -----


def _validate_slug(slug: str) -> str:
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Team slug must be 3-40 chars, lower-case letters, digits, or hyphen, "
                "and cannot start/end with a hyphen"
            ),
        )
    return slug


def _team_view(store: Store, team: TeamRecord) -> TeamView:
    members = store.list_team_members(team_id=team.id)
    entries = store.list_team_entries(team_id=team.id, limit=10000)
    return TeamView(
        id=team.id,
        slug=team.slug,
        name=team.name,
        description=team.description,
        member_count=len(members),
        entry_count=len(entries),
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


def _member_view(member: TeamMemberRecord) -> TeamMemberView:
    return TeamMemberView(
        id=member.id,
        display_name=member.display_name,
        role=member.role,  # type: ignore[arg-type]
        created_at=member.created_at,
        updated_at=member.updated_at,
        last_active_at=member.last_active_at,
    )


def _invite_view(invite: TeamInviteRecord) -> TeamInviteView:
    return TeamInviteView(
        id=invite.id,
        code=invite.code,
        role=invite.role,  # type: ignore[arg-type]
        max_uses=invite.max_uses,
        uses=invite.uses,
        expires_at=invite.expires_at,
        revoked_at=invite.revoked_at,
        created_at=invite.created_at,
    )


def _entry_view(entry: TeamEntryRecord) -> TeamEntryView:
    return TeamEntryView(
        uid=entry.uid,
        title=entry.title,
        body=entry.body,
        tags=list(entry.tags),
        author_display_name=entry.author_display_name,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _snippet(text: str, *, max_chars: int = 240) -> str:
    flat = " ".join(text.split())
    if len(flat) <= max_chars:
        return flat
    return flat[: max_chars - 1] + "…"


def _entry_text_for_embedding(entry: TeamEntryRecord) -> str:
    tag_str = " ".join(f"#{tag}" for tag in entry.tags)
    pieces = [entry.title.strip()]
    if tag_str:
        pieces.append(tag_str)
    if entry.body.strip():
        pieces.append(entry.body.strip())
    return "\n".join(piece for piece in pieces if piece)


def _build_embedding_client(request: Request) -> EmbeddingClient | None:
    cfg = request.app.state.config
    if not getattr(cfg, "vector_search_enabled", False):
        return None
    api_key = os.getenv(cfg.vector_search_api_key_env)
    if not api_key:
        return None
    return EmbeddingClient(
        base_url=cfg.vector_search_base_url,
        api_key=api_key,
        model=cfg.vector_search_model,
    )


async def _reindex_entry_vectors(
    request: Request,
    *,
    team_id: int,
    entry: TeamEntryRecord,
) -> None:
    """Best-effort: refresh the vector index for a single entry.

    Failures are logged and swallowed so a transient embedding outage never
    breaks the user-facing write path.
    """
    store: Store = request.app.state.store
    client = _build_embedding_client(request)
    if client is None:
        # No embedding key configured — silently clear any stale vectors.
        store.replace_team_entry_vectors(team_id=team_id, entry_uid=entry.uid, chunks=[])
        return
    text = _entry_text_for_embedding(entry)
    if not text:
        store.replace_team_entry_vectors(team_id=team_id, entry_uid=entry.uid, chunks=[])
        return
    try:
        embeddings = await client.get_embeddings([text])
    except LLMClientError as exc:
        LOGGER.warning("Team entry embedding failed for %s: %s", entry.uid, exc)
        return
    if not embeddings:
        return
    store.replace_team_entry_vectors(
        team_id=team_id, entry_uid=entry.uid, chunks=[(text, embeddings[0])],
    )


def _entry_matches_tag(entry: TeamEntryRecord, tag: str | None) -> bool:
    if not tag:
        return True
    needle = tag.lstrip("#").strip().lower()
    if not needle:
        return True
    return any(needle == t.lower() for t in entry.tags)


def _entry_matches_query(entry: TeamEntryRecord, query: str) -> bool:
    if not query:
        return True
    needle = query.lower()
    if needle in entry.title.lower() or needle in entry.body.lower():
        return True
    return any(needle in t.lower() for t in entry.tags)


# ----- Route registration -----


def register_team_routes(app: FastAPI) -> None:
    """Attach all team knowledge base routes onto the FastAPI app."""

    # ---------- Admin-only management ----------

    @app.post(
        "/admin/teams",
        response_model=TeamWithOwnerTokenView,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_admin)],
        tags=["teams"],
    )
    def create_team(request: Request, payload: TeamCreateRequest) -> TeamWithOwnerTokenView:
        store: Store = request.app.state.store
        workspace_id: str = request.app.state.config.workspace_id
        slug = _validate_slug(payload.slug.strip().lower())
        try:
            team = store.create_team(
                workspace_id=workspace_id,
                slug=slug,
                name=payload.name.strip(),
                description=payload.description,
            )
            member, raw_token = store.add_team_member(
                team_id=team.id,
                display_name=payload.owner_display_name.strip() or "管理员",
                role="owner",
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        return TeamWithOwnerTokenView(
            team=_team_view(store, team),
            owner_member_id=member.id,
            owner_token=raw_token,
        )

    @app.get(
        "/admin/teams",
        response_model=TeamListResponse,
        dependencies=[Depends(require_admin)],
        tags=["teams"],
    )
    def list_teams(request: Request) -> TeamListResponse:
        store: Store = request.app.state.store
        workspace_id: str = request.app.state.config.workspace_id
        teams = store.list_teams(workspace_id=workspace_id)
        return TeamListResponse(teams=[_team_view(store, team) for team in teams])

    @app.delete(
        "/admin/teams/{team_slug}",
        dependencies=[Depends(require_admin)],
        tags=["teams"],
    )
    def delete_team(team_slug: str, request: Request) -> dict[str, str]:
        store: Store = request.app.state.store
        workspace_id: str = request.app.state.config.workspace_id
        team = store.get_team_by_slug(workspace_id=workspace_id, slug=team_slug)
        if team is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team not found: {team_slug}",
            )
        store.delete_team(team_id=team.id)
        return {"status": "ok", "message": f"Team {team_slug} deleted"}

    # ---------- Public: join via invite (must precede /teams/{slug}) ----------

    @app.post(
        "/teams/join",
        response_model=TeamJoinResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["teams"],
    )
    def join_team(payload: TeamJoinRequest, request: Request) -> TeamJoinResponse:
        store: Store = request.app.state.store
        try:
            team, member, raw_token = store.redeem_team_invite(
                code=payload.code.strip(),
                display_name=payload.display_name.strip(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        workspace_id: str = request.app.state.config.workspace_id
        if team.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invite belongs to a different workspace",
            )
        return TeamJoinResponse(
            team=_team_view(store, team),
            member=_member_view(member),
            token=raw_token,
        )

    # ---------- Member-scoped routes ----------

    @app.get(
        "/teams/{team_slug}",
        response_model=TeamView,
        tags=["teams"],
    )
    def get_team(
        team_slug: str,
        request: Request,
        principal: TeamPrincipal = Depends(get_team_principal),
    ) -> TeamView:
        store: Store = request.app.state.store
        return _team_view(store, principal.team)

    @app.put(
        "/teams/{team_slug}",
        response_model=TeamView,
        tags=["teams"],
    )
    def update_team(
        team_slug: str,
        payload: TeamUpdateRequest,
        request: Request,
        principal: TeamPrincipal = Depends(require_team_role("owner")),
    ) -> TeamView:
        store: Store = request.app.state.store
        team = store.update_team(
            team_id=principal.team.id,
            name=payload.name,
            description=payload.description,
        )
        if team is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found",
            )
        return _team_view(store, team)

    @app.get(
        "/teams/{team_slug}/members",
        response_model=TeamMembersResponse,
        tags=["teams"],
    )
    def list_members(
        team_slug: str,
        request: Request,
        principal: TeamPrincipal = Depends(get_team_principal),
    ) -> TeamMembersResponse:
        store: Store = request.app.state.store
        members = store.list_team_members(team_id=principal.team.id)
        return TeamMembersResponse(members=[_member_view(m) for m in members])

    @app.put(
        "/teams/{team_slug}/members/{member_id}/role",
        response_model=TeamMemberView,
        tags=["teams"],
    )
    def update_member_role(
        team_slug: str,
        member_id: int,
        payload: TeamMemberRoleUpdateRequest,
        request: Request,
        principal: TeamPrincipal = Depends(require_team_role("owner")),
    ) -> TeamMemberView:
        store: Store = request.app.state.store
        member = store.get_team_member(member_id=member_id)
        if member is None or member.team_id != principal.team.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in this team",
            )
        if member.role == "owner" and payload.role != "owner":
            if store.count_team_owners(team_id=principal.team.id) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot demote the last remaining owner",
                )
        updated = store.update_team_member_role(member_id=member_id, role=payload.role)
        assert updated is not None
        return _member_view(updated)

    @app.delete(
        "/teams/{team_slug}/members/{member_id}",
        tags=["teams"],
    )
    def remove_member(
        team_slug: str,
        member_id: int,
        request: Request,
        principal: TeamPrincipal = Depends(require_team_role("owner")),
    ) -> dict[str, str]:
        store: Store = request.app.state.store
        member = store.get_team_member(member_id=member_id)
        if member is None or member.team_id != principal.team.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in this team",
            )
        if member.role == "owner" and store.count_team_owners(team_id=principal.team.id) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last remaining owner",
            )
        store.delete_team_member(member_id=member_id)
        return {"status": "ok", "message": f"Member {member.display_name} removed"}

    # ---------- Invites ----------

    @app.post(
        "/teams/{team_slug}/invites",
        response_model=TeamInviteView,
        status_code=status.HTTP_201_CREATED,
        tags=["teams"],
    )
    def create_invite(
        team_slug: str,
        payload: TeamInviteCreateRequest,
        request: Request,
        principal: TeamPrincipal = Depends(require_team_role("owner")),
    ) -> TeamInviteView:
        store: Store = request.app.state.store
        try:
            invite = store.create_team_invite(
                team_id=principal.team.id,
                role=payload.role,
                max_uses=payload.max_uses,
                expires_at=payload.expires_at,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return _invite_view(invite)

    @app.get(
        "/teams/{team_slug}/invites",
        response_model=TeamInvitesResponse,
        tags=["teams"],
    )
    def list_invites(
        team_slug: str,
        request: Request,
        principal: TeamPrincipal = Depends(require_team_role("owner")),
    ) -> TeamInvitesResponse:
        store: Store = request.app.state.store
        invites = store.list_team_invites(team_id=principal.team.id)
        return TeamInvitesResponse(invites=[_invite_view(invite) for invite in invites])

    @app.delete(
        "/teams/{team_slug}/invites/{invite_id}",
        response_model=TeamInviteView,
        tags=["teams"],
    )
    def revoke_invite(
        team_slug: str,
        invite_id: int,
        request: Request,
        principal: TeamPrincipal = Depends(require_team_role("owner")),
    ) -> TeamInviteView:
        store: Store = request.app.state.store
        invites = {inv.id: inv for inv in store.list_team_invites(team_id=principal.team.id)}
        if invite_id not in invites:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite not found in this team",
            )
        revoked = store.revoke_team_invite(invite_id=invite_id)
        assert revoked is not None
        return _invite_view(revoked)

    # ---------- Entries (knowledge content) ----------

    @app.get(
        "/teams/{team_slug}/entries",
        response_model=TeamEntriesResponse,
        tags=["teams"],
    )
    def list_entries(
        team_slug: str,
        request: Request,
        principal: TeamPrincipal = Depends(get_team_principal),
        tag: str | None = Query(default=None, max_length=80),
        query: str | None = Query(default=None, max_length=200),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> TeamEntriesResponse:
        store: Store = request.app.state.store
        tag_filter = tag.lstrip("#").strip() if tag else None
        entries = store.list_team_entries(
            team_id=principal.team.id,
            tag=tag_filter,
            query=query,
            limit=limit,
            offset=offset,
        )
        # `tag LIKE` is approximate; do a strict post-filter to make sure the
        # tag matches as a full token, not just a substring.
        if tag_filter:
            entries = [entry for entry in entries if _entry_matches_tag(entry, tag_filter)]
        total = len(
            store.list_team_entries(
                team_id=principal.team.id, tag=tag_filter, query=query, limit=10000,
            )
        )
        return TeamEntriesResponse(
            entries=[_entry_view(entry) for entry in entries],
            total=total,
        )

    @app.post(
        "/teams/{team_slug}/entries",
        response_model=TeamEntryView,
        status_code=status.HTTP_201_CREATED,
        tags=["teams"],
    )
    async def create_entry(
        team_slug: str,
        payload: TeamEntryCreateRequest,
        request: Request,
        principal: TeamPrincipal = Depends(require_team_role("editor")),
    ) -> TeamEntryView:
        store: Store = request.app.state.store
        try:
            entry = store.create_team_entry(
                team_id=principal.team.id,
                title=payload.title,
                body=payload.body,
                tags=payload.tags,
                author_member_id=principal.member.id if principal.member else None,
                author_display_name=(
                    principal.member.display_name if principal.member else "admin"
                ),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        await _reindex_entry_vectors(request, team_id=principal.team.id, entry=entry)
        return _entry_view(entry)

    @app.get(
        "/teams/{team_slug}/entries/{uid}",
        response_model=TeamEntryView,
        tags=["teams"],
    )
    def get_entry(
        team_slug: str,
        uid: str,
        request: Request,
        principal: TeamPrincipal = Depends(get_team_principal),
    ) -> TeamEntryView:
        store: Store = request.app.state.store
        entry = store.get_team_entry(team_id=principal.team.id, uid=uid)
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entry not found: {uid}",
            )
        return _entry_view(entry)

    @app.put(
        "/teams/{team_slug}/entries/{uid}",
        response_model=TeamEntryView,
        tags=["teams"],
    )
    async def update_entry(
        team_slug: str,
        uid: str,
        payload: TeamEntryUpdateRequest,
        request: Request,
        principal: TeamPrincipal = Depends(require_team_role("editor")),
    ) -> TeamEntryView:
        store: Store = request.app.state.store
        existing = store.get_team_entry(team_id=principal.team.id, uid=uid)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entry not found: {uid}",
            )
        # Editors can only edit their own entries; owners can edit anything.
        if (
            principal.role == "editor"
            and principal.member is not None
            and existing.author_member_id != principal.member.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Editors can only modify entries they authored",
            )
        updated = store.update_team_entry(
            team_id=principal.team.id,
            uid=uid,
            title=payload.title,
            body=payload.body,
            tags=payload.tags,
        )
        assert updated is not None
        await _reindex_entry_vectors(request, team_id=principal.team.id, entry=updated)
        return _entry_view(updated)

    @app.delete(
        "/teams/{team_slug}/entries/{uid}",
        tags=["teams"],
    )
    def delete_entry(
        team_slug: str,
        uid: str,
        request: Request,
        principal: TeamPrincipal = Depends(require_team_role("editor")),
    ) -> dict[str, str]:
        store: Store = request.app.state.store
        existing = store.get_team_entry(team_id=principal.team.id, uid=uid)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entry not found: {uid}",
            )
        if (
            principal.role == "editor"
            and principal.member is not None
            and existing.author_member_id != principal.member.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Editors can only delete entries they authored",
            )
        store.delete_team_entry(team_id=principal.team.id, uid=uid)
        return {"status": "ok", "uid": uid}

    # ---------- Search & QA ----------

    @app.post(
        "/teams/{team_slug}/search",
        response_model=TeamSearchResponse,
        tags=["teams"],
    )
    async def search_entries(
        team_slug: str,
        payload: TeamSearchRequest,
        request: Request,
        principal: TeamPrincipal = Depends(get_team_principal),
    ) -> TeamSearchResponse:
        store: Store = request.app.state.store
        tag_filter = payload.tag.lstrip("#").strip() if payload.tag else None
        retrieval_mode = "text"
        scored: list[tuple[TeamEntryRecord, float]] = []

        if payload.use_vector:
            client = _build_embedding_client(request)
            if client is not None:
                try:
                    query_embeddings = await client.get_embeddings([payload.query])
                except LLMClientError as exc:
                    LOGGER.warning("Team search embedding failed: %s", exc)
                    query_embeddings = []
                if query_embeddings:
                    vector_hits = store.search_team_entries_semantic(
                        team_id=principal.team.id,
                        query_embedding=query_embeddings[0],
                        limit=payload.top_k * 2,
                    )
                    seen: set[str] = set()
                    for unit, score in vector_hits:
                        if unit.entry_uid in seen:
                            continue
                        entry = store.get_team_entry(
                            team_id=principal.team.id, uid=unit.entry_uid,
                        )
                        if entry is None:
                            continue
                        if not _entry_matches_tag(entry, tag_filter):
                            continue
                        seen.add(unit.entry_uid)
                        scored.append((entry, float(score)))
                    if scored:
                        retrieval_mode = "vector"

        if not scored:
            all_entries = store.list_team_entries(
                team_id=principal.team.id, tag=tag_filter, limit=10000,
            )
            needle = payload.query.lower()
            for entry in all_entries:
                if not _entry_matches_tag(entry, tag_filter):
                    continue
                if not _entry_matches_query(entry, payload.query):
                    continue
                score = 0.0
                if entry.title and needle in entry.title.lower():
                    score += 1.0
                if needle in entry.body.lower():
                    score += 0.5
                if any(needle in tag.lower() for tag in entry.tags):
                    score += 0.3
                scored.append((entry, score))
            scored.sort(key=lambda pair: pair[1], reverse=True)
            retrieval_mode = "text"

        scored = scored[: payload.top_k]
        hits = [
            TeamSearchHit(
                entry=_entry_view(entry),
                score=round(score, 4),
                snippet=_snippet(entry.body or entry.title),
            )
            for entry, score in scored
        ]
        return TeamSearchResponse(hits=hits, retrieval_mode=retrieval_mode)

    @app.post(
        "/teams/{team_slug}/qa/generate-prompt",
        response_model=TeamPromptResponse,
        tags=["teams"],
    )
    async def generate_prompt(
        team_slug: str,
        payload: TeamPromptRequest,
        request: Request,
        principal: TeamPrincipal = Depends(get_team_principal),
    ) -> TeamPromptResponse:
        # Reuse the search route's logic via direct call so we don't duplicate.
        search_payload = TeamSearchRequest(
            query=payload.query,
            tag=payload.tag,
            top_k=payload.top_k,
            use_vector=payload.use_vector,
        )
        search_result = await search_entries(
            team_slug=team_slug,
            payload=search_payload,
            request=request,
            principal=principal,
        )
        context_blocks: list[str] = []
        for index, hit in enumerate(search_result.hits, start=1):
            entry = hit.entry
            tag_str = " ".join(f"#{tag}" for tag in entry.tags)
            header = f"### {index}. {entry.title or entry.uid} (UID: {entry.uid})"
            if entry.author_display_name:
                header += f" — 作者：{entry.author_display_name}"
            block = f"{header}\n"
            if tag_str:
                block += f"标签：{tag_str}\n"
            block += f"内容：\n{entry.body}\n"
            context_blocks.append(block)

        system_prompt = payload.system_prompt.strip() or (
            "你是该团队知识库的专属问答助手，"
            "请仅基于下方知识库参考上下文回答问题。"
        )
        assembled = f"# 系统提示\n{system_prompt}\n\n# 团队知识库参考上下文（{principal.team.name}）\n"
        if context_blocks:
            assembled += "\n\n".join(context_blocks)
        else:
            assembled += "（未在团队知识库内找到符合条件的条目）\n"
        assembled += f"\n\n# 用户提问\n{payload.query}\n"
        return TeamPromptResponse(
            assembled_prompt=assembled,
            retrieved_count=len(search_result.hits),
            retrieval_mode=search_result.retrieval_mode,
            sources=[hit.entry for hit in search_result.hits],
        )
