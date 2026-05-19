from __future__ import annotations

from memosima.api.webhooks import build_idempotency_key, extract_memo_uid


def test_extract_memo_uid_from_nested_memo_name():
    payload = {"type": "MEMO_CREATED", "memo": {"name": "memos/abc123"}}

    assert extract_memo_uid(payload) == "abc123"


def test_idempotency_key_prefers_event_memo_and_version():
    payload = {
        "type": "MEMO_UPDATED",
        "memo": {"name": "memos/abc123", "updateTime": "2026-05-19T10:00:00Z"},
    }

    assert build_idempotency_key(payload) == "MEMO_UPDATED:abc123:2026-05-19T10:00:00Z"


def test_idempotency_key_uses_stable_hash_without_version():
    payload = {"memo": {"name": "memos/abc123", "content": "hello"}}

    assert build_idempotency_key(payload) == build_idempotency_key(
        {"memo": {"content": "hello", "name": "memos/abc123"}}
    )

