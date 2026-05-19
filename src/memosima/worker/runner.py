from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os

from memosima.core.config import AppConfig, ModelsConfig
from memosima.core.summary import build_summary_memo_content
from memosima.core.taxonomy import OrganizationPlan, TaxonomyConfig
from memosima.db.store import Job, Store
from memosima.llm.provider import LLMOrganizationDraft, OpenAICompatibleClient
from memosima.memos.client import MemosClient

LOGGER = logging.getLogger(__name__)


class Worker:
    def __init__(self, config: AppConfig, store: Store, models_config: ModelsConfig | None = None):
        self.config = config
        self.store = store
        self.models_config = models_config

    async def run_once(self) -> bool:
        job = self.store.claim_next_job()
        if job is None:
            return False
        try:
            result = await self.handle_job(job)
            if result.get("status") == "waiting_user":
                self.store.mark_job_waiting_user(job.id, result)
            else:
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
        taxonomy = self._load_taxonomy(job.workspace_id)
        content = memo.get("content")
        source_content = content if isinstance(content, str) else ""
        organization_plan = taxonomy.build_organization_plan(source_content)
        self.store.upsert_memo(
            workspace_id=job.workspace_id,
            memos_uid=memo_uid,
            memo_type="original",
            status="synced",
            content_hash=content_hash,
        )
        for candidate in organization_plan.candidate_tags:
            self.store.upsert_tag_candidate(
                workspace_id=job.workspace_id,
                path=candidate.path,
                parent_path=candidate.parent_path,
                reason=candidate.reason,
                source_memo_uid=memo_uid,
                similar_tags=list(candidate.similar_existing_tags),
                confidence=candidate.confidence,
            )

        if organization_plan.needs_clarification:
            comment = _clarification_comment(organization_plan.clarification_reason)
            await client.create_comment(memo_uid, comment)
            return {
                "status": "waiting_user",
                "memo_uid": memo_uid,
                "content_hash": content_hash,
                "ai_plan": organization_plan.to_dict(),
                "clarification_comment_created": True,
                "clarification_comment": comment,
            }
        llm_draft = await self._build_llm_draft(
            source_content=source_content,
            taxonomy=taxonomy,
            organization_plan=organization_plan,
        )
        if llm_draft and llm_draft.needs_clarification:
            comment = _clarification_comment(llm_draft.clarification_question)
            await client.create_comment(memo_uid, comment)
            return {
                "status": "waiting_user",
                "memo_uid": memo_uid,
                "content_hash": content_hash,
                "ai_plan": organization_plan.to_dict(),
                "ai_source": "llm",
                "clarification_comment_created": True,
                "clarification_comment": comment,
            }

        summary_content = build_summary_memo_content(
            source_memo_uid=memo_uid,
            source_content=source_content,
            organization_plan=organization_plan,
            taxonomy=taxonomy,
            llm_draft=llm_draft,
        )
        summary_memo = await client.create_memo(summary_content)
        summary_memo_uid = _extract_memo_uid(summary_memo)
        self.store.upsert_memo(
            workspace_id=job.workspace_id,
            memos_uid=summary_memo_uid,
            memo_type="ai_summary",
            source_memo_uid=memo_uid,
            status="created",
            content_hash=_memo_hash(summary_memo),
        )

        comment_created = False
        if self.config.worker_create_probe_comment:
            await client.create_comment(memo_uid, "Memosima P0 探针评论：Sidecar 已读取此 memo。")
            comment_created = True

        return {
            "memo_uid": memo_uid,
            "content_hash": content_hash,
            "ai_summary_memo_uid": summary_memo_uid,
            "ai_plan": organization_plan.to_dict(),
            "ai_source": "llm" if llm_draft else "local",
            "comment_created": comment_created,
        }

    async def _build_llm_draft(
        self,
        *,
        source_content: str,
        taxonomy: TaxonomyConfig,
        organization_plan: OrganizationPlan,
    ) -> LLMOrganizationDraft | None:
        if self.models_config is None:
            return None
        provider = self.models_config.providers[self.models_config.default_provider]
        api_key = os.getenv(provider.api_key_env)
        if not api_key:
            return None
        client = OpenAICompatibleClient(
            provider=provider,
            api_key=api_key,
            timeout_seconds=self.config.memos_timeout_seconds,
        )
        return await client.organize_memo(
            content=source_content,
            taxonomy=taxonomy,
            local_plan=organization_plan,
        )

    def _load_taxonomy(self, workspace_id: str) -> TaxonomyConfig:
        taxonomy = TaxonomyConfig.load(self.config.taxonomy_path)
        approved_tags = [
            tag.path for tag in self.store.list_business_tags(workspace_id=workspace_id, status="active")
        ]
        return taxonomy.with_active_tags(approved_tags)


def _memo_hash(memo: dict[str, object]) -> str:
    payload = json.dumps(memo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_memo_uid(memo: dict[str, object]) -> str:
    name = memo.get("name")
    if not isinstance(name, str) or not name.startswith("memos/"):
        raise ValueError("Created summary memo response is missing name")
    return name.removeprefix("memos/")


def _clarification_comment(reason: str | None) -> str:
    message = reason or "内容需要进一步澄清。"
    return f"Memosima 需要补充信息后再整理：{message}"


async def _run(args: argparse.Namespace) -> None:
    config = AppConfig.load(args.config)
    models = ModelsConfig.load(args.models)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace(config.workspace_id)
    worker = Worker(config, store, models)
    if args.once:
        await worker.run_once()
    else:
        await worker.run_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/app.yaml")
    parser.add_argument("--models", default="config/models.yaml")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level.upper())
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
