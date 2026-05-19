from __future__ import annotations

import hashlib
import json
from typing import Any


def extract_memo_uid(payload: dict[str, Any]) -> str | None:
    candidates: list[Any] = [
        payload.get("memoUid"),
        payload.get("memo_uid"),
        payload.get("uid"),
        payload.get("id"),
        payload.get("name"),
    ]
    memo = payload.get("memo")
    if isinstance(memo, dict):
        candidates.extend(
            [
                memo.get("uid"),
                memo.get("id"),
                memo.get("name"),
            ]
        )
    resource = payload.get("resource")
    if isinstance(resource, dict):
        candidates.extend([resource.get("memoUid"), resource.get("memo_uid")])

    for candidate in candidates:
        uid = _normalize_uid(candidate)
        if uid:
            return uid
    return None


def build_idempotency_key(payload: dict[str, Any]) -> str:
    event_type = str(
        payload.get("type")
        or payload.get("event")
        or payload.get("activity")
        or payload.get("activityType")
        or "memos.webhook"
    )
    memo_uid = extract_memo_uid(payload) or "unknown"
    version = _extract_version(payload)
    if version:
        return f"{event_type}:{memo_uid}:{version}"

    stable_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(stable_json.encode("utf-8")).hexdigest()
    return f"{event_type}:{memo_uid}:{digest}"


def _extract_version(payload: dict[str, Any]) -> str | None:
    candidates: list[Any] = [
        payload.get("updatedTs"),
        payload.get("updated_at"),
        payload.get("updateTime"),
        payload.get("version"),
    ]
    memo = payload.get("memo")
    if isinstance(memo, dict):
        candidates.extend(
            [
                memo.get("updatedTs"),
                memo.get("updated_at"),
                memo.get("updateTime"),
                memo.get("version"),
            ]
        )
    for candidate in candidates:
        if candidate not in (None, ""):
            return str(candidate)
    return None


def _normalize_uid(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.startswith("memos/"):
        return text.split("/", maxsplit=1)[1]
    return text

