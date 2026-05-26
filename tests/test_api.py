from __future__ import annotations

import io
import json
import zipfile
import pytest

from fastapi.testclient import TestClient

from memosima.api.app import create_app
from memosima.llm.provider import LLMClientError

from helpers import app_config_text, models_config_text, prompts_config_text, write_yaml


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
    assert data["models_default_model"] == "google/gemma-3-27b-it"
    assert data["models_api_key_present"] is True
    assert "commit_hash" in data
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


def test_admin_prompts_can_be_read_and_updated(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "prompts.yaml", prompts_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    client = TestClient(create_app(str(app_path), str(models_path)))
    listed = client.get("/admin/prompts", headers={"Authorization": "Bearer admin-token"})
    updated = client.put(
        "/admin/prompts/organize-memo",
        headers={"Authorization": "Bearer admin-token"},
        json={"system": "新的系统提示 {active_tags}", "user": "新的用户提示 {content}"},
    )
    listed_again = client.get("/admin/prompts", headers={"Authorization": "Bearer admin-token"})

    assert listed.status_code == 200
    assert "测试系统提示词" in listed.json()["organize_memo"]["system"]
    assert updated.status_code == 200
    assert listed.json()["organize_memo"]["provider"] is None
    assert listed.json()["reminder_extraction"]["provider"] is None
    assert updated.json()["system"] == "新的系统提示 {active_tags}"
    assert updated.json()["provider"] is None
    assert listed_again.json()["organize_memo"]["user"] == "新的用户提示 {content}"
    assert "测试标签总结系统提示词" in listed_again.json()["tag_summary"]["system"]
    assert "提醒时间抽取器" in listed_again.json()["reminder_extraction"]["system"]


def test_admin_ai_call_prompts_can_store_provider_selection(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "prompts.yaml", prompts_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    client = TestClient(create_app(str(app_path), str(models_path)))
    tag_updated = client.put(
        "/admin/prompts/tag-summary",
        headers={"Authorization": "Bearer admin-token"},
        json={"provider": "deepseek", "system": "标签总结系统", "user": "标签总结用户 {tag} {memos_markdown}"},
    )
    reminder_updated = client.put(
        "/admin/prompts/reminder-extraction",
        headers={"Authorization": "Bearer admin-token"},
        json={
            "provider": "openrouter",
            "system": "提醒系统 {trigger_tag}",
            "user": "提醒用户 {now} {timezone} {content}",
        },
    )
    listed = client.get("/admin/prompts", headers={"Authorization": "Bearer admin-token"})

    assert tag_updated.status_code == 200
    assert tag_updated.json()["provider"] == "deepseek"
    assert tag_updated.json()["system"] == "标签总结系统"
    assert reminder_updated.status_code == 200
    assert reminder_updated.json()["provider"] == "openrouter"
    assert listed.json()["tag_summary"]["user"] == "标签总结用户 {tag} {memos_markdown}"
    assert listed.json()["tag_summary"]["provider"] == "deepseek"
    assert listed.json()["reminder_extraction"]["provider"] == "openrouter"
    assert listed.json()["reminder_extraction"]["user"] == "提醒用户 {now} {timezone} {content}"


def test_admin_models_can_be_read_and_updated_without_exposing_key(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    client = TestClient(create_app(str(app_path), str(models_path)))
    listed = client.get("/admin/models", headers={"Authorization": "Bearer admin-token"})
    updated = client.put(
        "/admin/models",
        headers={"Authorization": "Bearer admin-token"},
        json={
            "default_provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key_env": "DEEPSEEK_API_KEY",
            "default_model": "deepseek-v4-flash",
            "temperature": 0.1,
            "max_tokens": 1024,
            "response_format": "json_object",
            "extra_body": {"metadata": {"source": "admin-ui-test"}},
            "api_key": "deepseek-secret-key",
        },
    )
    health = client.get("/health")

    assert listed.status_code == 200
    assert "deepseek-secret-key" not in listed.text
    assert updated.status_code == 200
    assert updated.json()["default_provider"] == "deepseek"
    default_provider = [item for item in updated.json()["providers"] if item["is_default"]][0]
    assert default_provider["default_model"] == "deepseek-v4-flash"
    assert default_provider["api_key_present"] is True
    assert "deepseek-secret-key" not in updated.text
    assert "deepseek-secret-key" not in models_path.read_text(encoding="utf-8")
    assert "default_provider: deepseek" in models_path.read_text(encoding="utf-8")
    assert "default_model: deepseek-v4-flash" in models_path.read_text(encoding="utf-8")
    env_text = (tmp_path / ".env.local").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=deepseek-secret-key" in env_text
    assert health.json()["models_default_provider"] == "deepseek"
    assert health.json()["models_default_model"] == "deepseek-v4-flash"
    assert health.json()["models_api_key_present"] is True


def test_admin_models_rejects_multiline_api_key(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    client = TestClient(create_app(str(app_path), str(models_path)))
    response = client.put(
        "/admin/models",
        headers={"Authorization": "Bearer admin-token"},
        json={
            "default_provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key_env": "DEEPSEEK_API_KEY",
            "default_model": "deepseek-v4-flash",
            "api_key": "one-line\nINJECTED=value",
        },
    )

    assert response.status_code == 400
    assert not (tmp_path / ".env.local").exists()


def test_admin_retry_job_can_store_temporary_prompt_override(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    app = create_app(str(app_path), str(models_path))
    job, _ = app.state.store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:prompt-retry",
        payload={"memo_uid": "prompt-retry"},
    )
    app.state.store.mark_job_failed(job.id, "boom", max_attempts=1)
    client = TestClient(app)

    response = client.post(
        f"/admin/jobs/{job.id}/retry",
        headers={"Authorization": "Bearer admin-token"},
        json={"prompt_override": {"system": "临时系统 {active_tags}", "user": "临时用户 {content}"}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["payload"]["llm_prompt_override"] == {
        "system": "临时系统 {active_tags}",
        "user": "临时用户 {content}",
    }


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
    assert "/admin/reminders" in response.text
    assert "/admin/backups/download" in response.text
    assert "/admin/backups/restore" in response.text
    assert "/admin/prompts" in response.text
    assert "/admin/models" in response.text
    assert "AI 调用配置" in response.text
    assert "单条 memo 整理使用的模型配置" in response.text
    assert "标签总结使用的模型配置" in response.text
    assert "提醒抽取使用的模型配置" in response.text
    assert 'class="shell"' in response.text
    assert 'role="tablist"' in response.text
    assert 'data-tab-target="overview"' in response.text
    assert 'data-tab-target="jobs"' in response.text
    assert 'data-tab-target="tags"' in response.text
    assert 'data-tab-target="prompts"' in response.text
    assert 'data-tab-target="models"' in response.text
    assert 'data-tab-target="reminders"' in response.text
    assert 'data-tab-target="backup"' in response.text
    assert 'data-panel="overview"' in response.text
    assert 'data-panel="tags"' in response.text
    assert 'data-panel="backup"' in response.text
    assert "showPanelFromHash" in response.text
    assert "hashPanelMap" in response.text
    assert 'id="jobs"' in response.text
    assert 'id="tag-candidates"' in response.text
    assert 'id="tag-summary"' in response.text
    assert 'id="backup"' in response.text
    assert 'id="models"' in response.text
    assert "showPanelFromHash" in response.text
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


def test_admin_tag_candidates_review_flow_with_custom_path(tmp_path, monkeypatch):
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

    listed = client.get("/admin/tag-candidates", headers={"Authorization": "Bearer admin-token"})
    candidate_id = listed.json()["candidates"][0]["id"]
    
    approved = client.post(
        f"/admin/tag-candidates/{candidate_id}/approve",
        headers={"Authorization": "Bearer admin-token"},
        json={"note": "修改并纳入正式标签", "path": "#项目/修改后的新方向"},
    )
    
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewer_note"] == "修改并纳入正式标签"
    assert approved.json()["path"] == "#项目/修改后的新方向"
    assert approved.json()["parent_path"] == "#项目"


def test_admin_reminders_requires_token_lists_retries_and_cancels(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    app = create_app(str(app_path), str(models_path))
    reminder, _ = app.state.store.create_reminder(
        workspace_id="default",
        source_memo_uid="abc123",
        title="提交周报",
        body="周报发给团队",
        due_at="2026-05-22T01:30:00+00:00",
        timezone="Asia/Shanghai",
        confidence=0.92,
        raw_text="#提醒 明天 09:30 提交周报",
    )
    app.state.store.mark_reminder_failed(reminder.id, "webhook failed")
    client = TestClient(app)

    unauthorized = client.get("/admin/reminders")
    listed = client.get("/admin/reminders?status=failed", headers={"Authorization": "Bearer admin-token"})
    retried = client.post(
        f"/admin/reminders/{reminder.id}/retry",
        headers={"Authorization": "Bearer admin-token"},
    )
    cancelled = client.post(
        f"/admin/reminders/{reminder.id}/cancel",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert unauthorized.status_code == 401
    assert listed.status_code == 200
    assert listed.json()["reminders"][0]["title"] == "提交周报"
    assert listed.json()["reminders"][0]["status"] == "failed"
    assert retried.status_code == 200
    assert retried.json()["status"] == "pending"
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_admin_reminders_config(tmp_path, monkeypatch):
    import os
    app_yaml_content = app_config_text(tmp_path / "sidecar.db") + "\n" + """
reminders:
  enabled: true
  trigger_tag: "#提醒"
  webhook_url_env: REMINDER_WEBHOOK_URL
  confidence_threshold: 0.75
  request_timeout_seconds: 10
"""
    app_path = write_yaml(tmp_path / "app.yaml", app_yaml_content)
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("REMINDER_WEBHOOK_URL", "https://original-webhook.example.com")
    
    app = create_app(config_path=str(app_path), models_path=str(models_path))
    client = TestClient(app)

    # 1. GET config without token
    unauthorized = client.get("/admin/reminders/config")
    assert unauthorized.status_code == 401

    # 2. GET config with token
    response = client.get("/admin/reminders/config", headers={"Authorization": "Bearer admin-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["trigger_tag"] == "#提醒"
    assert data["confidence_threshold"] == 0.75
    assert data["request_timeout_seconds"] == 10.0
    assert data["webhook_url_present"] is True

    # 3. PUT config update
    update_payload = {
        "enabled": False,
        "trigger_tag": "#ALARM",
        "confidence_threshold": 0.85,
        "request_timeout_seconds": 15.0,
        "webhook_url": "https://new-webhook.example.com"
    }
    put_response = client.put(
        "/admin/reminders/config",
        json=update_payload,
        headers={"Authorization": "Bearer admin-token"}
    )
    assert put_response.status_code == 200
    updated_data = put_response.json()
    assert updated_data["enabled"] is False
    assert updated_data["trigger_tag"] == "#ALARM"
    assert updated_data["confidence_threshold"] == 0.85
    assert updated_data["request_timeout_seconds"] == 15.0
    assert updated_data["webhook_url_present"] is True

    # Verify app.yaml content got updated
    from memosima.core.config import _read_yaml
    yaml_content = _read_yaml(app_path)
    assert yaml_content["reminders"]["enabled"] is False
    assert yaml_content["reminders"]["trigger_tag"] == "#ALARM"
    assert yaml_content["reminders"]["confidence_threshold"] == 0.85
    assert yaml_content["reminders"]["request_timeout_seconds"] == 15.0

    # Verify env got updated
    assert os.getenv("REMINDER_WEBHOOK_URL") == "https://new-webhook.example.com"


def test_admin_backup_download_contains_database_and_non_secret_configs(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "prompts.yaml", prompts_config_text())
    write_yaml(tmp_path / "taxonomy.yaml", "system_tags:\n  original: \"#系统/原始记录\"\nbusiness_tags: []\naliases: []\ndisabled: []\n")
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")

    app = create_app(str(app_path), str(models_path))
    app.state.store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:backup",
        payload={"memo_uid": "backup"},
    )
    client = TestClient(app)

    unauthorized = client.get("/admin/backups/download")
    response = client.get("/admin/backups/download", headers={"Authorization": "Bearer admin-token"})

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "secret-key" not in response.content.decode("latin1")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "database/sidecar.db" in names
        assert "config/app.yaml" in names
        assert "config/models.yaml" in names
        assert "config/prompts.yaml" in names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["kind"] == "memosima-sidecar-backup"
        assert manifest["version"] == 1
        assert manifest["restore_behavior"] == "database_only"


def test_admin_backup_restore_replaces_sidecar_database(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    app = create_app(str(app_path), str(models_path))
    app.state.store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:before-backup",
        payload={"memo_uid": "before-backup"},
    )
    client = TestClient(app)
    backup = client.get("/admin/backups/download", headers={"Authorization": "Bearer admin-token"}).content

    app.state.store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:after-backup",
        payload={"memo_uid": "after-backup"},
    )
    assert len(app.state.store.list_jobs()) == 2

    unauthorized = client.post("/admin/backups/restore", content=backup, headers={"Content-Type": "application/zip"})
    restored = client.post(
        "/admin/backups/restore",
        content=backup,
        headers={"Authorization": "Bearer admin-token", "Content-Type": "application/zip"},
    )

    assert unauthorized.status_code == 401
    assert restored.status_code == 200
    data = restored.json()
    assert data["restored_database"] is True
    assert data["restored_configs"] is False
    jobs = app.state.store.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].idempotency_key == "memo:before-backup"


def test_admin_tag_summary_creates_summary_memo(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "prompts.yaml", prompts_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")

    class FakeMemosClient:
        created_memos: list[str] = []
        relations: list[tuple[str, str]] = []

        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, *, page_size, page_token=None, filter_text=None):
            assert page_size == 20
            assert page_token is None
            assert filter_text is None
            return {
                "memos": [
                    {
                        "name": "memos/source1",
                        "createTime": "2026-05-21T03:00:00Z",
                        "content": "个人 AI 知识库推进记录 #项目/个人AI知识库",
                        "tags": ["项目/个人AI知识库"],
                    },
                    {
                        "name": "memos/source-parent",
                        "createTime": "2026-05-21T03:05:00Z",
                        "content": "项目父标签直接记录 #项目",
                        "tags": ["项目"],
                    },
                    {
                        "name": "memos/source-content-child",
                        "createTime": "2026-05-21T03:10:00Z",
                        "content": "正文里只有子标签 #项目/高层总结",
                        "tags": [],
                    },
                    {
                        "name": "memos/other",
                        "content": "相似但不是子标签 #项目管理",
                        "tags": ["项目管理"],
                    },
                    {
                        "name": "memos/ai-summary",
                        "content": "#系统/AI整理 #项目/个人AI知识库\n\nAI 整理 memo",
                        "tags": ["系统/AI整理", "项目/个人AI知识库"],
                    },
                    {
                        "name": "memos/source-from-summary",
                        "createTime": "2026-05-21T03:15:00Z",
                        "content": "原文没有标签，只有 AI 整理结果命中了项目标签",
                        "tags": [],
                    },
                    {
                        "name": "memos/ai-summary-linked",
                        "content": "#系统/AI整理 #项目/个人AI知识库\n\nAI 整理 memo",
                        "tags": ["系统/AI整理", "项目/个人AI知识库"],
                    },
                    {
                        "name": "memos/tag-summary",
                        "content": "#系统/标签总结 #项目/个人AI知识库\n\n标签总结 memo",
                        "tags": ["系统/标签总结", "项目/个人AI知识库"],
                    },
                ]
            }

        async def create_memo(self, content):
            self.created_memos.append(content)
            return {"name": "memos/tag-summary-1", "content": content}

        async def upsert_memo_reference_relation(self, *, source_memo_uid, related_memo_uid):
            self.relations.append((source_memo_uid, related_memo_uid))
            return {}

    class FakeLLMClient:
        seen_memos_markdown = ""

        def __init__(self, *args, **kwargs):
            pass

        async def summarize_tag(self, *, tag, memos_markdown, memo_count, prompt_template):
            FakeLLMClient.seen_memos_markdown = memos_markdown
            assert tag == "#项目"
            assert memo_count == 4
            return "## 总览\n\n个人 AI 知识库正在推进，详见 [来源一](memos/source1) 和 memos/source-parent。"

    monkeypatch.setattr("memosima.api.app.MemosClient", FakeMemosClient)
    monkeypatch.setattr("memosima.api.app.OpenAICompatibleClient", FakeLLMClient)

    client = TestClient(create_app(str(app_path), str(models_path)))
    client.app.state.store.upsert_memo(
        workspace_id="default",
        memos_uid="ai-summary-linked",
        memo_type="ai_summary",
        source_memo_uid="source-from-summary",
        status="created",
    )
    response = client.post(
        "/admin/tag-summaries",
        headers={"Authorization": "Bearer admin-token"},
        json={"tag": "#项目", "limit": 20},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["summary_memo_uid"] == "tag-summary-1"
    assert data["memo_count"] == 4
    assert "#系统/标签总结 #项目" in data["content"]
    assert "source1" in data["content"]
    assert "memos/source1" not in data["content"]
    assert "来源一（memo UID：source1）" in data["content"]
    assert "source-parent" in data["content"]
    assert "memos/source-parent" not in data["content"]
    assert "memo UID：source-parent" in data["content"]
    assert "source-content-child" in data["content"]
    assert "source-from-summary" in data["content"]
    assert "memos/other" not in FakeLLMClient.seen_memos_markdown
    assert "memos/source1" not in FakeLLMClient.seen_memos_markdown
    assert "项目管理" not in FakeLLMClient.seen_memos_markdown
    assert "memos/ai-summary" not in FakeLLMClient.seen_memos_markdown
    assert "memos/ai-summary-linked" not in FakeLLMClient.seen_memos_markdown
    assert "memos/tag-summary" not in FakeLLMClient.seen_memos_markdown
    assert FakeMemosClient.created_memos == [data["content"]]
    assert FakeMemosClient.relations == [
        ("tag-summary-1", "source1"),
        ("tag-summary-1", "source-parent"),
        ("tag-summary-1", "source-content-child"),
        ("tag-summary-1", "source-from-summary"),
    ]


def test_admin_tag_summary_uses_configured_prompt_provider(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(
        tmp_path / "prompts.yaml",
        prompts_config_text()
        + """
tag_summary:
  provider: deepseek
  system: 标签总结系统
  user: 标签总结用户 {tag} {memo_count} {memos_markdown}
""",
    )
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")

    class FakeMemosClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, *, page_size, page_token=None, filter_text=None):
            return {
                "memos": [
                    {
                        "name": "memos/source1",
                        "createTime": "2026-05-21T03:00:00Z",
                        "content": "个人 AI 知识库推进记录 #项目/个人AI知识库",
                        "tags": ["项目/个人AI知识库"],
                    }
                ]
            }

        async def create_memo(self, content):
            return {"name": "memos/tag-summary-provider", "content": content}

        async def upsert_memo_reference_relation(self, *, source_memo_uid, related_memo_uid):
            return {}

    class FakeLLMClient:
        seen_provider = ""
        seen_api_key = ""

        def __init__(self, *, provider, api_key, timeout_seconds):
            FakeLLMClient.seen_provider = provider.name
            FakeLLMClient.seen_api_key = api_key

        async def summarize_tag(self, *, tag, memos_markdown, memo_count, prompt_template):
            return "## 总览\n\n使用独立模型生成。"

    monkeypatch.setattr("memosima.api.app.MemosClient", FakeMemosClient)
    monkeypatch.setattr("memosima.api.app.OpenAICompatibleClient", FakeLLMClient)

    client = TestClient(create_app(str(app_path), str(models_path)))
    response = client.post(
        "/admin/tag-summaries",
        headers={"Authorization": "Bearer admin-token"},
        json={"tag": "#项目/个人AI知识库", "limit": 20},
    )

    assert response.status_code == 200
    assert FakeLLMClient.seen_provider == "deepseek"
    assert FakeLLMClient.seen_api_key == "deepseek-key"


def test_admin_tag_summary_returns_bad_gateway_when_llm_fails(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "prompts.yaml", prompts_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")

    class FakeMemosClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, *, page_size, page_token=None, filter_text=None):
            return {
                "memos": [
                    {
                        "name": "memos/source1",
                        "createTime": "2026-05-21T03:00:00Z",
                        "content": "个人 AI 知识库推进记录 #项目/个人AI知识库",
                        "tags": ["项目/个人AI知识库"],
                    }
                ]
            }

    class FakeLLMClient:
        def __init__(self, *args, **kwargs):
            pass

        async def summarize_tag(self, *, tag, memos_markdown, memo_count, prompt_template):
            raise LLMClientError("LLM request failed: POST /chat/completions -> 500")

    monkeypatch.setattr("memosima.api.app.MemosClient", FakeMemosClient)
    monkeypatch.setattr("memosima.api.app.OpenAICompatibleClient", FakeLLMClient)

    client = TestClient(create_app(str(app_path), str(models_path)))
    response = client.post(
        "/admin/tag-summaries",
        headers={"Authorization": "Bearer admin-token"},
        json={"tag": "#项目/个人AI知识库", "limit": 20},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM tag summary request failed"


@pytest.mark.asyncio
async def test_reprocess_memo_endpoint(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    
    deleted_memos = []

    class FakeMemosClient:
        def __init__(self, *args, **kwargs):
            pass

        async def get_memo(self, memo_uid):
            return {"name": f"memos/{memo_uid}", "content": "Original content"}

        async def delete_memo(self, memo_uid):
            deleted_memos.append(memo_uid)

    monkeypatch.setattr("memosima.api.app.MemosClient", FakeMemosClient)

    client = TestClient(create_app(str(app_path), str(models_path)))
    store = client.app.state.store
    
    # Setup database with existing memos
    store.upsert_memo(
        workspace_id="default",
        memos_uid="original-1",
        memo_type="original",
        status="synced",
    )
    store.upsert_memo(
        workspace_id="default",
        memos_uid="summary-1",
        memo_type="ai_summary",
        source_memo_uid="original-1",
        status="created",
    )

    # 1. Test UID extraction and database deletion
    response = client.post(
        "/admin/jobs/reprocess-memo",
        headers={"Authorization": "Bearer admin-token"},
        json={
            "memo_url_or_uid": "http://localhost:8080/m/original-1",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat",
            "prompt_override": {
                "system": "Custom System",
                "user": "Custom User"
            }
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["memo_uid"] == "original-1"
    assert data["old_summaries_deleted"] == ["summary-1"]
    assert deleted_memos == ["summary-1"]
    
    # 2. Check if new job exists
    job = store.claim_next_job()
    assert job is not None
    assert job.type == "process_memo"
    assert job.payload["memo_uid"] == "original-1"
    assert job.payload["model_provider"] == "deepseek"
    assert job.payload["model_name"] == "deepseek-chat"
    assert job.payload["llm_prompt_override"] == {"system": "Custom System", "user": "Custom User"}
    
    # Check that SQLite is cleaned up
    summary_record = store.list_memos(workspace_id="default", memo_type="ai_summary")
    assert len(summary_record) == 0


@pytest.mark.asyncio
async def test_batch_reprocess_tag_endpoint(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    
    deleted_memos = []

    class FakeMemosClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, *args, **kwargs):
            return {
                "memos": [
                    {
                        "name": "memos/original-tag-1",
                        "content": "Original memo with tag #项目/数管",
                        "tags": ["项目/数管"],
                    }
                ],
                "nextPageToken": ""
            }

        async def delete_memo(self, memo_uid):
            deleted_memos.append(memo_uid)

    monkeypatch.setattr("memosima.api.app.MemosClient", FakeMemosClient)

    client = TestClient(create_app(str(app_path), str(models_path)))
    store = client.app.state.store
    
    # Setup old summary
    store.upsert_memo(
        workspace_id="default",
        memos_uid="original-tag-1",
        memo_type="original",
        status="synced",
    )
    store.upsert_memo(
        workspace_id="default",
        memos_uid="old-summary-tag-1",
        memo_type="ai_summary",
        source_memo_uid="original-tag-1",
        status="created",
    )

    response = client.post(
        "/admin/jobs/batch-reprocess-tag",
        headers={"Authorization": "Bearer admin-token"},
        json={
            "tag": "#项目",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat"
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tag"] == "#项目"
    assert data["matched_memo_count"] == 1
    assert data["jobs_created"] == 1
    assert data["old_summaries_deleted_count"] == 1
    assert deleted_memos == ["old-summary-tag-1"]

    # Verify job created in DB
    job = store.claim_next_job()
    assert job is not None
    assert job.payload["memo_uid"] == "original-tag-1"
    assert job.payload["model_provider"] == "deepseek"
    assert job.payload["model_name"] == "deepseek-chat"


@pytest.mark.asyncio
async def test_batch_reprocess_tags_multi_and_relation(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    deleted_memos = []

    class MockMemosClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, page_size, page_token=None):
            return {
                "memos": [
                    {
                        "name": "memos/original-tag-1",
                        "content": "含有标签 #项目 和 #AI 的笔记",
                        "tags": ["项目", "AI"],
                    },
                    {
                        "name": "memos/original-tag-2",
                        "content": "仅含有 #项目",
                        "tags": ["项目"],
                    }
                ]
            }

        async def delete_memo(self, uid):
            deleted_memos.append(uid)

    import memosima.api.app as app_module
    monkeypatch.setattr(app_module, "MemosClient", MockMemosClient)

    client = TestClient(create_app(str(app_path), str(models_path)))
    store = client.app.state.store

    store.upsert_memo(
        workspace_id="default",
        memos_uid="original-tag-1",
        memo_type="original",
        status="synced",
    )

    response = client.post(
        "/admin/jobs/batch-reprocess-tag",
        headers={"Authorization": "Bearer admin-token"},
        json={
            "tags": ["#项目", "#AI"],
            "relation": "AND",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == ["#项目", "#AI"]
    assert data["relation"] == "AND"
    assert data["matched_memo_count"] == 1  # 只有一个匹配 AND
    assert data["jobs_created"] == 1


@pytest.mark.asyncio
async def test_admin_tag_summary_multi_tags_and_relation(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")

    class FakeMemosClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, page_size, page_token=None):
            return {
                "memos": [
                    {
                        "name": "memos/source1",
                        "content": "含有标签 #项目 和 #AI 的笔记",
                        "tags": ["项目", "AI"],
                    },
                    {
                        "name": "memos/source2",
                        "content": "仅含有 #项目",
                        "tags": ["项目"],
                    }
                ]
            }

        async def create_memo(self, content):
            return {"name": "memos/tag-summary-123"}

        async def upsert_memo_reference_relation(self, source_memo_uid, related_memo_uid):
            pass

    class FakeLLMClient:
        def __init__(self, *args, **kwargs):
            pass

        async def summarize_tag(self, tag, memos_markdown, memo_count, prompt_template):
            assert "#项目" in tag
            assert "#AI" in tag
            assert "AND" in tag
            return "大模型输出的总结内容"

    import memosima.api.app as app_module
    monkeypatch.setattr(app_module, "MemosClient", FakeMemosClient)
    monkeypatch.setattr(app_module, "OpenAICompatibleClient", FakeLLMClient)

    client = TestClient(create_app(str(app_path), str(models_path)))
    store = client.app.state.store

    store.upsert_memo(
        workspace_id="default",
        memos_uid="source1",
        memo_type="original",
        status="synced",
    )

    response = client.post(
        "/admin/tag-summaries",
        headers={"Authorization": "Bearer admin-token"},
        json={
            "tags": ["#项目", "#AI"],
            "relation": "AND",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == ["#项目", "#AI"]
    assert data["relation"] == "AND"
    assert data["memo_count"] == 1
    assert data["summary_memo_uid"] == "tag-summary-123"
    assert "#系统/标签总结 #项目 #AI" in data["content"]


def test_delete_all_memos(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://localhost:5230")
    monkeypatch.setenv("MEMOS_API_TOKEN", "some-memos-token")

    list_called = []
    delete_called = []

    class MockMemosClient:
        def __init__(self, base_url, api_token, timeout_seconds=15):
            assert base_url == "http://localhost:5230"
            assert api_token == "some-memos-token"

        async def list_memos(self, page_size=20, page_token=None, filter_text=None):
            list_called.append((page_size, page_token))
            if page_token is None:
                return {
                    "memos": [
                        {"uid": "memo1", "name": "memos/memo1"},
                        {"uid": "memo2", "name": "memos/memo2"},
                    ],
                    "nextPageToken": "page-2",
                }
            elif page_token == "page-2":
                return {
                    "memos": [
                        {"uid": "memo3", "name": "memos/memo3"},
                    ],
                    "nextPageToken": None,
                }
            return {"memos": []}

        async def delete_memo(self, memo_uid):
            delete_called.append(memo_uid)

    import memosima.api.app as app_module
    monkeypatch.setattr(app_module, "MemosClient", MockMemosClient)

    client = TestClient(create_app(str(app_path), str(models_path)))
    store = client.app.state.store
    workspace_id = client.app.state.config.workspace_id

    # Seed local database
    store.upsert_memo(
        workspace_id=workspace_id,
        memos_uid="memo1",
        memo_type="original",
        status="synced",
    )
    store.upsert_memo(
        workspace_id=workspace_id,
        memos_uid="memo2",
        memo_type="original",
        status="synced",
    )

    # 1. Unauthorized POST should fail
    unauth = client.post("/admin/memos/delete-all")
    assert unauth.status_code == 401

    # 2. Authorized POST should succeed
    response = client.post(
        "/admin/memos/delete-all",
        headers={"Authorization": "Bearer admin-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "deleted 3 memos" in data["message"]

    assert list_called == [(100, None), (100, "page-2")]
    assert sorted(delete_called) == ["memo1", "memo2", "memo3"]

    # Verify that database was cleared for workspace
    with store.connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM memos WHERE workspace_id = ?", (workspace_id,)).fetchone()[0]
        assert count == 0


def test_admin_tag_summary_with_prompt_override(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "prompts.yaml", prompts_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")

    class FakeMemosClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, *, page_size, page_token=None, filter_text=None):
            return {
                "memos": [
                    {
                        "name": "memos/source1",
                        "createTime": "2026-05-21T03:00:00Z",
                        "content": "个人 AI 知识库推进记录 #项目/个人AI知识库",
                        "tags": ["项目/个人AI知识库"],
                    }
                ]
            }

        async def create_memo(self, content):
            return {"name": "memos/summary1", "content": content}

        async def upsert_memo_reference_relation(self, *args, **kwargs):
            pass

    class FakeLLMClient:
        seen_prompt_template = None

        def __init__(self, *args, **kwargs):
            pass

        async def summarize_tag(self, *, tag, memos_markdown, memo_count, prompt_template):
            FakeLLMClient.seen_prompt_template = prompt_template
            return "## Override Summary"

    monkeypatch.setattr("memosima.api.app.MemosClient", FakeMemosClient)
    monkeypatch.setattr("memosima.api.app.OpenAICompatibleClient", FakeLLMClient)

    client = TestClient(create_app(str(app_path), str(models_path)))
    response = client.post(
        "/admin/tag-summaries",
        headers={"Authorization": "Bearer admin-token"},
        json={
            "tag": "#项目/个人AI知识库",
            "limit": 20,
            "system_prompt_override": "System Override Text",
            "user_prompt_override": "User Override Text"
        },
    )

    assert response.status_code == 200
    assert FakeLLMClient.seen_prompt_template is not None
    assert FakeLLMClient.seen_prompt_template.system == "System Override Text"
    assert FakeLLMClient.seen_prompt_template.user == "User Override Text"


