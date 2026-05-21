from __future__ import annotations

import pytest

from memosima.core.config import AppConfig, ModelsConfig
from memosima.db.store import Store
from memosima.llm.provider import LLMOrganizationDraft
from memosima.worker.runner import Worker

from helpers import app_config_text, models_config_text, taxonomy_config_text, write_yaml


@pytest.mark.asyncio
async def test_worker_processes_memo_with_mock_client(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    config = AppConfig.load(app_path)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace("default")
    store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:abc123",
        payload={"memo_uid": "abc123"},
    )

    class FakeClient:
        created_memos: list[str] = []
        relations: list[tuple[str, str]] = []

        def __init__(self, *args, **kwargs):
            pass

        async def get_memo(self, memo_uid):
            return {
                "name": f"memos/{memo_uid}",
                "content": "个人 AI 知识库开发记录 #AI知识库 #项目/新方向",
                "resources": [
                    {
                        "name": "resources/note1",
                        "filename": "note.txt",
                        "contentType": "text/plain",
                        "size": 12,
                    }
                ],
            }

        async def create_memo(self, content):
            self.created_memos.append(content)
            return {"name": "memos/summary123", "content": content}

        async def create_comment(self, memo_uid, content):
            raise AssertionError("probe comment is disabled")

        async def download_resource(self, resource_name):
            assert resource_name == "resources/note1"
            return b"attachment text\n"

        async def upsert_memo_reference_relation(self, *, source_memo_uid, related_memo_uid):
            self.relations.append((source_memo_uid, related_memo_uid))
            return {}

    monkeypatch.setattr("memosima.worker.runner.MemosClient", FakeClient)

    processed = await Worker(config, store).run_once()

    assert processed is True
    jobs = store.list_jobs()
    assert jobs[0].status == "succeeded"
    assert jobs[0].result["memo_uid"] == "abc123"
    assert jobs[0].result["ai_summary_memo_uid"] == "summary123"
    assert jobs[0].result["comment_created"] is False
    assert jobs[0].result["attachments"][0]["status"] == "parsed"
    assert jobs[0].result["ai_plan"]["active_tags"] == ["#项目/个人AI知识库"]
    assert jobs[0].result["ai_plan"]["candidate_tags"][0]["path"] == "#项目/新方向"
    assert len(FakeClient.created_memos) == 1
    assert "#系统/AI整理" in FakeClient.created_memos[0]
    assert "#项目/个人AI知识库" in FakeClient.created_memos[0]
    assert "#项目/新方向" in FakeClient.created_memos[0]
    assert "来源 memo：memos/abc123" in FakeClient.created_memos[0]
    candidates = store.list_tag_candidates(workspace_id="default")
    assert len(candidates) == 1
    assert candidates[0].path == "#项目/新方向"
    assert candidates[0].source_memo_uid == "abc123"
    summaries = store.list_memos(
        workspace_id="default",
        memo_type="ai_summary",
        source_memo_uid="abc123",
    )
    assert len(summaries) == 1
    assert summaries[0].memos_uid == "summary123"
    assert summaries[0].status == "created"
    assert FakeClient.relations == [("abc123", "summary123")]
    artifacts = store.list_artifacts(
        workspace_id="default",
        memo_uid="abc123",
        kind="attachment_text",
    )
    assert len(artifacts) == 1
    assert artifacts[0].resource_uid == "resources/note1"
    assert artifacts[0].content_markdown == "attachment text\n"


@pytest.mark.asyncio
async def test_worker_waits_for_user_when_memo_needs_clarification(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    config = AppConfig.load(app_path)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace("default")
    store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:short",
        payload={"memo_uid": "short"},
    )

    class FakeClient:
        created_memos: list[str] = []
        comments: list[tuple[str, str]] = []

        def __init__(self, *args, **kwargs):
            pass

        async def get_memo(self, memo_uid):
            return {"name": f"memos/{memo_uid}", "content": "啥？"}

        async def create_memo(self, content):
            self.created_memos.append(content)
            raise AssertionError("clarification jobs must not create summary memos")

        async def create_comment(self, memo_uid, content):
            self.comments.append((memo_uid, content))
            return {"name": f"memos/{memo_uid}/comments/1", "content": content}

        async def download_resource(self, resource_name):
            raise AssertionError("short memo has no resources")

    monkeypatch.setattr("memosima.worker.runner.MemosClient", FakeClient)

    processed = await Worker(config, store).run_once()

    assert processed is True
    jobs = store.list_jobs()
    assert jobs[0].status == "waiting_user"
    assert jobs[0].result["status"] == "waiting_user"
    assert jobs[0].result["memo_uid"] == "short"
    assert jobs[0].result["clarification_comment_created"] is True
    assert jobs[0].result["ai_plan"]["needs_clarification"] is True
    assert FakeClient.created_memos == []
    assert len(FakeClient.comments) == 1
    assert FakeClient.comments[0][0] == "short"
    assert "需要补充信息" in FakeClient.comments[0][1]
    assert store.list_memos(workspace_id="default", memo_type="ai_summary") == []


