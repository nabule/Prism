from __future__ import annotations

import argparse
import asyncio
import json

from memosima.core.config import AppConfig
from memosima.memos.client import MemosClient


async def run_probe(
    *,
    config_path: str,
    memo_uid: str | None,
    create_comment: bool,
) -> dict[str, object]:
    config = AppConfig.load(config_path)
    if not config.memos_base_url or not config.memos_api_token:
        raise RuntimeError("MEMOS_BASE_URL and MEMOS_API_TOKEN must be configured")

    client = MemosClient(
        base_url=config.memos_base_url,
        api_token=config.memos_api_token,
        timeout_seconds=config.memos_timeout_seconds,
    )
    result: dict[str, object] = {
        "base_url": config.memos_base_url,
        "health_ok": False,
        "memo_read_ok": False,
        "comment_created": False,
    }

    try:
        result["health"] = await client.get_health()
        result["health_ok"] = True
    except Exception as exc:
        result["health_error"] = str(exc)

    if memo_uid:
        memo = await client.get_memo(memo_uid)
        result["memo"] = _summarize_memo(memo)
        result["memo_read_ok"] = True
        if create_comment:
            comment = await client.create_comment(
                memo_uid,
                "Memosima P0 API 探针评论：Sidecar 已完成真实 API 读写验证。",
            )
            result["comment"] = _summarize_memo(comment)
            result["comment_created"] = True

    return result


def _summarize_memo(value: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for key in ("name", "uid", "id", "displayTime", "createTime", "updateTime"):
        if key in value:
            summary[key] = value[key]
    content = value.get("content")
    if isinstance(content, str):
        summary["content_preview"] = content[:80]
    return summary or {"keys": sorted(value.keys())}


async def _run(args: argparse.Namespace) -> None:
    result = await run_probe(
        config_path=args.config,
        memo_uid=args.memo_uid,
        create_comment=args.create_comment,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe a real Memos API instance.")
    parser.add_argument("--config", default="config/app.yaml")
    parser.add_argument("--memo-uid")
    parser.add_argument("--create-comment", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
