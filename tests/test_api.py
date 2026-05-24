from __future__ import annotations

import io
import json
import zipfile

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
            "provider": "",
            "system": "提醒系统 {trigger_tag}",
            "user": "提醒用户 {now} {timezone} {content}",
        },
    )
    listed = client.get("/admin/prompts", headers={"Authorization": "Bearer admin-token"})

    assert tag_updated.status_code == 200
    assert tag_updated.json()["provider"] == "deepseek"
    assert tag_updated.json()["system"] == "标签总结系统"
    assert reminder_updated.status_code == 200
    assert reminder_updated.json()["provider"] == ""
    assert listed.json()["tag_summary"]["user"] == "标签总结用户 {tag} {memos_markdown}"
    assert listed.json()["tag_summary"]["provider"] == "deepseek"
    assert listed.json()["reminder_extraction"]["provider"] == ""
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