@pytest.mark.asyncio
async def test_worker_uses_llm_draft_when_model_key_is_configured(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    config = AppConfig.load(app_path)
    models = ModelsConfig.load(models_path)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace("default")
    store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:llm",
        payload={"memo_uid": "llm"},
    )

    class FakeMemosClient:
        created_memos: list[str] = []
        relations: list[tuple[str, str]] = []

        def __init__(self, *args, **kwargs):
            pass

        async def get_memo(self, memo_uid):
            return {"name": f"memos/{memo_uid}", "content": "整理个人 AI 知识库开发记录 #AI知识库"}

        async def create_memo(self, content):
            self.created_memos.append(content)
            return {"name": "memos/summary-llm", "content": content}

        async def create_comment(self, memo_uid, content):
            raise AssertionError("clear LLM jobs must not create comments")

        async def download_resource(self, resource_name):
            raise AssertionError("LLM memo has no resources")

        async def upsert_memo_reference_relation(self, *, source_memo_uid, related_memo_uid):
            self.relations.append((source_memo_uid, related_memo_uid))
            return {}

    class FakeLLMClient:
        def __init__(self, *args, **kwargs):
            pass

        async def organize_memo(self, *, content, taxonomy, local_plan, prompt_template):
            return LLMOrganizationDraft(
                title="整理记录",
                summary="LLM 结构化摘要",
                key_points=["关键点一"],
                todos=["后续任务一"],
                active_tags=["#项目/个人AI知识库"],
                needs_clarification=False,
            )

    monkeypatch.setattr("memosima.worker.runner.MemosClient", FakeMemosClient)
    monkeypatch.setattr("memosima.worker.runner.OpenAICompatibleClient", FakeLLMClient)

    processed = await Worker(config, store, models).run_once()

    assert processed is True
    jobs = store.list_jobs()
    assert jobs[0].status == "succeeded"
    assert jobs[0].result["ai_source"] == "llm"
    assert jobs[0].result["ai_summary_memo_uid"] == "summary-llm"
    assert len(FakeMemosClient.created_memos) == 1
    assert FakeMemosClient.relations == [("llm", "summary-llm")]
    assert "LLM 结构化摘要" in FakeMemosClient.created_memos[0]
    assert "- 关键点一" in FakeMemosClient.created_memos[0]
    assert "- 后续任务一" in FakeMemosClient.created_memos[0]
    assert "#项目/个人AI知识库" in FakeMemosClient.created_memos[0]


@pytest.mark.asyncio
async def test_worker_uses_temporary_prompt_override_from_job_payload(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    config = AppConfig.load(app_path)
    models = ModelsConfig.load(models_path)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace("default")
    store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:prompt-override",
        payload={
            "memo_uid": "prompt-override",
            "llm_prompt_override": {
                "system": "临时系统提示 {active_tags}",
                "user": "临时用户提示 {content}",
            },
        },
    )

    class FakeMemosClient:
        created_memos: list[str] = []

        def __init__(self, *args, **kwargs):
            pass

        async def get_memo(self, memo_uid):
            return {"name": f"memos/{memo_uid}", "content": "整理个人 AI 知识库开发记录"}

        async def create_memo(self, content):
            self.created_memos.append(content)
            return {"name": "memos/summary-prompt-override", "content": content}

        async def create_comment(self, memo_uid, content):
            raise AssertionError("clear prompt override jobs must not create comments")

        async def download_resource(self, resource_name):
            raise AssertionError("prompt override memo has no resources")

        async def upsert_memo_reference_relation(self, *, source_memo_uid, related_memo_uid):
            return {}

    class FakeLLMClient:
        seen_prompt_system = ""
        seen_prompt_user = ""

        def __init__(self, *args, **kwargs):
            pass

        async def organize_memo(self, *, content, taxonomy, local_plan, prompt_template):
            rendered = prompt_template.render(
                {
                    "active_tags": "\n".join(f"- {tag}" for tag in taxonomy.active_tag_paths),
                    "local_plan_json": "{}",
                    "content": content,
                }
            )
            FakeLLMClient.seen_prompt_system = rendered.system
            FakeLLMClient.seen_prompt_user = rendered.user
            return LLMOrganizationDraft(
                title="临时提示整理",
                summary="使用临时提示词",
                needs_clarification=False,
            )

    monkeypatch.setattr("memosima.worker.runner.MemosClient", FakeMemosClient)
    monkeypatch.setattr("memosima.worker.runner.OpenAICompatibleClient", FakeLLMClient)

    processed = await Worker(config, store, models).run_once()

    assert processed is True
    assert FakeLLMClient.seen_prompt_system.startswith("临时系统提示")
    assert FakeLLMClient.seen_prompt_user == "临时用户提示 整理个人 AI 知识库开发记录"


