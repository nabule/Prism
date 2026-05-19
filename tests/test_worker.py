from __future__ import annotations

import pytest

from memosima.core.config import AppConfig
from memosima.db.store import Store
from memosima.worker.runner import Worker

from helpers import app_config_text, taxonomy_config_text, write_yaml


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

        def __init__(self, *args, **kwargs):
            pass

        async def get_memo(self, memo_uid):
            return {
                "name": f"memos/{memo_uid}",
                "content": "个人 AI 知识库开发记录 #AI知识库 #项目/新方向",
            }

        async def create_memo(self, content):
            self.created_memos.append(content)
            return {"name": "memos/summary123", "content": content}

        async def create_comment(self, memo_uid, content):
            raise AssertionError("probe comment is disabled")

    monkeypatch.setattr("memosima.worker.runner.MemosClient", FakeClient)

    processed = await Worker(config, store).run_once()

    assert processed is True
    jobs = store.list_jobs()
    assert jobs[0].status == "succeeded"
    assert jobs[0].result["memo_uid"] == "abc123"
    assert jobs[0].result["ai_summary_memo_uid"] == "summary123"
    assert jobs[0].result["comment_created"] is False
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
