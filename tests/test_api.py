from __future__ import annotations

from fastapi.testclient import TestClient

from memosima.api.app import create_app

from helpers import app_config_text, models_config_text, write_yaml


def test_health_reports_model_without_exposing_key(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")

    client = TestClient(create_app(str(app_path), str(models_path)))
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["models_default_provider"] == "openrouter"
    assert data["models_default_model"] == "deepseek/deepseek-v4-flash:free"
    assert data["models_api_key_present"] is True
    assert "secret-key" not in response.text


def test_webhook_creates_idempotent_job(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    client = TestClient(create_app(str(app_path), str(models_path)))
    payload = {"type": "MEMO_CREATED", "memo": {"name": "memos/abc123", "updateTime": "v1"}}

    first = client.post("/webhooks/memos", json=payload)
    second = client.post("/webhooks/memos", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["job_id"] == second.json()["job_id"]


def test_admin_jobs_requires_token_and_lists_jobs(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    client = TestClient(create_app(str(app_path), str(models_path)))
    client.post("/webhooks/memos", json={"memo": {"name": "memos/abc123"}})

    unauthorized = client.get("/admin/jobs")
    authorized = client.get("/admin/jobs", headers={"Authorization": "Bearer admin-token"})

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["jobs"][0]["status"] == "pending"


def test_admin_ui_returns_debug_page_without_exposing_token(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")

    client = TestClient(create_app(str(app_path), str(models_path)))
    response = client.get("/admin/ui")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Memosima Admin" in response.text
    assert "/admin/jobs" in response.text
    assert "/admin/tag-candidates" in response.text
    assert "admin-token" not in response.text
    assert "secret-key" not in response.text


def test_admin_tag_candidates_review_flow(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    app = create_app(str(app_path), str(models_path))
    app.state.store.upsert_tag_candidate(
        workspace_id="default",
        path="#项目/新方向",
        parent_path="#项目",
        reason="memo contains a tag outside the approved taxonomy",
        source_memo_uid="abc123",
        similar_tags=["#项目/个人AI知识库"],
    )
    client = TestClient(app)

    unauthorized = client.get("/admin/tag-candidates")
    listed = client.get("/admin/tag-candidates", headers={"Authorization": "Bearer admin-token"})
    candidate_id = listed.json()["candidates"][0]["id"]
    approved = client.post(
        f"/admin/tag-candidates/{candidate_id}/approve",
        headers={"Authorization": "Bearer admin-token"},
        json={"note": "纳入正式标签"},
    )
    remaining = client.get("/admin/tag-candidates", headers={"Authorization": "Bearer admin-token"})

    assert unauthorized.status_code == 401
    assert listed.status_code == 200
    assert listed.json()["candidates"][0]["path"] == "#项目/新方向"
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewer_note"] == "纳入正式标签"
    assert remaining.json()["candidates"] == []