@pytest.mark.asyncio
async def test_worker_merges_ai_generated_tags_from_body(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    config = AppConfig.load(app_path)
    models = ModelsConfig.load(models_path)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace("default")
    store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:ai-tags",
        payload={"memo_uid": "ai-tags"},
    )

    class FakeMemosClient:
        created_memos: list[str] = []
        relations: list[tuple[str, str]] = []

        def __init__(self, *args, **kwargs):
            pass

        async def get_memo(self, memo_uid):
            return {"name": f"memos/{memo_uid}", "content": "今天继续整理个人 AI 知识库，准备新增调试后台"}

        async def create_memo(self, content):
            self.created_memos.append(content)
            return {"name": "memos/summary-ai-tags", "content": content}

        async def create_comment(self, memo_uid, content):
            raise AssertionError("clear AI tag jobs must not create comments")

        async def download_resource(self, resource_name):
            raise AssertionError("AI tag memo has no resources")

        async def upsert_memo_reference_relation(self, *, source_memo_uid, related_memo_uid):
            self.relations.append((source_memo_uid, related_memo_uid))
            return {}

    class FakeLLMClient:
        def __init__(self, *args, **kwargs):
            pass

        async def organize_memo(self, *, content, taxonomy, local_plan, prompt_template):
            return LLMOrganizationDraft(
                title="AI 标签整理",
                summary="AI 从正文识别知识库开发主题",
                key_points=[],
                todos=[],
                active_tags=["#项目/个人AI知识库", "#项目/未知正式标签"],
                candidate_tags=[
                    {
                        "path": "#项目/调试后台",
                        "reason": "正文提到新增调试后台",
                        "confidence": 0.9,
                    },
                    {
                        "path": "#杂项",
                        "reason": "禁用标签应被记录为 disabled",
                        "confidence": 0.8,
                    },
                ],
                needs_clarification=False,
            )

    monkeypatch.setattr("memosima.worker.runner.MemosClient", FakeMemosClient)
    monkeypatch.setattr("memosima.worker.runner.OpenAICompatibleClient", FakeLLMClient)

    processed = await Worker(config, store, models).run_once()

    assert processed is True
    job = store.list_jobs()[0]
    assert job.status == "succeeded"
    assert job.result["ai_source"] == "llm"
    assert job.result["ai_plan"]["active_tags"] == ["#项目/个人AI知识库"]
    candidate_paths = [candidate["path"] for candidate in job.result["ai_plan"]["candidate_tags"]]
    assert candidate_paths == ["#项目/未知正式标签", "#项目/调试后台"]
    assert job.result["ai_plan"]["disabled_tags"] == ["#杂项"]
    candidates = store.list_tag_candidates(workspace_id="default", status="candidate")
    assert [candidate.path for candidate in candidates] == ["#项目/调试后台", "#项目/未知正式标签"]
    assert candidates[0].reason == "正文提到新增调试后台"
    assert candidates[0].confidence == 0.9
    assert "#项目/个人AI知识库" in FakeMemosClient.created_memos[0]
    assert "#项目/调试后台" in FakeMemosClient.created_memos[0]
    assert "#项目/未知正式标签" in FakeMemosClient.created_memos[0]
    assert "#杂项" in FakeMemosClient.created_memos[0]
    assert FakeMemosClient.relations == [("ai-tags", "summary-ai-tags")]


