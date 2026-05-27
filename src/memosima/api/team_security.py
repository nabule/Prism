"""Team knowledge base authentication & authorization helpers.

The personal sidecar exposes an admin token (`SIDECAR_ADMIN_TOKEN`) that already
grants full power over the service. For team workflows, we additionally issue
per-member access tokens (returned at member creation / invite redemption time)
which are stored hashed (`sha256`) in `team_members.token_hash`.

Requests authenticate via the `Authorization: Bearer <token>` header:

* If the token equals the admin token, the caller is treated as a synthetic
  "owner" member that can act on every team in the workspace.
* Otherwise the token is looked up in `team_members`. The matching member must
  belong to the team identified in the route path.

Roles are ranked owner > editor > viewer. Endpoints can require a minimum role
via `require_team_role(...)`.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from memosima.db.store import (
    Store,
    TeamMemberRecord,
    TeamRecord,
    team_role_at_least,
)


@dataclass(frozen=True)
class TeamPrincipal:
    """The authenticated actor for a team-scoped request.

    `member` is None when the caller authenticated using the global admin token.
    """

    team: TeamRecord
    role: str
    member: TeamMemberRecord | None
    is_admin: bool


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer ") :].strip()
    return token or None


def _team_or_404(store: Store, workspace_id: str, slug: str) -> TeamRecord:
    team = store.get_team_by_slug(workspace_id=workspace_id, slug=slug)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found: {slug}",
        )
    return team


def get_team_principal(team_slug: str, request: Request) -> TeamPrincipal:
    """FastAPI dependency that resolves a `TeamPrincipal` from path + bearer."""
    store: Store = request.app.state.store
    workspace_id: str = request.app.state.config.workspace_id
    admin_token: str | None = getattr(request.app.state, "admin_token", None)

    token = _extract_bearer(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization bearer token",
        )

    if admin_token and token == admin_token:
        team = _team_or_404(store, workspace_id, team_slug)
        return TeamPrincipal(team=team, role="owner", member=None, is_admin=True)

    found = store.find_team_member_by_token(token)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid team token",
        )
    member, team = found
    if team.workspace_id != workspace_id or team.slug != team_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not belong to this team",
        )
    return TeamPrincipal(team=team, role=member.role, member=member, is_admin=False)


def require_team_role(required: str):
    """Build a dependency that asserts the principal's role is at least `required`."""

    def _check(principal: TeamPrincipal = Depends(get_team_principal)) -> TeamPrincipal:
        if not team_role_at_least(principal.role, required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires at least the '{required}' role",
            )
        return principal

    return _check
