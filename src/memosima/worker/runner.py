from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from memosima.core.attachments import (
    ParsedAttachment,
    SkippedAttachment,
    extract_attachment_resources,
    is_document_attachment,
    parse_text_attachment,
)
from memosima.core.admin_entry import (
    ADMIN_ENTRY_MARKER,
    ADMIN_ENTRY_SEARCH_FILTER,
    build_admin_entry_memo_content,
    build_summary_admin_links,
)
from memosima.core.config import AppConfig, ModelsConfig, ProviderConfig
from memosima.core.document_parsers import create_document_parser
from memosima.core.prompts import PromptTemplate, load_prompts_or_default
from memosima.core.summary import build_summary_memo_content
from memosima.core.taxonomy import OrganizationPlan, TagCandidate, TaxonomyConfig
from memosima.db.store import Job, ReminderRecord, Store, utc_now
from memosima.llm.provider import EmbeddingClient, LLMOrganizationDraft, LLMReminderExtraction, LLMReminderItem, OpenAICompatibleClient
from memosima.memos.client import MemosClient

LOGGER = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        config: AppConfig,
        store: Store,
        models_config: ModelsConfig | None = None,
        models_path: str = "config/models.yaml",
        config_path: str = "config/app.yaml",
    ):
        self.config = config
        self.store = store
        self.models_config = models_config
        self.models_path = models_path
        self.config_path = config_path

    async def run_once(self) -> bool:
        if await self._send_due_reminders_once():
            return True
        job = self.store.claim_next_job()
        if job is None:
            if await self._ensure_admin_entry_memo_once():
                return True
            if await self._poll_memos_once():
                return True
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
            self.config = AppConfig.load(self.config_path)
            if self.models_config is not None:
                self.models_config = ModelsConfig.load(self.models_path)
                
            processed = await self.run_once()
            if not processed:
                await asyncio.sleep(self.config.worker_poll_interval_seconds)

    async def _poll_memos_once(self) -> bool:
        if self.config.memos_ingestion_mode not in {"poll", "both"}:
            return False
        if not self.config.memos_base_url or not self.config.memos_api_token:
            return False

        client = MemosClient(
            base_url=self.config.memos_base_url,
            api_token=self.config.memos_api_token,
            timeout_seconds=self.config.memos_timeout_seconds,
        )
        response = await client.list_memos(page_size=self.config.memos_poll_page_size)
        memos = response.get("memos", [])
        if not isinstance(memos, list):
            return False

        created_any = False
        for memo in memos:
            if not isinstance(memo, dict) or _is_sidecar_summary_memo(memo):
                continue
            memo_uid = _memo_uid(memo)
            update_time = memo.get("updateTime") or memo.get("update_time") or memo.get("updatedTs")
            if not memo_uid or self.store.has_memo(
                workspace_id=self.config.workspace_id,
                memos_uid=memo_uid,
                memo_type="original",
            ):
                continue
            idempotency_key = f"memos.poll:{memo_uid}:{update_time or 'unknown'}"
            if self.store.has_job(workspace_id=self.config.workspace_id, idempotency_key=idempotency_key):
                continue
            _, created = self.store.create_job(
                workspace_id=self.config.workspace_id,
                job_type="process_memo",
                idempotency_key=idempotency_key,
                payload={"memo_uid": memo_uid, "poll": {"memo": {"name": memo.get("name"), "updateTime": update_time}}},
            )
            created_any = created_any or created
        return created_any

    async def _ensure_admin_entry_memo_once(self) -> bool:
        if not self.config.memos_admin_entry_enabled:
            return False
        if not self.config.memos_base_url or not self.config.memos_api_token:
            return False

        client = MemosClient(
            base_url=self.config.memos_base_url,
            api_token=self.config.memos_api_token,
            timeout_seconds=self.config.memos_timeout_seconds,
        )
        desired_content = build_admin_entry_memo_content(
            public_base_url=self.config.public_base_url,
            title=self.config.memos_admin_entry_title,
        )
        existing = self.store.list_memos(
            workspace_id=self.config.workspace_id,
            memo_type="admin_entry",
            limit=1,
        )
        if existing:
            memo_uid = existing[0].memos_uid
            try:
                current = await client.get_memo(memo_uid)
            except Exception as exc:
                LOGGER.warning("Failed to read Memosima admin entry memo %s: %s", memo_uid, exc)
            else:
                if current.get("content") != desired_content:
                    await client.update_memo_content(memo_uid, desired_content)
                    self.store.upsert_memo(
                        workspace_id=self.config.workspace_id,
                        memos_uid=memo_uid,
                        memo_type="admin_entry",
                        status="updated",
                        content_hash=_memo_hash({"content": desired_content}),
                    )
                    return True
                return False

        response = await client.list_memos(
            page_size=self.config.memos_poll_page_size,
            filter_text=ADMIN_ENTRY_SEARCH_FILTER,
        )
        memos = response.get("memos", [])
        if isinstance(memos, list):
            for memo in memos:
                if not isinstance(memo, dict) or not _is_admin_entry_memo(memo):
                    continue
                memo_uid = _memo_uid(memo)
                if not memo_uid:
                    continue
                if memo.get("content") != desired_content:
                    await client.update_memo_content(memo_uid, desired_content)
                    status = "updated"
                else:
                    status = "synced"
                self.store.upsert_memo(
                    workspace_id=self.config.workspace_id,
                    memos_uid=memo_uid,
                    memo_type="admin_entry",
                    status=status,
                    content_hash=_memo_hash({"content": desired_content}),
                )
                return status == "updated"

        created = await client.create_memo(
            desired_content,
            visibility=self.config.memos_admin_entry_visibility,
        )
        memo_uid = _extract_memo_uid(created)
        self.store.upsert_memo(
            workspace_id=self.config.workspace_id,
            memos_uid=memo_uid,
            memo_type="admin_entry",
            status="created",
            content_hash=_memo_hash(created),
        )
        return True

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
        memo_content = content if isinstance(content, str) else ""
        self.store.upsert_memo(
            workspace_id=job.workspace_id,
            memos_uid=memo_uid,
            memo_type="original",
            status="synced",
            content_hash=content_hash,
        )

        attachment_results, attachment_markdowns = await self._process_attachments(
            client=client,
            workspace_id=job.workspace_id,
            memo_uid=memo_uid,
            memo=memo,
        )
        source_content = _build_source_content(memo_content, attachment_markdowns)
        user_tags = _extract_user_business_tags(memo_content)
        allow_ai_tags = not user_tags
        reminder_result = await self._handle_reminders(
            client=client,
            workspace_id=job.workspace_id,
            memo_uid=memo_uid,
            source_content=source_content,
        )
        organization_plan = taxonomy.build_organization_plan_from_tags(source_content, user_tags)
        self._upsert_tag_candidates(job.workspace_id, memo_uid, organization_plan.candidate_tags)

        if organization_plan.needs_clarification:
            comment = _clarification_comment(organization_plan.clarification_reason)
            await client.create_comment(memo_uid, comment)
            return {
                "status": "waiting_user",
                "memo_uid": memo_uid,
                "content_hash": content_hash,
                "ai_plan": organization_plan.to_dict(),
                "attachments": attachment_results,
                "reminder": reminder_result,
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
                "reminder": reminder_result,
                "clarification_comment_created": True,
                "clarification_comment": comment,
            }
        if llm_draft and allow_ai_tags:
            organization_plan = self._merge_llm_tags(
                taxonomy=taxonomy,
                local_plan=organization_plan,
                llm_draft=llm_draft,
            )
            self._upsert_tag_candidates(job.workspace_id, memo_uid, organization_plan.candidate_tags)

        original_title_content = _build_original_title_backfill_content(
            memo_content=memo_content,
            attachment_markdowns=attachment_markdowns,
            llm_draft=llm_draft,
        )
        original_memo_title_updated = False
        if original_title_content:
            await client.update_memo_content(memo_uid, original_title_content)
            original_memo_title_updated = True

        summary_content = build_summary_memo_content(
            source_memo_uid=memo_uid,
            source_content=source_content,
            organization_plan=organization_plan,
            taxonomy=taxonomy,
            llm_draft=llm_draft,
            show_candidate_tags=self.config.memos_show_candidate_tags,
            admin_links=build_summary_admin_links(
                public_base_url=self.config.public_base_url,
                has_candidate_tags=bool(organization_plan.candidate_tags),
            )
            if self.config.memos_admin_entry_enabled
            else None,
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
            source_memo_uid=summary_memo_uid,
            related_memo_uid=memo_uid,
        )

        vector_search_result = await self._handle_vector_search(
            workspace_id=job.workspace_id,
            memo_uid=memo_uid,
            source_content=source_content,
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
            "reminder": reminder_result,
            "vector_search": vector_search_result,
            "comment_created": comment_created,
            "original_memo_title_updated": original_memo_title_updated,
            "original_memo_title": _extract_backfilled_title(original_title_content) if original_title_content else None,
        }

    async def _process_attachments(
        self,
        *,
        client: MemosClient,
        workspace_id: str,
        memo_uid: str,
        memo: dict[str, object],
    ) -> tuple[list[dict[str, object]], list[str]]:
        results: list[dict[str, object]] = []
        markdowns: list[str] = []
        document_parser = create_document_parser(self.config)
        for resource in extract_attachment_resources(memo):
            try:
                data = await client.download_resource(resource.name, filename=resource.filename)
                parsed = parse_text_attachment(
                    resource=resource,
                    data=data,
                    max_bytes=self.config.max_attachment_bytes,
                    allowed_extensions=self.config.allowed_parse_extensions,
                )
                if isinstance(parsed, SkippedAttachment) and _should_parse_with_document_parser(parsed):
                    if document_parser is None:
                        parsed = SkippedAttachment(
                            resource,
                            "document_parser_not_configured",
                            {
                                **parsed.metadata,
                                "parser_provider": self.config.document_parser_provider,
                                "token_env": self.config.document_parser_token_env,
                            },
                        )
                    else:
                        parsed = await document_parser.parse(resource=resource, data=data)
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
                    markdowns.append(_format_attachment_markdown(resource.filename, parsed.content_markdown))
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
        return results, markdowns

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
        models_config = self._load_models_config()
        prompt_template = self._load_prompt_template(job)
        provider = _provider_for_prompt(models_config, prompt_template)
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
            prompt_template=prompt_template,
        )

    async def _handle_vector_search(
        self,
        *,
        workspace_id: str,
        memo_uid: str,
        source_content: str,
    ) -> dict[str, object]:
        if not self.config.vector_search_enabled:
            return {"status": "disabled"}
        
        api_key = os.getenv(self.config.vector_search_api_key_env)
        if not api_key:
            return {"status": "skipped", "reason": "api_key_not_configured"}

        chunks = _chunk_text(source_content, max_length=500)
        if not chunks:
            self.store.replace_vector_units(workspace_id=workspace_id, memo_uid=memo_uid, chunks=[])
            return {"status": "skipped", "reason": "no_content"}

        client = EmbeddingClient(
            base_url=self.config.vector_search_base_url,
            api_key=api_key,
            model=self.config.vector_search_model,
        )

        try:
            embeddings = await client.get_embeddings(chunks)
        except Exception as exc:
            LOGGER.warning("Vector embedding failed for memo %s: %s", memo_uid, exc)
            return {"status": "failed", "reason": str(exc)}

        if len(embeddings) != len(chunks):
            return {"status": "failed", "reason": "embedding_count_mismatch"}

        unit_data = list(zip(chunks, embeddings))
        self.store.replace_vector_units(workspace_id=workspace_id, memo_uid=memo_uid, chunks=unit_data)
        
        return {
            "status": "succeeded",
            "chunks_count": len(chunks),
        }

    async def _handle_reminders(
        self,
        *,
        client: MemosClient,
        workspace_id: str,
        memo_uid: str,
        source_content: str,
    ) -> dict[str, object]:
        if not self.config.reminders_enabled:
            return {"status": "disabled"}
        if self.config.reminders_trigger_tag not in source_content:
            return {"status": "not_triggered"}
        if self.models_config is None:
            return {"status": "skipped", "reason": "models_not_configured"}
        models_config = self._load_models_config()
        prompt_template = load_prompts_or_default(self.config.prompts_path).reminder_extraction
        provider = _provider_for_prompt(models_config, prompt_template)
        api_key = os.getenv(provider.api_key_env)
        if not api_key:
            return {"status": "skipped", "reason": "llm_key_not_configured"}

        llm_client = OpenAICompatibleClient(
            provider=provider,
            api_key=api_key,
            timeout_seconds=self.config.memos_timeout_seconds,
        )
        try:
            extraction = await llm_client.extract_reminders(
                content=source_content,
                timezone=self.config.timezone,
                now=_now_in_timezone(self.config.timezone).isoformat(timespec="seconds"),
                trigger_tag=self.config.reminders_trigger_tag,
                prompt_template=prompt_template,
            )
        except Exception as exc:
            LOGGER.warning("Reminder extraction failed for memo %s: %s", memo_uid, exc)
            return {"status": "skipped", "reason": "extract_failed"}

        created: list[dict[str, object]] = []
        skipped: list[dict[str, object]] = []
        clarification_questions: list[str] = []
        now_utc = datetime.now(UTC)

        for item in extraction.items:
            due_at = _parse_due_at(item.due_at, item.timezone or self.config.timezone)
            if item.confidence < self.config.reminders_confidence_threshold:
                skipped.append({"reason": "low_confidence", "title": item.title, "confidence": item.confidence})
                continue
            if due_at is None:
                skipped.append({"reason": "invalid_due_at", "title": item.title})
                continue
            if due_at <= now_utc:
                skipped.append({"reason": "past_due_at", "title": item.title, "due_at": due_at.isoformat(timespec="seconds")})
                continue
            reminder, inserted = self.store.create_reminder(
                workspace_id=workspace_id,
                source_memo_uid=memo_uid,
                title=item.title,
                body=item.body or item.raw_text or item.title,
                due_at=due_at.isoformat(timespec="seconds"),
                timezone=item.timezone or self.config.timezone,
                confidence=item.confidence,
                raw_text=item.raw_text or source_content[:1000],
            )
            created.append({"id": reminder.id, "created": inserted, "due_at": reminder.due_at, "title": reminder.title})

        if extraction.needs_clarification and extraction.clarification_question:
            clarification_questions.append(extraction.clarification_question)
        if skipped and not created:
            clarification_questions.append("请补充明确的提醒日期和时间，例如：#提醒 明天 09:30 提醒我提交周报。")
        if clarification_questions:
            comment = _reminder_clarification_comment(_dedupe(clarification_questions)[0])
            await client.create_comment(memo_uid, comment)
            return {
                "status": "waiting_user",
                "created": created,
                "skipped": skipped,
                "clarification_comment_created": True,
                "clarification_comment": comment,
            }

        if created:
            return {"status": "created", "created": created, "skipped": skipped}
        if extraction.has_reminder:
            return {"status": "skipped", "reason": "no_valid_items", "skipped": skipped}
        return {"status": "not_triggered"}

    def _load_models_config(self) -> ModelsConfig:
        self.models_config = ModelsConfig.load(self.models_path)
        return self.models_config

    async def _send_due_reminders_once(self) -> bool:
        if not self.config.reminders_enabled:
            return False
        reminders = self.store.list_due_reminders(
            workspace_id=self.config.workspace_id,
            now=utc_now(),
            limit=20,
        )
        if not reminders:
            return False
        for reminder in reminders:
            await self._send_reminder(reminder)
        return True

    async def _send_reminder(self, reminder: ReminderRecord) -> None:
        webhook_url = self.config.reminders_webhook_url
        if not webhook_url:
            self.store.mark_reminder_failed(reminder.id, "REMINDER_WEBHOOK_URL is not configured")
            return
        title = f"Memosima 提醒：{reminder.title}"
        body = (
            f"{reminder.body}\n\n"
            f"到期时间：{reminder.due_at}\n"
            f"来源 memo UID：{reminder.source_memo_uid}"
        )
        try:
            async with httpx.AsyncClient(timeout=self.config.reminders_request_timeout_seconds) as client:
                response = await client.post(webhook_url, data={"title": title, "body": body})
            response.raise_for_status()
        except Exception as exc:
            LOGGER.warning("Reminder send failed for id %s: %s", reminder.id, exc)
            self.store.mark_reminder_failed(reminder.id, _sanitize_error(str(exc)))
            return
        self.store.mark_reminder_sent(reminder.id)

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
        active_tag_result_paths = set(active_tags)
        candidate_paths = {candidate.path for candidate in candidates}
        candidate_leafs = {_tag_leaf(candidate.path) for candidate in candidates}
        llm_active_added = 0
        llm_candidates_added = 0

        def add_candidate(path: str, reason: str, confidence: float) -> None:
            nonlocal candidate_paths, candidate_leafs, llm_candidates_added
            if (
                path in candidate_paths
                or path in active_tag_paths
                or _tag_leaf(path) in candidate_leafs
                or path.startswith("#系统/")
            ):
                return
            if llm_candidates_added >= self.config.max_ai_candidate_tags:
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
            candidate_leafs.add(_tag_leaf(path))
            llm_candidates_added += 1

        def add_active(path: str) -> None:
            nonlocal llm_active_added
            if path in active_tag_result_paths:
                return
            if llm_active_added >= self.config.max_ai_active_tags:
                return
            active_tags.append(path)
            active_tag_result_paths.add(path)
            llm_active_added += 1

        for raw_tag in llm_draft.active_tags:
            try:
                tag, status = taxonomy.resolve_business_tag(raw_tag)
            except Exception:
                continue
            if status == "disabled":
                disabled_tags.append(tag)
            elif status == "active":
                add_active(tag)
            elif not tag.startswith("#系统/"):
                add_candidate(tag, "AI suggested this tag from memo content but it is not approved", 0.6)

        for llm_candidate in llm_draft.candidate_tags:
            try:
                tag, status = taxonomy.resolve_business_tag(llm_candidate.path)
            except Exception:
                continue
            if status == "disabled":
                disabled_tags.append(tag)
            elif status == "active":
                add_active(tag)
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

    def _upsert_tag_candidates(
        self,
        workspace_id: str,
        memo_uid: str,
        candidates: tuple[TagCandidate, ...],
    ) -> None:
        for candidate in candidates:
            try:
                self.store.upsert_tag_candidate(
                    workspace_id=workspace_id,
                    path=candidate.path,
                    parent_path=candidate.parent_path,
                    reason=candidate.reason,
                    source_memo_uid=memo_uid,
                    similar_tags=list(candidate.similar_existing_tags),
                    confidence=candidate.confidence,
                )
            except ValueError:
                LOGGER.info("Skipping tag candidate with non-unique leaf: %s", candidate.path)


