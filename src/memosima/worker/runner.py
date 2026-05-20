from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os

from memosima.core.attachments import (
    ParsedAttachment,
    SkippedAttachment,
    extract_attachment_resources,
    parse_text_attachment,
)
from memosima.core.config import AppConfig, ModelsConfig
from memosima.core.prompts import PromptTemplate, load_prompts_or_default
from memosima.core.summary import build_summary_memo_content
from memosima.core.taxonomy import OrganizationPlan, TagCandidate, TaxonomyConfig
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

        attachment_results = await self._process_attachments(
            client=client,
            workspace_id=job.workspace_id,
            memo_uid=memo_uid,
            memo=memo,
        )
        if organization_plan.needs_clarification:
            comment = _clarification_comment(organization_plan.clarification_reason)
            await client.create_comment(memo_uid, comment)
            return {
                "status": "waiting_user",
                "memo_uid": memo_uid,
                "content_hash": content_hash,
                "ai_plan": organization_plan.to_dict(),
                "attachments": attachment_results,
                "clarification_comment_created": True,
                "clarification_comment": comment,
            }
        llm_draft = await self._build_llm_draft(
            job=job,
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
                "attachments": attachment_results,
                "clarification_comment_created": True,
                "clarification_comment": comment,
            }
        if llm_draft:
            organization_plan = self._merge_llm_tags(
                taxonomy=taxonomy,
                local_plan=organization_plan,
                llm_draft=llm_draft,
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
        await client.upsert_memo_reference_relation(
            source_memo_uid=memo_uid,
            related_memo_uid=summary_memo_uid,
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
            "attachments": attachment_results,
            "comment_created": comment_created,
        }

    async def _process_attachments(
        self,
        *,
        client: MemosClient,
        workspace_id: str,
        memo_uid: str,
        memo: dict[str, object],
    ) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for resource in extract_attachment_resources(memo):
            try:
                data = await client.download_resource(resource.name)
                parsed = parse_text_attachment(
                    resource=resource,
                    data=data,
                    max_bytes=self.config.max_attachment_bytes,
                    allowed_extensions=self.config.allowed_parse_extensions,
                )
                if isinstance(parsed, ParsedAttachment):
                    artifact = self.store.upsert_artifact(
                        workspace_id=workspace_id,
                        memo_uid=memo_uid,
                        resource_uid=resource.name,
                        kind=parsed.kind,
                        content_markdown=parsed.content_markdown,
                        metadata=parsed.metadata,
                    )
                    results.append(
                        {
                            "resource": resource.name,
                            "status": "parsed",
                            "artifact_id": artifact.id,
                            "kind": artifact.kind,
                        }
                    )
                elif isinstance(parsed, SkippedAttachment):
                    results.append(
                        {
                            "resource": resource.name,
                            "status": "skipped",
                            "reason": parsed.reason,
                        }
                    )
            except Exception as exc:
                LOGGER.warning("Attachment parse failed for memo %s resource %s: %s", memo_uid, resource.name, exc)
                results.append(
                    {
                        "resource": resource.name,
                        "status": "failed",
                        "reason": str(exc),
                    }
                )
        return results

    async def _build_llm_draft(
        self,
        *,
        job: Job,
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
            prompt_template=self._load_prompt_template(job),
        )

    def _load_prompt_template(self, job: Job) -> PromptTemplate:
        override = job.payload.get("llm_prompt_override")
        if isinstance(override, dict):
            system = str(override.get("system", "")).strip()
            user = str(override.get("user", "")).strip()
            if system and user:
                return PromptTemplate(system=system, user=user)
        return load_prompts_or_default(self.config.prompts_path).organize_memo

    def _merge_llm_tags(
        self,
        *,
        taxonomy: TaxonomyConfig,
        local_plan: OrganizationPlan,
        llm_draft: LLMOrganizationDraft,
    ) -> OrganizationPlan:
        active_tags = list(local_plan.active_tags)
        candidates = list(local_plan.candidate_tags)
        disabled_tags = list(local_plan.disabled_tags)
        active_tag_paths = set(taxonomy.active_tag_paths)
        disabled_tag_paths = set(taxonomy.disabled)
        candidate_paths = {candidate.path for candidate in candidates}

        def add_candidate(path: str, reason: str, confidence: float) -> None:
            nonlocal candidate_paths
            if path in candidate_paths or path in active_tag_paths or path.startswith("#系统/"):
                return
            candidates.append(
                TagCandidate(
                    path=path,
                    parent_path=taxonomy.parent_tag(path),
                    reason=reason,
                    similar_existing_tags=taxonomy.similar_tags(path),
                    confidence=confidence,
                )
            )
            candidate_paths.add(path)

        for raw_tag in llm_draft.active_tags:
            try:
                tag = taxonomy.normalize_tag(raw_tag)
            except Exception:
                continue
            tag = taxonomy.aliases.get(tag, tag)
            if tag in disabled_tag_paths:
                disabled_tags.append(tag)
            elif tag in active_tag_paths:
                active_tags.append(tag)
            elif not tag.startswith("#系统/"):
                add_candidate(tag, "AI suggested this tag from memo content but it is not approved", 0.6)

        for llm_candidate in llm_draft.candidate_tags:
            try:
                tag = taxonomy.normalize_tag(llm_candidate.path)
            except Exception:
                continue
            tag = taxonomy.aliases.get(tag, tag)
            if tag in disabled_tag_paths:
                disabled_tags.append(tag)
            elif tag in active_tag_paths:
                active_tags.append(tag)
            else:
                add_candidate(tag, llm_candidate.reason, llm_candidate.confidence)

        system_tags = list(local_plan.system_tags)
        if candidates:
            candidate_system_tag = taxonomy.system_tags.get("tag_candidate", "#系统/标签待审核")
            system_tags.append(candidate_system_tag)

        return OrganizationPlan(
            system_tags=tuple(_dedupe(system_tags)),
            active_tags=tuple(_dedupe(active_tags)),
            candidate_tags=tuple(candidates),
            disabled_tags=tuple(_dedupe(disabled_tags)),
            needs_clarification=local_plan.needs_clarification,
            clarification_reason=local_plan.clarification_reason,
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


def _dedupe(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


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
