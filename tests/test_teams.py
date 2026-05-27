"""Tests for the team knowledge base feature.

These tests cover the full life-cycle:

* admin creates a team and receives an owner token
* owner generates an invite, a viewer redeems it
* role-based access control (editor only edits own entries, last-owner protection)
* entry CRUD and tag/keyword filtering
* search and prompt assembly in text mode (no embedding key configured) and
  vector mode (with a monkey-patched ``EmbeddingClient``).
"""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from memosima.api.app import create_app

from helpers import app_config_text, models_config_text, write_yaml


# ----- fixtures -----


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    # Make sure no real embedding key leaks in from the host's env.
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    test_client = TestClient(create_app(str(app_path), str(models_path)))
    yield test_client


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer admin-token"}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_team(client: TestClient, slug: str = "platform", name: str = "Platform 团队"):
    response = client.post(
        "/admin/teams",
        headers=_admin_headers(),
        json={"slug": slug, "name": name, "description": "core platform"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["team"], body["owner_token"], body["owner_member_id"]


def _create_invite(client: TestClient, slug: str, owner_token: str, role: str = "editor", max_uses: int = 0):
    response = client.post(
        f"/teams/{slug}/invites",
        headers=_bearer(owner_token),
        json={"role": role, "max_uses": max_uses},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _join(client: TestClient, code: str, display_name: str):
    response = client.post(
        "/teams/join",
        json={"code": code, "display_name": display_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ----- tests -----


def test_admin_creates_team_and_returns_owner_token(client: TestClient):
    response = client.post(
        "/admin/teams",
        headers=_admin_headers(),
        json={"slug": "growth", "name": "增长团队"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["team"]["slug"] == "growth"
    assert body["team"]["name"] == "增长团队"
    assert body["team"]["member_count"] == 1
    assert body["team"]["entry_count"] == 0
    assert body["owner_token"].startswith("team_")
    assert isinstance(body["owner_member_id"], int)


def test_admin_team_creation_requires_admin_token(client: TestClient):
    response = client.post(
        "/admin/teams",
        json={"slug": "growth", "name": "增长团队"},
    )
    assert response.status_code == 401


def test_team_slug_validation_rejects_bad_input(client: TestClient):
    bad = client.post(
        "/admin/teams",
        headers=_admin_headers(),
        json={"slug": "-Bad-Slug", "name": "x"},
    )
    assert bad.status_code == 400


def test_duplicate_slug_returns_conflict(client: TestClient):
    _create_team(client, "ops")
    duplicate = client.post(
        "/admin/teams",
        headers=_admin_headers(),
        json={"slug": "ops", "name": "ops2"},
    )
    assert duplicate.status_code == 409


def test_invite_and_join_flow_issues_token(client: TestClient):
    _team, owner_token, _ = _create_team(client)
    invite = _create_invite(client, "platform", owner_token, role="editor", max_uses=2)
    assert invite["code"]

    joined = _join(client, invite["code"], "Alice")
    assert joined["token"].startswith("team_")
    assert joined["member"]["role"] == "editor"
    assert joined["member"]["display_name"] == "Alice"

    # Second redemption succeeds; third should fail because max_uses=2
    _join(client, invite["code"], "Bob")
    failed = client.post(
        "/teams/join",
        json={"code": invite["code"], "display_name": "Carol"},
    )
    assert failed.status_code == 400


def test_revoked_invite_cannot_be_redeemed(client: TestClient):
    _team, owner_token, _ = _create_team(client)
    invite = _create_invite(client, "platform", owner_token)
    revoke = client.delete(
        f"/teams/platform/invites/{invite['id']}",
        headers=_bearer(owner_token),
    )
    assert revoke.status_code == 200
    assert revoke.json()["revoked_at"] is not None
    failed = client.post(
        "/teams/join",
        json={"code": invite["code"], "display_name": "Mallory"},
    )
    assert failed.status_code == 400


def test_member_cannot_act_on_another_team(client: TestClient):
    _create_team(client, "platform")
    _team_b, owner_b_token, _ = _create_team(client, "data")
    invite_b = _create_invite(client, "data", owner_b_token)
    member_b = _join(client, invite_b["code"], "Dan")

    response = client.get(
        "/teams/platform/entries",
        headers=_bearer(member_b["token"]),
    )
    assert response.status_code == 403


def test_entry_crud_with_editor_isolation(client: TestClient):
    _team, owner_token, owner_member_id = _create_team(client)
    invite_editor = _create_invite(client, "platform", owner_token, role="editor")
    invite_viewer = _create_invite(client, "platform", owner_token, role="viewer")
    editor = _join(client, invite_editor["code"], "Ed")
    viewer = _join(client, invite_viewer["code"], "Val")

    # Editor creates an entry
    created = client.post(
        "/teams/platform/entries",
        headers=_bearer(editor["token"]),
        json={
            "title": "On-call playbook",
            "body": "1. Check pager\n2. Acknowledge\n3. Triage",
            "tags": ["#运维", "playbook"],
        },
    )
    assert created.status_code == 201
    entry = created.json()
    assert entry["author_display_name"] == "Ed"
    # Tags are stripped of leading # for storage but returned as plain strings.
    assert set(entry["tags"]) == {"运维", "playbook"}

    # Viewer can read, but cannot create
    listed = client.get(
        "/teams/platform/entries",
        headers=_bearer(viewer["token"]),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    viewer_create = client.post(
        "/teams/platform/entries",
        headers=_bearer(viewer["token"]),
        json={"title": "x", "body": "y"},
    )
    assert viewer_create.status_code == 403

    # Another editor cannot edit the first editor's entry
    invite_e2 = _create_invite(client, "platform", owner_token, role="editor")
    editor2 = _join(client, invite_e2["code"], "Eve")
    forbidden_update = client.put(
        f"/teams/platform/entries/{entry['uid']}",
        headers=_bearer(editor2["token"]),
        json={"title": "hijacked"},
    )
    assert forbidden_update.status_code == 403

    # Owner (the admin token) can edit anything
    admin_update = client.put(
        f"/teams/platform/entries/{entry['uid']}",
        headers=_admin_headers(),
        json={"title": "On-call playbook v2", "tags": ["运维", "v2"]},
    )
    assert admin_update.status_code == 200
    assert admin_update.json()["title"] == "On-call playbook v2"

    # Tag filtering
    by_tag = client.get(
        "/teams/platform/entries?tag=v2",
        headers=_bearer(viewer["token"]),
    )
    assert by_tag.status_code == 200
    assert by_tag.json()["total"] == 1

    no_match = client.get(
        "/teams/platform/entries?tag=does-not-exist",
        headers=_bearer(viewer["token"]),
    )
    assert no_match.json()["total"] == 0

    # Editor deletes their own entry
    deleted = client.delete(
        f"/teams/platform/entries/{entry['uid']}",
        headers=_bearer(editor["token"]),
    )
    assert deleted.status_code == 200


def test_text_search_finds_keyword_hits(client: TestClient):
    _team, owner_token, _ = _create_team(client)
    invite = _create_invite(client, "platform", owner_token, role="editor")
    member = _join(client, invite["code"], "Searcher")
    client.post(
        "/teams/platform/entries",
        headers=_bearer(member["token"]),
        json={"title": "数据库迁移手册", "body": "PostgreSQL 升级到 16 的步骤", "tags": ["db"]},
    )
    client.post(
        "/teams/platform/entries",
        headers=_bearer(member["token"]),
        json={"title": "测试报告", "body": "QA team weekly summary", "tags": ["qa"]},
    )

    response = client.post(
        "/teams/platform/search",
        headers=_bearer(member["token"]),
        json={"query": "PostgreSQL", "top_k": 5, "use_vector": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["retrieval_mode"] == "text"
    assert len(body["hits"]) == 1
    assert body["hits"][0]["entry"]["title"] == "数据库迁移手册"


def test_vector_search_uses_embedding_when_configured(client: TestClient, monkeypatch):
    """When SILICONFLOW_API_KEY is set, search should use vector mode."""
    monkeypatch.setenv("SILICONFLOW_API_KEY", "fake-embedding-key")

    # Monkey-patch EmbeddingClient.get_embeddings to return a deterministic
    # vector based on the input text — entries whose text starts the same way
    # as the query will get a higher cosine score.
    from memosima.api import teams as teams_mod

    async def fake_get_embeddings(self, texts):
        results = []
        for text in texts:
            # Map each character to a slot in a fixed-size vector so that
            # similar texts produce similar vectors.
            buckets = [0.0] * 32
            for char in text.lower():
                buckets[ord(char) % 32] += 1.0
            results.append(buckets)
        return results

    monkeypatch.setattr(
        "memosima.llm.provider.EmbeddingClient.get_embeddings",
        fake_get_embeddings,
    )

    _team, owner_token, _ = _create_team(client)
    invite = _create_invite(client, "platform", owner_token, role="editor")
    member = _join(client, invite["code"], "Vec")
    client.post(
        "/teams/platform/entries",
        headers=_bearer(member["token"]),
        json={"title": "PostgreSQL upgrade", "body": "Upgrade Postgres to v16", "tags": ["db"]},
    )
    client.post(
        "/teams/platform/entries",
        headers=_bearer(member["token"]),
        json={"title": "Marketing brief", "body": "Q3 campaign overview", "tags": ["marketing"]},
    )

    response = client.post(
        "/teams/platform/search",
        headers=_bearer(member["token"]),
        json={"query": "Postgres upgrade plan", "top_k": 5, "use_vector": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["retrieval_mode"] == "vector"
    assert body["hits"], "expected at least one vector hit"
    assert body["hits"][0]["entry"]["title"] == "PostgreSQL upgrade"


def test_prompt_generation_assembles_context(client: TestClient):
    _team, owner_token, _ = _create_team(client)
    invite = _create_invite(client, "platform", owner_token, role="editor")
    member = _join(client, invite["code"], "Writer")
    client.post(
        "/teams/platform/entries",
        headers=_bearer(member["token"]),
        json={
            "title": "事故复盘 - 2026-03",
            "body": "数据库连接池被打满导致 P0 故障",
            "tags": ["postmortem"],
        },
    )

    response = client.post(
        "/teams/platform/qa/generate-prompt",
        headers=_bearer(member["token"]),
        json={
            "query": "P0 故障",
            "system_prompt": "你是事故复盘助手。",
            "top_k": 3,
            "use_vector": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "事故复盘助手" in body["assembled_prompt"]
    assert "数据库连接池" in body["assembled_prompt"]
    assert body["retrieved_count"] == 1
    assert body["sources"][0]["title"] == "事故复盘 - 2026-03"


def test_owner_role_protection(client: TestClient):
    _team, owner_token, owner_member_id = _create_team(client, "growth")
    invite = _create_invite(client, "growth", owner_token, role="editor")
    member = _join(client, invite["code"], "Newcomer")

    # Get the admin-side member ID for the auto-created owner via the listing.
    members = client.get(
        "/teams/growth/members",
        headers=_admin_headers(),
    ).json()["members"]
    owner_entry = next(m for m in members if m["role"] == "owner")

    # Attempt to demote the sole owner — should fail.
    demoted = client.put(
        f"/teams/growth/members/{owner_entry['id']}/role",
        headers=_bearer(owner_token),
        json={"role": "viewer"},
    )
    assert demoted.status_code == 409

    # Promote the new member to owner — now there are two; demotion allowed.
    promoted = client.put(
        f"/teams/growth/members/{member['member']['id']}/role",
        headers=_bearer(owner_token),
        json={"role": "owner"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "owner"

    demoted_again = client.put(
        f"/teams/growth/members/{owner_entry['id']}/role",
        headers=_bearer(owner_token),
        json={"role": "editor"},
    )
    assert demoted_again.status_code == 200


def test_team_deletion_cascades(client: TestClient):
    _team, owner_token, _ = _create_team(client, "scratch")
    invite = _create_invite(client, "scratch", owner_token, role="editor")
    member = _join(client, invite["code"], "Tester")
    client.post(
        "/teams/scratch/entries",
        headers=_bearer(member["token"]),
        json={"title": "draft", "body": "to be deleted"},
    )

    response = client.delete(
        "/admin/teams/scratch",
        headers=_admin_headers(),
    )
    assert response.status_code == 200

    after = client.get(
        "/teams/scratch",
        headers=_bearer(member["token"]),
    )
    assert after.status_code in {401, 403, 404}