def _memo_hash(memo: dict[str, object]) -> str:
    payload = json.dumps(memo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_memo_uid(memo: dict[str, object]) -> str:
    name = memo.get("name")
    if not isinstance(name, str) or not name.startswith("memos/"):
        raise ValueError("Created summary memo response is missing name")
    return name.removeprefix("memos/")


def _memo_uid(memo: dict[str, object]) -> str | None:
    name = memo.get("name")
    if isinstance(name, str) and name.startswith("memos/"):
        return name.removeprefix("memos/")
    uid = memo.get("uid") or memo.get("id")
    return str(uid) if uid else None


def _is_sidecar_summary_memo(memo: dict[str, object]) -> bool:
    sidecar_tags = {"系统/AI整理", "系统/标签总结", "系统/Memosima"}
    tags = memo.get("tags")
    if isinstance(tags, list) and sidecar_tags.intersection({str(tag) for tag in tags}):
        return True
    content = memo.get("content")
    return isinstance(content, str) and (
        ADMIN_ENTRY_MARKER in content
        or any(content.lstrip().startswith(f"#{tag}") for tag in sidecar_tags)
    )


def _is_admin_entry_memo(memo: dict[str, object]) -> bool:
    content = memo.get("content")
    return isinstance(content, str) and ADMIN_ENTRY_MARKER in content


def _extract_user_business_tags(content: str) -> tuple[str, ...]:
    tags: list[str] = []
    for token in content.replace("\n", " ").split():
        if not token.startswith("#"):
            continue
        tag = token.rstrip(".,;:!?，。；：！？）)")
        if tag.strip("#") and not tag.startswith("#系统/"):
            tags.append(tag)
    return tuple(_dedupe(tags))


def _clarification_comment(reason: str | None) -> str:
    message = reason or "内容需要进一步澄清。"
    return f"Memosima 需要补充信息后再整理：{message}"


def _reminder_clarification_comment(reason: str) -> str:
    return f"Memosima 提醒需要补充信息：{reason}"


def _dedupe(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _tag_leaf(tag: str) -> str:
    return tag.rsplit("/", maxsplit=1)[-1].removeprefix("#")


def _provider_for_prompt(models: ModelsConfig, prompt: PromptTemplate) -> ProviderConfig:
    provider_name = prompt.provider or models.default_provider
    try:
        return models.providers[provider_name]
    except KeyError as exc:
        raise RuntimeError(f"LLM provider is not configured: {provider_name}") from exc


def _build_source_content(memo_content: str, attachment_markdowns: list[str]) -> str:
    parts = [memo_content.strip()] if memo_content.strip() else []
    parts.extend(markdown.strip() for markdown in attachment_markdowns if markdown.strip())
    return "\n\n".join(parts)


def _format_attachment_markdown(filename: str, markdown: str) -> str:
    return f"## 附件：{filename}\n\n{markdown.strip()}"


def _build_original_title_backfill_content(
    *,
    memo_content: str,
    attachment_markdowns: list[str],
    llm_draft: LLMOrganizationDraft | None,
) -> str | None:
    if memo_content.strip() or not attachment_markdowns or llm_draft is None:
        return None
    title = _sanitize_original_title(llm_draft.title)
    if not title:
        return None
    return f"# {title}"


def _sanitize_original_title(title: str) -> str:
    text = " ".join(title.strip().split())
    for prefix in ("AI整理：", "AI整理:", "AI整理"):
        if text.startswith(prefix):
            text = text.removeprefix(prefix).strip()
    text = text.lstrip("#").strip()
    if len(text) > 120:
        text = text[:120].rstrip()
    return text


def _extract_backfilled_title(content: str) -> str:
    return content.removeprefix("#").strip()


def _should_parse_with_document_parser(skipped: SkippedAttachment) -> bool:
    return skipped.reason == "parser_not_implemented" and is_document_attachment(skipped.resource)


def _now_in_timezone(timezone: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        return datetime.now(UTC)


def _parse_due_at(value: str, timezone: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
        except ZoneInfoNotFoundError:
            parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _sanitize_error(error: str) -> str:
    text = error.strip().replace("\n", " ")
    return text[:500]


def _chunk_text(text: str, max_length: int = 500) -> list[str]:
    lines = text.splitlines()
    chunks = []
    current_chunk = []
    current_len = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        line_len = len(stripped)
        if current_len + line_len > max_length and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = [stripped]
            current_len = line_len
        else:
            current_chunk.append(stripped)
            current_len += line_len + 1 # +1 for newline
    
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    return chunks


async def _run(args: argparse.Namespace) -> None:
    config = AppConfig.load(args.config)
    models = ModelsConfig.load(args.models)
    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace(config.workspace_id)
    worker = Worker(config, store, models, models_path=args.models, config_path=args.config)
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
