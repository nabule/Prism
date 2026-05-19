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

