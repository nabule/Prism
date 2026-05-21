from __future__ import annotations

from fastapi.testclient import TestClient

from memosima.api.app import create_app

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
    assert updated.json()["system"] == "新的系统提示 {active_tags}"
    assert listed_again.json()["organize_memo"]["user"] == "新的用户提示 {content}"
    assert "测试标签总结系统提示词" in listed_again.json()["tag_summary"]["system"]


def test_admin_tag_summary_prompt_can_be_updated(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "prompts.yaml", prompts_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    client = TestClient(create_app(str(app_path), str(models_path)))
    updated = client.put(
        "/admin/prompts/tag-summary",
        headers={"Authorization": "Bearer admin-token"},
        json={"system": "标签总结系统", "user": "标签总结用户 {tag} {memos_markdown}"},
    )
    listed = client.get("/admin/prompts", headers={"Authorization": "Bearer admin-token"})

    assert updated.status_code == 200
    assert updated.json()["system"] == "标签总结系统"
    assert listed.json()["tag_summary"]["user"] == "标签总结用户 {tag} {memos_markdown}"


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
    assert "/admin/prompts" in response.text
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
