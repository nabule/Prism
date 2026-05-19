from __future__ import annotations

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