@pytest.mark.asyncio
async def test_worker_uses_approved_business_tags_from_store(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    config = AppConfig.load(app_path)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace("default")
    candidate = store.upsert_tag_candidate(
        workspace_id="default",
        path="#项目/新方向",
        parent_path="#项目",
        reason="memo contains a tag outside the approved taxonomy",
    )
    store.review_tag_candidate(candidate_id=candidate.id, status="approved")
    store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:approved-tag",
        payload={"memo_uid": "approved-tag"},
    )

    class FakeClient:
        created_memos: list[str] = []
        relations: list[tuple[str, str]] = []

        def __init__(self, *args, **kwargs):
            pass

        async def get_memo(self, memo_uid):
            return {"name": f"memos/{memo_uid}", "content": "已审核新方向推进记录 #项目/新方向"}

        async def create_memo(self, content):
            self.created_memos.append(content)
            return {"name": "memos/summary-approved-tag", "content": content}

        async def create_comment(self, memo_uid, content):
            raise AssertionError("clear jobs must not create comments")

        async def download_resource(self, resource_name):
            raise AssertionError("approved tag memo has no resources")

        async def upsert_memo_reference_relation(self, *, source_memo_uid, related_memo_uid):
            self.relations.append((source_memo_uid, related_memo_uid))
            return {}

    monkeypatch.setattr("memosima.worker.runner.MemosClient", FakeClient)

    processed = await Worker(config, store).run_once()

    assert processed is True
    job = store.list_jobs()[0]
    assert job.status == "succeeded"
    assert job.result["ai_plan"]["active_tags"] == ["#项目/新方向"]
    assert job.result["ai_plan"]["candidate_tags"] == []
    assert store.list_tag_candidates(workspace_id="default", status="candidate") == []
    assert "#项目/新方向" in FakeClient.created_memos[0]
    assert FakeClient.relations == [("approved-tag", "summary-approved-tag")]


@pytest.mark.asyncio
async def test_worker_polling_enqueues_new_original_memos(tmp_path, monkeypatch):
    app_path = write_yaml(
        tmp_path / "app.yaml",
        app_config_text(tmp_path / "sidecar.db").replace("ingestion_mode: webhook", "ingestion_mode: poll"),
    )
    write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    config = AppConfig.load(app_path)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace("default")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, *, page_size, page_token=None, filter_text=None):
            return {
                "memos": [
                    {
                        "name": "memos/new-original",
                        "updateTime": "2026-05-21T03:20:00Z",
                        "content": "新的原始 memo",
                        "tags": [],
                    },
                    {
                        "name": "memos/summary",
                        "updateTime": "2026-05-21T03:19:00Z",
                        "content": "#系统/AI整理\n\nAI memo",
                        "tags": ["系统/AI整理"],
                    },
                    {
                        "name": "memos/tag-summary",
                        "updateTime": "2026-05-21T03:18:00Z",
                        "content": "#系统/标签总结 #项目/个人AI知识库\n\n标签整体总结",
                        "tags": ["系统/标签总结", "项目/个人AI知识库"],
                    },
                ]
            }

    monkeypatch.setattr("memosima.worker.runner.MemosClient", FakeClient)

    worker = Worker(config, store)

    assert await worker._poll_memos_once() is True
    jobs = store.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].status == "pending"
    assert jobs[0].payload["memo_uid"] == "new-original"
    assert jobs[0].idempotency_key == "memos.poll:new-original:2026-05-21T03:20:00Z"

    assert await worker._poll_memos_once() is False
    assert len(store.list_jobs()) == 1


@pytest.mark.asyncio
async def test_worker_polling_skips_already_synced_memos(tmp_path, monkeypatch):
    app_path = write_yaml(
        tmp_path / "app.yaml",
        app_config_text(tmp_path / "sidecar.db").replace("ingestion_mode: webhook", "ingestion_mode: poll"),
    )
    write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    config = AppConfig.load(app_path)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace("default")
    store.upsert_memo(
        workspace_id="default",
        memos_uid="already-synced",
        memo_type="original",
        status="synced",
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, *, page_size, page_token=None, filter_text=None):
            return {
                "memos": [
                    {
                        "name": "memos/already-synced",
                        "updateTime": "2026-05-21T03:20:00Z",
                        "content": "已处理 memo",
                        "tags": [],
                    }
                ]
            }

    monkeypatch.setattr("memosima.worker.runner.MemosClient", FakeClient)

    assert await Worker(config, store)._poll_memos_once() is False
    assert store.list_jobs() == []
