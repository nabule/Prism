from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging

from memosima.core.config import AppConfig
from memosima.core.taxonomy import TaxonomyConfig
from memosima.db.store import Job, Store
from memosima.memos.client import MemosClient

LOGGER = logging.getLogger(__name__)


class Worker:
    def __init__(self, config: AppConfig, store: Store):
        self.config = config
        self.store = store

    async def run_once(self) -> bool:
        job = self.store.claim_next_job()
        if job is None:
            return False
        try:
            result = await self.handle_job(job)
            self.store.mark_job_succeeded(job.id, result)
            return True
        except Exception as exc:
            LOGGER.exception("Job failed: %s", job.id)
            self.store.mark_job_failed(job.id, str(exc), self.config.worker_max_attempts)
            return True

    async def run_forever(self) -> None:
        while True:
            processed = await self.run_once()
            if not processed:
                await asyncio.sleep(self.config.worker_poll_interval_seconds)

    async def handle_job(self, job: Job) -> dict[str, object]:
        if job.type != "process_memo":
            raise ValueError(f"Unsupported job type: {job.type}")
        return await self._process_memo(job)

    async def _process_memo(self, job: Job) -> dict[str, object]:
        memo_uid = job.payload.get("memo_uid")
        if not isinstance(memo_uid, str) or not memo_uid:
            raise ValueError("process_memo job payload is missing memo_uid")
        if not self.config.memos_base_url or not self.config.memos_api_token:
            raise RuntimeError("Memos base URL or API token is not configured")

        client = MemosClient(
            base_url=self.config.memos_base_url,
            api_token=self.config.memos_api_token,
            timeout_seconds=self.config.memos_timeout_seconds,
        )
        memo = await client.get_memo(memo_uid)
        content_hash = _memo_hash(memo)
        taxonomy = TaxonomyConfig.load(self.config.taxonomy_path)
        content = memo.get("content")
        organization_plan = taxonomy.build_organization_plan(content if isinstance(content, str) else "")
        self.store.upsert_memo(
            workspace_id=job.workspace_id,
            memos_uid=memo_uid,
            memo_type="original",
            status="synced",
            content_hash=content_hash,
        )

        comment_created = False
        if self.config.worker_create_probe_comment:
            await client.create_comment(memo_uid, "Memosima P0 探针评论：Sidecar 已读取此 memo。")
            comment_created = True

        return {
            "memo_uid": memo_uid,
            "content_hash": content_hash,
            "ai_plan": organization_plan.to_dict(),
            "comment_created": comment_created,
        }


def _memo_hash(memo: dict[str, object]) -> str:
    payload = json.dumps(memo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _run(args: argparse.Namespace) -> None:
    config = AppConfig.load(args.config)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace(config.workspace_id)
    worker = Worker(config, store)
    if args.once:
        await worker.run_once()
    else:
        await worker.run_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/app.yaml")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level.upper())
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
