from __future__ import annotations

import pytest

from memosima.db.store import Store


def test_create_job_is_idempotent(tmp_path):
    store = Store(tmp_path / "sidecar.db")
    store.migrate()
    store.ensure_workspace("default")

    first, first_created = store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:1",
        payload={"memo_uid": "1"},
    )
    second, second_created = store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:1",
        payload={"memo_uid": "1"},
    )

    assert first.id == second.id
    assert first_created is True
    assert second_created is False
    assert len(store.list_jobs()) == 1


def test_job_claim_fail_and_retry_flow(tmp_path):
    store = Store(tmp_path / "sidecar.db")
    store.migrate()
    store.ensure_workspace("default")
    job, _ = store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:1",
        payload={"memo_uid": "1"},
    )

    claimed = store.claim_next_job()
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "running"

    store.mark_job_failed(job.id, "boom", max_attempts=1)
    failed = store.get_job(job.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.retry_count == 1

    retried = store.retry_job(job.id)
    assert retried is not None
    assert retried.status == "pending"
    assert retried.error is None
    assert retried.retry_count == 0


def test_job_waiting_user_flow_can_be_retried(tmp_path):
    store = Store(tmp_path / "sidecar.db")
    store.migrate()
    store.ensure_workspace("default")
    job, _ = store.create_job(
        workspace_id="default",
        job_type="process_memo",
        idempotency_key="memo:waiting",
        payload={"memo_uid": "waiting"},
    )

    store.mark_job_waiting_user(job.id, {"memo_uid": "waiting", "status": "waiting_user"})

    waiting = store.get_job(job.id)
    assert waiting is not None
    assert waiting.status == "waiting_user"
    assert waiting.result == {"memo_uid": "waiting", "status": "waiting_user"}

    retried = store.retry_job(job.id)
    assert retried is not None
    assert retried.status == "pending"
    assert retried.error is None
    assert retried.retry_count == 0


def test_tag_candidate_upsert_list_and_review_flow(tmp_path):
    store = Store(tmp_path / "sidecar.db")
    store.migrate()
    store.ensure_workspace("default")

    created = store.upsert_tag_candidate(
        workspace_id="default",
        path="#项目/新方向",
        parent_path="#项目",
        reason="memo contains a tag outside the approved taxonomy",
        source_memo_uid="abc123",
        similar_tags=["#项目/个人AI知识库"],
        confidence=0.5,
    )
    updated = store.upsert_tag_candidate(
        workspace_id="default",
        path="#项目/新方向",
        parent_path="#项目",
        reason="updated reason",
        source_memo_uid="def456",
        similar_tags=["#项目/个人AI知识库"],
        confidence=0.7,
    )

    assert created.id == updated.id
    candidates = store.list_tag_candidates(workspace_id="default")
    assert len(candidates) == 1
    assert candidates[0].status == "candidate"
    assert candidates[0].reason == "updated reason"
    assert candidates[0].source_memo_uid == "def456"

    reviewed = store.review_tag_candidate(
        candidate_id=created.id,
        status="approved",
        reviewer_note="纳入正式标签",
    )

    assert reviewed is not None
    assert reviewed.status == "approved"
    assert reviewed.reviewer_note == "纳入正式标签"
    assert store.list_tag_candidates(workspace_id="default", status="candidate") == []
    active_tags = store.list_business_tags(workspace_id="default")
    assert len(active_tags) == 1
    assert active_tags[0].path == "#项目/新方向"
    assert active_tags[0].status == "active"
    assert active_tags[0].source == "candidate_review"


def test_tag_candidate_leaf_is_unique_across_levels(tmp_path):
    store = Store(tmp_path / "sidecar.db")
    store.migrate()
    store.ensure_workspace("default")

    created = store.upsert_tag_candidate(
        workspace_id="default",
        path="#项目/数管",
        parent_path="#项目",
        reason="first candidate",
    )
    duplicate_leaf = store.upsert_tag_candidate(
        workspace_id="default",
        path="#数管",
        reason="same leaf candidate",
    )

    assert duplicate_leaf.id == created.id
    assert store.review_tag_candidate(candidate_id=created.id, status="approved") is not None
    with pytest.raises(ValueError, match="Tag leaf conflicts"):
        store.upsert_tag_candidate(
            workspace_id="default",
            path="#其他/数管",
            parent_path="#其他",
            reason="same leaf as active tag",
        )


def test_memo_records_can_be_listed_by_type_and_source(tmp_path):
    store = Store(tmp_path / "sidecar.db")
    store.migrate()
    store.ensure_workspace("default")

    store.upsert_memo(
        workspace_id="default",
        memos_uid="abc123",
        memo_type="original",
        status="synced",
        content_hash="original-hash",
    )
    store.upsert_memo(
        workspace_id="default",
        memos_uid="summary123",
        memo_type="ai_summary",
        source_memo_uid="abc123",
        status="created",
        content_hash="summary-hash",
    )

    summaries = store.list_memos(
        workspace_id="default",
        memo_type="ai_summary",
        source_memo_uid="abc123",
    )

    assert len(summaries) == 1
    assert summaries[0].memos_uid == "summary123"
    assert summaries[0].source_memo_uid == "abc123"
    assert summaries[0].content_hash == "summary-hash"


def test_artifact_upsert_and_list_flow(tmp_path):
    store = Store(tmp_path / "sidecar.db")
    store.migrate()
    store.ensure_workspace("default")

    created = store.upsert_artifact(
        workspace_id="default",
        memo_uid="abc123",
        resource_uid="resources/file1",
        kind="attachment_text",
        content_markdown="hello\n",
        metadata={"filename": "note.txt"},
    )
    updated = store.upsert_artifact(
        workspace_id="default",
        memo_uid="abc123",
        resource_uid="resources/file1",
        kind="attachment_text",
        content_markdown="updated\n",
        metadata={"filename": "note.txt", "size": 7},
    )

    assert created.id == updated.id
    artifacts = store.list_artifacts(
        workspace_id="default",
        memo_uid="abc123",
        kind="attachment_text",
    )
    assert len(artifacts) == 1
    assert artifacts[0].content_markdown == "updated\n"
    assert artifacts[0].metadata == {"filename": "note.txt", "size": 7}
