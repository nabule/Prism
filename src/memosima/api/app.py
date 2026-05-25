from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

LOGGER = logging.getLogger("memosima.api")

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from memosima import __version__
from memosima.api.admin_ui import ADMIN_UI_HTML
from memosima.api.security import require_admin
from memosima.api.webhooks import build_idempotency_key, extract_memo_uid
from memosima.core.config import AppConfig, ConfigError, ModelsConfig, ProviderConfig, _read_yaml, load_env_file
from memosima.core.prompts import PromptTemplate, PromptsConfig, load_prompts_or_default
from memosima.db.store import Job, MemoRecord, ReminderRecord, Store, TagCandidateRecord
from memosima.llm.provider import EmbeddingClient, LLMClientError, OpenAICompatibleClient
from memosima.memos.client import MemosClient


class WebhookAccepted(BaseModel):
    job_id: int
    created: bool
    idempotency_key: str
    memo_uid: str | None


class JobView(BaseModel):
    id: int
    workspace_id: str
    type: str
    status: str
    idempotency_key: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    retry_count: int
    created_at: str
    updated_at: str


class JobsResponse(BaseModel):
    jobs: list[JobView]


class TagCandidateView(BaseModel):
    id: int
    workspace_id: str
    path: str
    parent_path: str | None
    status: str
    reason: str
    source_memo_uid: str | None
    similar_tags: list[str]
    confidence: float
    reviewer_note: str | None
    created_at: str
    updated_at: str


class TagCandidatesResponse(BaseModel):
    candidates: list[TagCandidateView]


class ReminderView(BaseModel):
    id: int
    workspace_id: str
    source_memo_uid: str
    title: str
    body: str
    due_at: str
    timezone: str
    status: str
    confidence: float
    raw_text: str
    sent_at: str | None
    error: str | None
    created_at: str
    updated_at: str


class RemindersResponse(BaseModel):
    reminders: list[ReminderView]


class ReviewTagCandidateRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class PromptTemplateView(BaseModel):
    provider: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    system: str = Field(min_length=1, max_length=12000)
    user: str = Field(min_length=1, max_length=12000)


class PromptsResponse(BaseModel):
    organize_memo: PromptTemplateView
    tag_summary: PromptTemplateView
    reminder_extraction: PromptTemplateView


class LLMProviderView(BaseModel):
    name: str
    base_url: str
    api_key_env: str
    default_model: str
    temperature: float
    max_tokens: int | None
    response_format: str | None
    extra_body: dict[str, Any]
    api_key_present: bool
    is_default: bool


class LLMModelsResponse(BaseModel):
    default_provider: str
    providers: list[LLMProviderView]


class LLMProviderUpdateRequest(BaseModel):
    default_provider: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    base_url: str = Field(min_length=1, max_length=500)
    api_key_env: str = Field(min_length=1, max_length=120, pattern=r"^[A-Z_][A-Z0-9_]*$")
    default_model: str = Field(min_length=1, max_length=200)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=200000)
    response_format: str | None = Field(default="json_object", max_length=80)
    extra_body: dict[str, Any] = Field(default_factory=dict)
    api_key: str | None = Field(default=None, max_length=12000)


class RetryJobRequest(BaseModel):
    prompt_override: PromptTemplateView | None = None


class TagSummaryRequest(BaseModel):
    tag: str = Field(min_length=2, max_length=120)
    limit: int = Field(default=50, ge=1, le=200)


class TagSummaryResponse(BaseModel):
    tag: str
    memo_count: int
    summary_memo_uid: str
    content: str


class ReprocessPromptOverride(BaseModel):
    system: str | None = Field(default=None, max_length=20000)
    user: str | None = Field(default=None, max_length=20000)


class ReprocessMemoRequest(BaseModel):
    memo_url_or_uid: str = Field(min_length=1, max_length=2000)
    model_provider: str | None = Field(default=None, max_length=80)
    model_name: str | None = Field(default=None, max_length=200)
    prompt_override: ReprocessPromptOverride | None = None


class BatchReprocessTagRequest(BaseModel):
    tag: str = Field(min_length=1, max_length=120)
    model_provider: str | None = Field(default=None, max_length=80)
    model_name: str | None = Field(default=None, max_length=200)
    prompt_override: ReprocessPromptOverride | None = None


class ReprocessMemoResponse(BaseModel):
    job_id: int
    status: str
    memo_uid: str
    old_summaries_deleted: list[str]


class BatchReprocessTagResponse(BaseModel):
    tag: str
    matched_memo_count: int
    jobs_created: int
    job_ids: list[int]
    old_summaries_deleted_count: int


class BackupRestoreResponse(BaseModel):
    restored_database: bool
    restored_configs: bool = False
    backup_version: int
    source_created_at: str | None = None
    message: str


def get_git_commit_hash() -> str | None:
    import subprocess
    env_hash = os.environ.get("COMMIT_HASH") or os.environ.get("GIT_COMMIT")
    if env_hash:
        return env_hash
    try:
        cwd = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=2
        )
        return result.stdout.strip()
    except Exception:
        return None


class HealthResponse(BaseModel):
    service: str = "memosima"
    version: str
    commit_hash: str | None = None
    database: str
    workspace_id: str
    admin_token_configured: bool
    memos_base_url_configured: bool
    models_default_provider: str
    models_default_model: str
    models_api_key_present: bool
    reminders_enabled: bool
    reminders_webhook_configured: bool


class QA_Source(BaseModel):
    memos_uid: str
    content_excerpt: str
    tags: list[str]


class GeneratePromptRequest(BaseModel):
    tags: list[str]
    system_prompt: str
    query: str
    top_k: int = 15
    include_original: bool = True
    include_attachments: bool = True
    include_ai_summary: bool = True


class GeneratePromptResponse(BaseModel):
    assembled_prompt: str
    retrieved_count: int
    sources: list[QA_Source]


class DocumentParserConfigView(BaseModel):
    provider: str
    token_env: str
    base_url: str
    timeout_seconds: float
    poll_interval_seconds: float
    max_polls: int
    model_version: str
    language: str
    enable_table: bool
    enable_formula: bool
    is_ocr: bool
    api_key_present: bool


class DocumentParserUpdateRequest(BaseModel):
    provider: str = Field(default="mineru", max_length=80)
    token_env: str = Field(default="MINERU_API_TOKEN", max_length=120, pattern=r"^[A-Z_][A-Z0-9_]*$")
    base_url: str = Field(default="https://mineru.net", max_length=500)
    timeout_seconds: float = Field(default=60, ge=1, le=600)
    poll_interval_seconds: float = Field(default=3, ge=1, le=60)
    max_polls: int = Field(default=60, ge=1, le=600)
    model_version: str = Field(default="vlm", max_length=40)
    language: str = Field(default="ch", max_length=20)
    enable_table: bool = True
    enable_formula: bool = True
    is_ocr: bool = False
    api_key: str | None = Field(default=None, max_length=12000)


class MemosConfigView(BaseModel):
    base_url: str
    api_token_present: bool
    api_token_env: str
    base_url_env: str


class MemosConfigUpdateRequest(BaseModel):
    base_url: str = Field(..., max_length=500)
    api_token: str | None = Field(default=None, max_length=12000)
    api_token_env: str = Field(default="MEMOS_API_TOKEN", max_length=120, pattern=r"^[A-Z_][A-Z0-9_]*$")
    base_url_env: str = Field(default="MEMOS_BASE_URL", max_length=120, pattern=r"^[A-Z_][A-Z0-9_]*$")


class RemindersConfigView(BaseModel):
    enabled: bool
    trigger_tag: str
    confidence_threshold: float
    request_timeout_seconds: float
    webhook_url_present: bool


class RemindersConfigUpdateRequest(BaseModel):
    enabled: bool
    trigger_tag: str = Field(default="#提醒", max_length=80)
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    request_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    webhook_url: str | None = Field(default=None, max_length=12000)


class VectorSearchConfigView(BaseModel):
    enabled: bool
    api_key_env: str
    base_url: str
    model: str
    api_key_present: bool


class VectorSearchConfigUpdateRequest(BaseModel):
    enabled: bool
    api_key_env: str = Field(default="SILICONFLOW_API_KEY", max_length=120, pattern=r"^[A-Z_][A-Z0-9_]*$")
    base_url: str = Field(default="https://api.siliconflow.cn/v1", max_length=500)
    model: str = Field(default="BAAI/bge-m3", max_length=80)
    api_key: str | None = Field(default=None, max_length=12000)


def create_app(
    config_path: str = "config/app.yaml",
    models_path: str = "config/models.yaml",
) -> FastAPI:
    app = FastAPI(title="Memosima Sidecar", version=__version__)

    try:
        config = AppConfig.load(config_path)
        models = ModelsConfig.load(models_path)
    except ConfigError as exc:
        raise RuntimeError(str(exc)) from exc

    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace(config.workspace_id)

    app.state.config = config
    app.state.models = models
    app.state.store = store
    app.state.admin_token = config.admin_token

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        current_models: ModelsConfig = app.state.models
        provider = current_models.providers[current_models.default_provider]
        return HealthResponse(
            version=__version__,
            commit_hash=get_git_commit_hash(),
            database=str(config.database_path),
            workspace_id=config.workspace_id,
            admin_token_configured=bool(config.admin_token),
            memos_base_url_configured=bool(config.memos_base_url),
            models_default_provider=current_models.default_provider,
            models_default_model=provider.default_model,
            models_api_key_present=provider.api_key_present,
            reminders_enabled=config.reminders_enabled,
            reminders_webhook_configured=bool(config.reminders_webhook_url),
        )

    @app.get("/admin/ui", include_in_schema=False)
    async def admin_ui() -> Response:
        return Response(content=ADMIN_UI_HTML, media_type="text/html; charset=utf-8")

    @app.post("/webhooks/memos", response_model=WebhookAccepted, status_code=status.HTTP_202_ACCEPTED)
    async def memos_webhook(request: Request) -> WebhookAccepted:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook payload must be a JSON object",
            )
        memo_uid = extract_memo_uid(payload)
        idempotency_key = build_idempotency_key(payload)
        job, created = store.create_job(
            workspace_id=config.workspace_id,
            job_type="process_memo",
            idempotency_key=idempotency_key,
            payload={"memo_uid": memo_uid, "webhook": payload},
        )
        return WebhookAccepted(
            job_id=job.id,
            created=created,
            idempotency_key=idempotency_key,
            memo_uid=memo_uid,
        )

    @app.get(
        "/admin/jobs",
        response_model=JobsResponse,
        dependencies=[Depends(require_admin)],
    )
    async def list_jobs(
        status_filter: str | None = Query(default=None, alias="status"),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> JobsResponse:
        return JobsResponse(jobs=[_job_view(job) for job in store.list_jobs(status=status_filter, limit=limit)])

    @app.get(
        "/admin/prompts",
        response_model=PromptsResponse,
        dependencies=[Depends(require_admin)],
    )
    async def get_prompts() -> PromptsResponse:
        prompts = load_prompts_or_default(config.prompts_path)
        return PromptsResponse(
            organize_memo=_prompt_view(prompts.organize_memo),
            tag_summary=_prompt_view(prompts.tag_summary),
            reminder_extraction=_prompt_view(prompts.reminder_extraction),
        )

    @app.get(
        "/admin/models",
        response_model=LLMModelsResponse,
        dependencies=[Depends(require_admin)],
    )
    async def get_models() -> LLMModelsResponse:
        return _models_response(app.state.models)

    @app.put(
        "/admin/models",
        response_model=LLMModelsResponse,
        dependencies=[Depends(require_admin)],
    )
    async def update_models(request: LLMProviderUpdateRequest) -> LLMModelsResponse:
        if request.api_key and ("\n" in request.api_key or "\r" in request.api_key):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key must be a single line")
        updated_provider = ProviderConfig(
            name=request.default_provider,
            base_url=request.base_url.strip().rstrip("/"),
            api_key_env=request.api_key_env,
            default_model=request.default_model.strip(),
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            response_format=_normalize_response_format(request.response_format),
            extra_body=dict(request.extra_body),
            api_key_present=_provider_api_key_present(request.api_key_env, request.api_key),
        )
        current_models: ModelsConfig = app.state.models
        updated_providers = dict(current_models.providers)
        updated_providers[request.default_provider] = updated_provider
        updated = ModelsConfig(default_provider=request.default_provider, providers=updated_providers)
        updated.save(models_path)
        env_path = Path(models_path).parent / ".env.local"
        if request.api_key is not None and request.api_key.strip():
            _upsert_env_value(env_path, request.api_key_env, request.api_key.strip())
            os.environ[request.api_key_env] = request.api_key.strip()
            updated = ModelsConfig.load(models_path)
        app.state.models = updated
        return _models_response(updated)

    @app.put(
        "/admin/prompts/organize-memo",
        response_model=PromptTemplateView,
        dependencies=[Depends(require_admin)],
    )
    async def update_organize_memo_prompt(prompt: PromptTemplateView) -> PromptTemplateView:
        updated = PromptTemplate(system=prompt.system, user=prompt.user, provider=prompt.provider)
        prompts = load_prompts_or_default(config.prompts_path)
        PromptsConfig(
            organize_memo=updated,
            tag_summary=prompts.tag_summary,
            reminder_extraction=prompts.reminder_extraction,
        ).save(config.prompts_path)
        return _prompt_view(updated)

    @app.put(
        "/admin/prompts/tag-summary",
        response_model=PromptTemplateView,
        dependencies=[Depends(require_admin)],
    )
    async def update_tag_summary_prompt(prompt: PromptTemplateView) -> PromptTemplateView:
        updated = PromptTemplate(system=prompt.system, user=prompt.user, provider=prompt.provider)
        prompts = load_prompts_or_default(config.prompts_path)
        PromptsConfig(
            organize_memo=prompts.organize_memo,
            tag_summary=updated,
            reminder_extraction=prompts.reminder_extraction,
        ).save(config.prompts_path)
        return _prompt_view(updated)

    @app.put(
        "/admin/prompts/reminder-extraction",
        response_model=PromptTemplateView,
        dependencies=[Depends(require_admin)],
    )
    async def update_reminder_extraction_prompt(prompt: PromptTemplateView) -> PromptTemplateView:
        updated = PromptTemplate(system=prompt.system, user=prompt.user, provider=prompt.provider)
        prompts = load_prompts_or_default(config.prompts_path)
        PromptsConfig(
            organize_memo=prompts.organize_memo,
            tag_summary=prompts.tag_summary,
            reminder_extraction=updated,
        ).save(config.prompts_path)
        return _prompt_view(updated)

    @app.post(
        "/admin/tag-summaries",
        response_model=TagSummaryResponse,
        dependencies=[Depends(require_admin)],
    )
    async def create_tag_summary(request: TagSummaryRequest) -> TagSummaryResponse:
        if not config.memos_base_url or not config.memos_api_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Memos is not configured")
        current_models: ModelsConfig = app.state.models
        prompts = load_prompts_or_default(config.prompts_path)
        provider = _provider_for_prompt(current_models, prompts.tag_summary)
        api_key = os.getenv(provider.api_key_env)
        if not api_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="LLM key is not configured")

        memos_client = MemosClient(
            base_url=config.memos_base_url,
            api_token=config.memos_api_token,
            timeout_seconds=config.memos_timeout_seconds,
        )
        memos = await _list_memos_for_tag(
            memos_client,
            store=store,
            workspace_id=config.workspace_id,
            tag=request.tag,
            limit=request.limit,
        )
        if not memos:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No memos found for tag")

        memos_markdown = _memos_markdown(memos)
        llm_client = OpenAICompatibleClient(
            provider=provider,
            api_key=api_key,
            timeout_seconds=config.memos_timeout_seconds,
        )
        try:
            summary = await llm_client.summarize_tag(
                tag=request.tag,
                memos_markdown=memos_markdown,
                memo_count=len(memos),
                prompt_template=prompts.tag_summary,
            )
        except LLMClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM tag summary request failed",
            ) from exc
        content = _tag_summary_memo_content(tag=request.tag, summary=summary, memos=memos)
        created = await memos_client.create_memo(content)
        summary_uid = _memo_uid_from_name(created.get("name"))
        if not summary_uid:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Memos summary response missing name")
        for related_uid in _memo_uids_from_memos(memos):
            await memos_client.upsert_memo_reference_relation(
                source_memo_uid=summary_uid,
                related_memo_uid=related_uid,
            )
        return TagSummaryResponse(
            tag=request.tag,
            memo_count=len(memos),
            summary_memo_uid=summary_uid,
            content=content,
        )

    @app.post(
        "/admin/jobs/{job_id}/retry",
        response_model=JobView,
        dependencies=[Depends(require_admin)],
    )
    async def retry_job(job_id: int, retry: RetryJobRequest | None = None) -> JobView:
        payload_patch = None
        if retry and retry.prompt_override:
            payload_patch = {"llm_prompt_override": retry.prompt_override.model_dump(exclude_none=True)}
        job = store.retry_job_with_payload(job_id, payload_patch)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return _job_view(job)

    @app.post(
        "/admin/jobs/reprocess-memo",
        response_model=ReprocessMemoResponse,
        dependencies=[Depends(require_admin)],
    )
    async def reprocess_memo(request: ReprocessMemoRequest) -> ReprocessMemoResponse:
        match = re.search(r"(?:/m/|/memos/)([A-Za-z0-9_-]+)", request.memo_url_or_uid)
        memo_uid = match.group(1) if match else request.memo_url_or_uid.strip()
        if not memo_uid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Memo URL or UID")

        if not config.memos_base_url or not config.memos_api_token:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Memos not configured")
        
        memos_client = MemosClient(
            base_url=config.memos_base_url,
            api_token=config.memos_api_token,
            timeout_seconds=config.memos_timeout_seconds,
        )

        try:
            await memos_client.get_memo(memo_uid)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memo '{memo_uid}' not found on Memos side: {str(exc)}",
            )

        deleted_summaries: list[str] = []
        with store.connect() as conn:
            rows = conn.execute(
                "SELECT memos_uid FROM memos WHERE source_memo_uid = ? AND type = 'ai_summary'",
                (memo_uid,),
            ).fetchall()
            for row in rows:
                old_uid = str(row["memos_uid"])
                try:
                    await memos_client.delete_memo(old_uid)
                    deleted_summaries.append(old_uid)
                except Exception as exc:
                    LOGGER.warning("Failed to delete old AI summary %s on Memos: %s", old_uid, exc)
            
            if deleted_summaries:
                conn.execute(
                    f"DELETE FROM memos WHERE memos_uid IN ({','.join(['?'] * len(deleted_summaries))})",
                    deleted_summaries,
                )
                conn.execute("DELETE FROM tag_candidates WHERE source_memo_uid = ?", (memo_uid,))
                
        import uuid
        idempotency_key = f"manual.reprocess:{memo_uid}:{uuid.uuid4().hex[:8]}"
        payload = {"memo_uid": memo_uid, "manual": True}
        if request.model_provider:
            payload["model_provider"] = request.model_provider
        if request.model_name:
            payload["model_name"] = request.model_name
        if request.prompt_override:
            payload["llm_prompt_override"] = request.prompt_override.model_dump(exclude_none=True)

        job, created = store.create_job(
            workspace_id=config.workspace_id,
            job_type="process_memo",
            idempotency_key=idempotency_key,
            payload=payload,
        )
        
        return ReprocessMemoResponse(
            job_id=job.id,
            status=job.status,
            memo_uid=memo_uid,
            old_summaries_deleted=deleted_summaries,
        )

    @app.post(
        "/admin/jobs/batch-reprocess-tag",
        response_model=BatchReprocessTagResponse,
        dependencies=[Depends(require_admin)],
    )
    async def batch_reprocess_tag(request: BatchReprocessTagRequest) -> BatchReprocessTagResponse:
        if not config.memos_base_url or not config.memos_api_token:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Memos not configured")
        
        memos_client = MemosClient(
            base_url=config.memos_base_url,
            api_token=config.memos_api_token,
            timeout_seconds=config.memos_timeout_seconds,
        )

        memos = await _list_memos_for_tag(
            memos_client,
            store=store,
            workspace_id=config.workspace_id,
            tag=request.tag,
            limit=200,
        )

        if not memos:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No memos found for the specified tag")

        job_ids: list[int] = []
        old_summaries_deleted_count = 0
        import uuid

        memo_uids = _memo_uids_from_memos(memos)

        for memo_uid in memo_uids:
            deleted_summaries: list[str] = []
            with store.connect() as conn:
                rows = conn.execute(
                    "SELECT memos_uid FROM memos WHERE source_memo_uid = ? AND type = 'ai_summary'",
                    (memo_uid,),
                ).fetchall()
                for row in rows:
                    old_uid = str(row["memos_uid"])
                    try:
                        await memos_client.delete_memo(old_uid)
                        deleted_summaries.append(old_uid)
                    except Exception as exc:
                        LOGGER.warning("Failed to delete old AI summary %s on Memos: %s", old_uid, exc)
                
                if deleted_summaries:
                    conn.execute(
                        f"DELETE FROM memos WHERE memos_uid IN ({','.join(['?'] * len(deleted_summaries))})",
                        deleted_summaries,
                    )
                    conn.execute("DELETE FROM tag_candidates WHERE source_memo_uid = ?", (memo_uid,))
                    old_summaries_deleted_count += len(deleted_summaries)

            idempotency_key = f"manual.reprocess:{memo_uid}:{uuid.uuid4().hex[:8]}"
            payload = {"memo_uid": memo_uid, "manual": True}
            if request.model_provider:
                payload["model_provider"] = request.model_provider
            if request.model_name:
                payload["model_name"] = request.model_name
            if request.prompt_override:
                payload["llm_prompt_override"] = request.prompt_override.model_dump(exclude_none=True)

            job, created = store.create_job(
                workspace_id=config.workspace_id,
                job_type="process_memo",
                idempotency_key=idempotency_key,
                payload=payload,
            )
            job_ids.append(job.id)

        return BatchReprocessTagResponse(
            tag=request.tag,
            matched_memo_count=len(memos),
            jobs_created=len(job_ids),
            job_ids=job_ids,
            old_summaries_deleted_count=old_summaries_deleted_count,
        )

    @app.get(
        "/admin/backups/download",
        dependencies=[Depends(require_admin)],
    )
    async def download_backup() -> Response:
        backup = _build_backup_archive(
            config=config,
            models_path=Path(models_path),
            config_path=Path(config_path),
        )
        filename = f"memosima-sidecar-backup-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.zip"
        return Response(
            content=backup,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post(
        "/admin/backups/restore",
        response_model=BackupRestoreResponse,
        dependencies=[Depends(require_admin)],
    )
    async def restore_backup(request: Request) -> BackupRestoreResponse:
        archive = await request.body()
        result = _restore_backup_archive(archive=archive, config=config)
        app.state.store = Store(config.database_path)
        app.state.store.migrate()
        app.state.store.ensure_workspace(config.workspace_id)
        return result

    @app.post(
        "/admin/database/reset",
        dependencies=[Depends(require_admin)],
    )
    async def reset_database() -> dict[str, str]:
        store.reset()
        store.ensure_workspace(config.workspace_id)
        return {"status": "ok", "message": "Database has been reset"}

    @app.get(
        "/admin/tag-candidates",
        response_model=TagCandidatesResponse,
        dependencies=[Depends(require_admin)],
    )
    async def list_tag_candidates(
        status_filter: str | None = Query(default="candidate", alias="status"),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> TagCandidatesResponse:
        return TagCandidatesResponse(
            candidates=[
                _tag_candidate_view(candidate)
                for candidate in store.list_tag_candidates(
                    workspace_id=config.workspace_id,
                    status=status_filter,
                    limit=limit,
                )
            ]
        )

    @app.get(
        "/admin/reminders/config",
        response_model=RemindersConfigView,
        dependencies=[Depends(require_admin)],
    )
    async def get_reminders_config() -> RemindersConfigView:
        cfg: AppConfig = app.state.config
        return RemindersConfigView(
            enabled=cfg.reminders_enabled,
            trigger_tag=cfg.reminders_trigger_tag,
            confidence_threshold=cfg.reminders_confidence_threshold,
            request_timeout_seconds=cfg.reminders_request_timeout_seconds,
            webhook_url_present=bool(cfg.reminders_webhook_url),
        )

    @app.put(
        "/admin/reminders/config",
        response_model=RemindersConfigView,
        dependencies=[Depends(require_admin)],
    )
    async def update_reminders_config(request: RemindersConfigUpdateRequest) -> RemindersConfigView:
        if request.webhook_url and ("\n" in request.webhook_url or "\r" in request.webhook_url):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook URL must be a single line")
        _update_app_yaml_reminders(
            config_path=Path(config_path),
            enabled=request.enabled,
            trigger_tag=request.trigger_tag.strip(),
            confidence_threshold=request.confidence_threshold,
            request_timeout_seconds=request.request_timeout_seconds,
        )
        if request.webhook_url is not None and request.webhook_url.strip():
            env_path = Path(config_path).parent / ".env.local"
            _upsert_env_value(env_path, "REMINDER_WEBHOOK_URL", request.webhook_url.strip())
            os.environ["REMINDER_WEBHOOK_URL"] = request.webhook_url.strip()
        app.state.config = AppConfig.load(config_path)
        return await get_reminders_config()

    @app.get(
        "/admin/vector-search/config",
        response_model=VectorSearchConfigView,
        dependencies=[Depends(require_admin)],
    )
    async def get_vector_search_config() -> VectorSearchConfigView:
        cfg: AppConfig = app.state.config
        return VectorSearchConfigView(
            enabled=cfg.vector_search_enabled,
            api_key_env=cfg.vector_search_api_key_env,
            base_url=cfg.vector_search_base_url,
            model=cfg.vector_search_model,
            api_key_present=bool(os.getenv(cfg.vector_search_api_key_env)),
        )

    @app.put(
        "/admin/vector-search/config",
        response_model=VectorSearchConfigView,
        dependencies=[Depends(require_admin)],
    )
    async def update_vector_search_config(request: VectorSearchConfigUpdateRequest) -> VectorSearchConfigView:
        _update_app_yaml_vector_search(
            config_path=Path(config_path),
            enabled=request.enabled,
            api_key_env=request.api_key_env,
            base_url=request.base_url,
            model=request.model,
        )
        if request.api_key is not None and request.api_key.strip():
            env_path = Path(config_path).parent / ".env.local"
            _upsert_env_value(env_path, request.api_key_env, request.api_key.strip())
            os.environ[request.api_key_env] = request.api_key.strip()
        app.state.config = AppConfig.load(config_path)
        return await get_vector_search_config()

    @app.get(
        "/admin/reminders",
        response_model=RemindersResponse,
        dependencies=[Depends(require_admin)],
    )
    async def list_reminders(
        status_filter: str | None = Query(default=None, alias="status"),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> RemindersResponse:
        return RemindersResponse(
            reminders=[
                _reminder_view(reminder)
                for reminder in store.list_reminders(
                    workspace_id=config.workspace_id,
                    status=status_filter,
                    limit=limit,
                )
            ]
        )

    @app.post(
        "/admin/reminders/{reminder_id}/retry",
        response_model=ReminderView,
        dependencies=[Depends(require_admin)],
    )
    async def retry_reminder(reminder_id: int) -> ReminderView:
        reminder = store.retry_reminder(reminder_id)
        if reminder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
        return _reminder_view(reminder)

    @app.post(
        "/admin/reminders/{reminder_id}/cancel",
        response_model=ReminderView,
        dependencies=[Depends(require_admin)],
    )
    async def cancel_reminder(reminder_id: int) -> ReminderView:
        reminder = store.cancel_reminder(reminder_id)
        if reminder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
        return _reminder_view(reminder)
    async def _trigger_reprocess_for_memo(memo_uid: str) -> None:
        if not config.memos_base_url or not config.memos_api_token:
            return
        try:
            memos_client = MemosClient(
                base_url=config.memos_base_url,
                api_token=config.memos_api_token,
                timeout_seconds=config.memos_timeout_seconds,
            )
            deleted_summaries = []
            with store.connect() as conn:
                rows = conn.execute(
                    "SELECT memos_uid FROM memos WHERE source_memo_uid = ? AND type = 'ai_summary'",
                    (memo_uid,),
                ).fetchall()
                for row in rows:
                    old_uid = str(row["memos_uid"])
                    try:
                        await memos_client.delete_memo(old_uid)
                        deleted_summaries.append(old_uid)
                    except Exception as exc:
                        LOGGER.warning("Failed to delete old AI summary %s on Memos: %s", old_uid, exc)
                if deleted_summaries:
                    conn.execute(
                        f"DELETE FROM memos WHERE memos_uid IN ({','.join(['?'] * len(deleted_summaries))})",
                        deleted_summaries,
                    )
            
            import uuid
            idempotency_key = f"manual.reprocess:{memo_uid}:{uuid.uuid4().hex[:8]}"
            store.create_job(
                workspace_id=config.workspace_id,
                job_type="process_memo",
                idempotency_key=idempotency_key,
                payload={"memo_uid": memo_uid, "manual": True},
            )
        except Exception as exc:
            LOGGER.error("Failed to trigger automatic reprocess for %s: %s", memo_uid, exc)

    @app.post(
        "/admin/tag-candidates/{candidate_id}/approve",
        response_model=TagCandidateView,
        dependencies=[Depends(require_admin)],
    )
    async def approve_tag_candidate(
        candidate_id: int,
        review: ReviewTagCandidateRequest | None = None,
    ) -> TagCandidateView:
        try:
            candidate = store.review_tag_candidate(
                candidate_id=candidate_id,
                status="approved",
                reviewer_note=review.note if review else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag candidate not found")
        
        # Trigger automatic reprocessing of the source memo to update the AI summary card
        if candidate.source_memo_uid:
            await _trigger_reprocess_for_memo(candidate.source_memo_uid)
            
        return _tag_candidate_view(candidate)

    @app.post(
        "/admin/tag-candidates/{candidate_id}/reject",
        response_model=TagCandidateView,
        dependencies=[Depends(require_admin)],
    )
    async def reject_tag_candidate(
        candidate_id: int,
        review: ReviewTagCandidateRequest | None = None,
    ) -> TagCandidateView:
        candidate = store.review_tag_candidate(
            candidate_id=candidate_id,
            status="rejected",
            reviewer_note=review.note if review else None,
        )
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag candidate not found")
            
        # Trigger automatic reprocessing of the source memo to update the AI summary card
        if candidate.source_memo_uid:
            await _trigger_reprocess_for_memo(candidate.source_memo_uid)
            
        return _tag_candidate_view(candidate)

    @app.get(
        "/admin/tags/business",
        response_model=list[str],
        dependencies=[Depends(require_admin)],
    )
    async def get_business_tags() -> list[str]:
        tags = store.list_business_tags(workspace_id=config.workspace_id)
        return [tag.path for tag in tags if tag.status == "active"]

    @app.post(
        "/admin/qa/generate-prompt",
        response_model=GeneratePromptResponse,
        dependencies=[Depends(require_admin)],
    )
    async def generate_prompt(request_data: GeneratePromptRequest) -> GeneratePromptResponse:
        if not config.memos_base_url or not config.memos_api_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Memos base URL or API token is not configured",
            )
        
        memos_client = MemosClient(
            base_url=config.memos_base_url,
            api_token=config.memos_api_token,
            timeout_seconds=config.memos_timeout_seconds,
        )
        
        retrieved_memos = []
        seen_memos = set()
        
        # If there are no tags, we can just fetch recent memos
        if not request_data.tags:
            try:
                response = await memos_client.list_memos(page_size=50)
                memos = response.get("memos", [])
                if isinstance(memos, list):
                    for memo in memos:
                        uid = memo.get("uid") or memo.get("name")
                        if uid and uid not in seen_memos:
                            seen_memos.add(uid)
                            retrieved_memos.append(memo)
            except Exception as exc:
                LOGGER.warning("QA list_memos failed: %s", exc)
        else:
            for tag_or_word in request_data.tags:
                tag_or_word = tag_or_word.strip()
                if not tag_or_word:
                    continue
                
                # Check if it's a tag or a keyword
                if tag_or_word.startswith("#"):
                    filter_str = f"tag in ['{tag_or_word}']"
                else:
                    filter_str = f"content.contains('{tag_or_word}')"
                
                try:
                    response = await memos_client.list_memos(page_size=50, filter_text=filter_str)
                    memos = response.get("memos", [])
                    if isinstance(memos, list):
                        for memo in memos:
                            uid = memo.get("uid") or memo.get("name")
                            if uid and uid not in seen_memos:
                                seen_memos.add(uid)
                                retrieved_memos.append(memo)
                except Exception as exc:
                    LOGGER.warning("QA list_memos failed for %s: %s", tag_or_word, exc)
                    
        # Limit to top_k
        retrieved_memos = retrieved_memos[:request_data.top_k]
        
        sources = []
        context_parts = []
        
        for memo in retrieved_memos:
            uid = memo.get("uid") or memo.get("name")
            if not uid:
                continue
            clean_uid = uid.split("/")[-1] if "/" in uid else uid
            content = memo.get("content", "")
            
            # Determine if this memo is an AI-generated summary or system summary
            is_ai_summary = "#系统/AI整理" in content or "#系统/标签总结" in content or "#系统/AI文档" in content
            
            # Apply RAG filters
            if is_ai_summary and not request_data.include_ai_summary:
                continue
            if not is_ai_summary and not request_data.include_original:
                continue
                
            # Retrieve associated high-fidelity parsed attachments if enabled
            artifacts = []
            if request_data.include_attachments:
                artifacts = store.list_artifacts(workspace_id=config.workspace_id, memo_uid=clean_uid)
            
            memo_tags = []
            for part in content.split():
                if part.startswith("#") and len(part) > 1:
                    memo_tags.append(part)
                    
            sources.append(
                QA_Source(
                    memos_uid=clean_uid,
                    content_excerpt=content[:200] + "..." if len(content) > 200 else content,
                    tags=memo_tags,
                )
            )
            
            snippet = f"### 来源 Memo [ID: {clean_uid}]\n"
            snippet += f"创建时间: {memo.get('createTime') or memo.get('create_time') or '未知'}\n"
            if memo_tags:
                snippet += f"标签: {', '.join(memo_tags)}\n"
            snippet += f"内容:\n{content}\n"
            
            if artifacts:
                snippet += "\n-- 关联解析附件 --\n"
                for art in artifacts:
                    snippet += f"附件名称: {art.resource_uid}\n"
                    snippet += f"内容:\n{art.content_markdown}\n"
                    
            context_parts.append(snippet)
            
        assembled_prompt = ""
        assembled_prompt += f"# 系统提示\n{request_data.system_prompt}\n\n"
        assembled_prompt += "# 知识库参考上下文\n"
        if context_parts:
            assembled_prompt += "\n\n".join(context_parts)
        else:
            assembled_prompt += "（未找到符合所选标签或检索词的知识库内容）\n"
        assembled_prompt += f"\n\n# 用户提问\n{request_data.query}\n"
        
        return GeneratePromptResponse(
            assembled_prompt=assembled_prompt,
            retrieved_count=len(retrieved_memos),
            sources=sources,
        )

    @app.get(
        "/admin/document-parser",
        response_model=DocumentParserConfigView,
        dependencies=[Depends(require_admin)],
    )
    async def get_document_parser_config() -> DocumentParserConfigView:
        cfg: AppConfig = app.state.config
        return DocumentParserConfigView(
            provider=cfg.document_parser_provider,
            token_env=cfg.document_parser_token_env,
            base_url=cfg.document_parser_base_url,
            timeout_seconds=cfg.document_parser_timeout_seconds,
            poll_interval_seconds=cfg.document_parser_poll_interval_seconds,
            max_polls=cfg.document_parser_max_polls,
            model_version=cfg.mineru_model_version,
            language=cfg.mineru_language,
            enable_table=cfg.mineru_enable_table,
            enable_formula=cfg.mineru_enable_formula,
            is_ocr=cfg.mineru_is_ocr,
            api_key_present=bool(os.getenv(cfg.document_parser_token_env)),
        )

    @app.put(
        "/admin/document-parser",
        response_model=DocumentParserConfigView,
        dependencies=[Depends(require_admin)],
    )
    async def update_document_parser_config(request: DocumentParserUpdateRequest) -> DocumentParserConfigView:
        if request.api_key and ("\n" in request.api_key or "\r" in request.api_key):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key must be a single line")
        _update_app_yaml_document_parser(
            config_path=Path(config_path),
            provider=request.provider,
            token_env=request.token_env,
            base_url=request.base_url.strip().rstrip("/"),
            timeout_seconds=request.timeout_seconds,
            poll_interval_seconds=request.poll_interval_seconds,
            max_polls=request.max_polls,
            model_version=request.model_version.strip(),
            language=request.language.strip(),
            enable_table=request.enable_table,
            enable_formula=request.enable_formula,
            is_ocr=request.is_ocr,
        )
        if request.api_key is not None and request.api_key.strip():
            env_path = Path(config_path).parent / ".env.local"
            _upsert_env_value(env_path, request.token_env, request.api_key.strip())
            os.environ[request.token_env] = request.api_key.strip()
        app.state.config = AppConfig.load(config_path)
        cfg: AppConfig = app.state.config
        return DocumentParserConfigView(
            provider=cfg.document_parser_provider,
            token_env=cfg.document_parser_token_env,
            base_url=cfg.document_parser_base_url,
            timeout_seconds=cfg.document_parser_timeout_seconds,
            poll_interval_seconds=cfg.document_parser_poll_interval_seconds,
            max_polls=cfg.document_parser_max_polls,
            model_version=cfg.mineru_model_version,
            language=cfg.mineru_language,
            enable_table=cfg.mineru_enable_table,
            enable_formula=cfg.mineru_enable_formula,
            is_ocr=cfg.mineru_is_ocr,
            api_key_present=bool(os.getenv(cfg.document_parser_token_env)),
        )

    @app.get(
        "/admin/memos/config",
        response_model=MemosConfigView,
        dependencies=[Depends(require_admin)],
    )
    async def get_memos_config() -> MemosConfigView:
        cfg: AppConfig = app.state.config
        raw = _read_yaml(Path(config_path)) if Path(config_path).exists() else {}
        memos_sec = raw.get("memos", {})
        base_url_env = str(memos_sec.get("base_url_env", "MEMOS_BASE_URL"))
        api_token_env = str(memos_sec.get("api_token_env", "MEMOS_API_TOKEN"))
        
        return MemosConfigView(
            base_url=os.getenv(base_url_env, ""),
            api_token_present=bool(os.getenv(api_token_env)),
            api_token_env=api_token_env,
            base_url_env=base_url_env,
        )

    @app.put(
        "/admin/memos/config",
        response_model=MemosConfigView,
        dependencies=[Depends(require_admin)],
    )
    async def update_memos_config(request: MemosConfigUpdateRequest) -> MemosConfigView:
        if request.api_token and ("\n" in request.api_token or "\r" in request.api_token):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API token must be a single line")
        
        _update_app_yaml_memos(
            config_path=Path(config_path),
            base_url_env=request.base_url_env,
            api_token_env=request.api_token_env,
        )
        
        env_path = Path(config_path).parent / ".env.local"
        _upsert_env_value(env_path, request.base_url_env, request.base_url.strip())
        os.environ[request.base_url_env] = request.base_url.strip()
        
        if request.api_token is not None and request.api_token.strip():
            _upsert_env_value(env_path, request.api_token_env, request.api_token.strip())
            os.environ[request.api_token_env] = request.api_token.strip()
            
        app.state.config = AppConfig.load(config_path)
        return await get_memos_config()

    @app.post(
        "/admin/qa/generate-prompt",
        response_model=GeneratePromptResponse,
        dependencies=[Depends(require_admin)],
    )
    async def generate_prompt(request: GeneratePromptRequest) -> GeneratePromptResponse:
        cfg: AppConfig = app.state.config
        if not cfg.vector_search_enabled:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vector search is disabled")
            
        api_key = os.getenv(cfg.vector_search_api_key_env)
        if not api_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vector search API key is not configured")
            
        client = EmbeddingClient(
            base_url=cfg.vector_search_base_url,
            api_key=api_key,
            model=cfg.vector_search_model,
        )
        
        try:
            embeddings = await client.get_embeddings([request.query])
        except LLMClientError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
            
        if not embeddings:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get embedding for query")
            
        query_embedding = embeddings[0]
        results = store.search_similar_chunks(
            workspace_id=config.workspace_id,
            query_embedding=query_embedding,
            limit=request.top_k,
        )
        
        sources = []
        context_parts = []
        for unit, score in results:
            # We can optionally filter by tag here if we load the tags for each memo, but for V1 we just return top similar chunks.
            # In V2, we would inner join vector_units with memos or artifacts to apply strict tag filters.
            sources.append(QA_Source(
                memos_uid=unit.memo_uid,
                content_excerpt=unit.chunk_text[:100] + "...",
                tags=[] # Tag fetching is deferred
            ))
            context_parts.append(f"Source (Memo UID {unit.memo_uid}):\n{unit.chunk_text}")
            
        context_text = "\n\n---\n\n".join(context_parts)
        
        assembled = f"{request.system_prompt}\n\n[References Context]\n{context_text}\n\n[User Query]\n{request.query}"
        
        return GeneratePromptResponse(
            assembled_prompt=assembled,
            retrieved_count=len(results),
            sources=sources,
        )


    return app

def _job_view(job: Job) -> JobView:
    return JobView(
        id=job.id,
        workspace_id=job.workspace_id,
        type=job.type,
        status=job.status,
        idempotency_key=job.idempotency_key,
        payload=job.payload,
        result=job.result,
        error=job.error,
        retry_count=job.retry_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _build_backup_archive(*, config: AppConfig, models_path: Path, config_path: Path) -> bytes:
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    buffer = io.BytesIO()
    config_files = _backup_config_files(config=config, models_path=models_path, config_path=config_path)
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_path = Path(tmpdir) / "sidecar.db"
        _copy_sqlite_database(config.database_path, snapshot_path)
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                "kind": "memosima-sidecar-backup",
                "version": 1,
                "created_at": created_at,
                "workspace_id": config.workspace_id,
                "database_path": str(config.database_path),
                "config_files": [name for name, _ in config_files],
                "restore_behavior": "database_only",
            }
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.write(snapshot_path, "database/sidecar.db")
            for archive_name, file_path in config_files:
                if file_path.exists() and file_path.is_file():
                    archive.write(file_path, archive_name)
    return buffer.getvalue()


def _restore_backup_archive(*, archive: bytes, config: AppConfig) -> BackupRestoreResponse:
    if len(archive) > 100 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Backup archive is too large")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zip_archive:
            _validate_backup_members(zip_archive)
            manifest = _read_backup_manifest(zip_archive)
            database_bytes = zip_archive.read("database/sidecar.db")
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Backup archive must be a ZIP file") from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Backup archive is missing database") from exc

    if manifest.get("kind") != "memosima-sidecar-backup":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported backup archive")
    version = int(manifest.get("version", 0))
    if version != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported backup version: {version}")

    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "restore.db"
        tmp_path.write_bytes(database_bytes)
        _validate_sqlite_database(tmp_path)
        replacement_path = config.database_path.with_suffix(f"{config.database_path.suffix}.restore")
        shutil.copy2(tmp_path, replacement_path)
        os.replace(replacement_path, config.database_path)

    store = Store(config.database_path)
    store.migrate()
    store.ensure_workspace(config.workspace_id)
    return BackupRestoreResponse(
        restored_database=True,
        restored_configs=False,
        backup_version=version,
        source_created_at=manifest.get("created_at") if isinstance(manifest.get("created_at"), str) else None,
        message="Sidecar database restored. Config files in the archive were not applied automatically.",
    )


def _copy_sqlite_database(source: Path, destination: Path) -> None:
    source.parent.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(source)
    try:
        destination_connection = sqlite3.connect(destination)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
    finally:
        source_connection.close()


def _backup_config_files(*, config: AppConfig, models_path: Path, config_path: Path) -> list[tuple[str, Path]]:
    files = [
        ("config/app.yaml", config_path),
        ("config/models.yaml", models_path),
        ("config/prompts.yaml", config.prompts_path),
        ("config/taxonomy.yaml", config.taxonomy_path),
    ]
    result: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for archive_name, path in files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append((archive_name, path))
    return result


def _validate_backup_members(archive: zipfile.ZipFile) -> None:
    for name in archive.namelist():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Backup archive contains unsafe paths")


def _read_backup_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        raw = json.loads(archive.read("manifest.json").decode("utf-8"))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Backup archive is missing manifest") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Backup manifest is invalid") from exc
    if not isinstance(raw, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Backup manifest must be an object")
    return raw


def _validate_sqlite_database(path: Path) -> None:
    try:
        connection = sqlite3.connect(path)
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Backup database is invalid") from exc
    if row is None or row[0] != "ok":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Backup database failed integrity check")


def _tag_candidate_view(candidate: TagCandidateRecord) -> TagCandidateView:
    return TagCandidateView(
        id=candidate.id,
        workspace_id=candidate.workspace_id,
        path=candidate.path,
        parent_path=candidate.parent_path,
        status=candidate.status,
        reason=candidate.reason,
        source_memo_uid=candidate.source_memo_uid,
        similar_tags=candidate.similar_tags,
        confidence=candidate.confidence,
        reviewer_note=candidate.reviewer_note,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def _reminder_view(reminder: ReminderRecord) -> ReminderView:
    return ReminderView(
        id=reminder.id,
        workspace_id=reminder.workspace_id,
        source_memo_uid=reminder.source_memo_uid,
        title=reminder.title,
        body=reminder.body,
        due_at=reminder.due_at,
        timezone=reminder.timezone,
        status=reminder.status,
        confidence=reminder.confidence,
        raw_text=reminder.raw_text,
        sent_at=reminder.sent_at,
        error=reminder.error,
        created_at=reminder.created_at,
        updated_at=reminder.updated_at,
    )


def _prompt_view(prompt: PromptTemplate) -> PromptTemplateView:
    return PromptTemplateView(provider=prompt.provider, system=prompt.system, user=prompt.user)


def _provider_for_prompt(models: ModelsConfig, prompt: PromptTemplate) -> ProviderConfig:
    provider_name = prompt.provider or models.default_provider
    provider = models.providers.get(provider_name)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"LLM provider is not configured: {provider_name}")
    return provider


def _models_response(models: ModelsConfig) -> LLMModelsResponse:
    return LLMModelsResponse(
        default_provider=models.default_provider,
        providers=[
            _provider_view(provider, is_default=name == models.default_provider)
            for name, provider in models.providers.items()
        ],
    )


def _provider_view(provider: ProviderConfig, *, is_default: bool) -> LLMProviderView:
    return LLMProviderView(
        name=provider.name,
        base_url=provider.base_url,
        api_key_env=provider.api_key_env,
        default_model=provider.default_model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
        response_format=provider.response_format,
        extra_body=provider.extra_body,
        api_key_present=provider.api_key_present,
        is_default=is_default,
    )


def _normalize_response_format(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _provider_api_key_present(api_key_env: str, api_key: str | None) -> bool:
    if api_key is not None and api_key.strip():
        return True
    load_env_file()
    return bool(os.getenv(api_key_env))


def _upsert_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(f"{key}="):
            updated.append(f"{key}={value}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        if updated and updated[-1] != "":
            updated.append("")
        updated.append(f"{key}={value}")
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _update_app_yaml_document_parser(
    *,
    config_path: Path,
    provider: str,
    token_env: str,
    base_url: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    max_polls: int,
    model_version: str,
    language: str,
    enable_table: bool,
    enable_formula: bool,
    is_ocr: bool,
) -> None:
    raw = _read_yaml(config_path) if config_path.exists() else {}
    raw["document_parser"] = {
        "provider": provider,
        "token_env": token_env,
        "base_url": base_url,
        "timeout_seconds": timeout_seconds,
        "poll_interval_seconds": poll_interval_seconds,
        "max_polls": max_polls,
        "mineru_model_version": model_version,
        "language": language,
        "enable_table": enable_table,
        "enable_formula": enable_formula,
        "is_ocr": is_ocr,
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(raw, file, allow_unicode=True, sort_keys=False)


def _update_app_yaml_reminders(
    *,
    config_path: Path,
    enabled: bool,
    trigger_tag: str,
    confidence_threshold: float,
    request_timeout_seconds: float,
) -> None:
    raw = _read_yaml(config_path) if config_path.exists() else {}
    raw["reminders"] = {
        "enabled": enabled,
        "trigger_tag": trigger_tag,
        "webhook_url_env": "REMINDER_WEBHOOK_URL",
        "confidence_threshold": confidence_threshold,
        "request_timeout_seconds": request_timeout_seconds,
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(raw, file, allow_unicode=True, sort_keys=False)


def _update_app_yaml_vector_search(
    *,
    config_path: Path,
    enabled: bool,
    api_key_env: str,
    base_url: str,
    model: str,
) -> None:
    raw = _read_yaml(config_path) if config_path.exists() else {}
    raw["vector_search"] = {
        "enabled": enabled,
        "api_key_env": api_key_env,
        "base_url": base_url,
        "model": model,
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(raw, file, allow_unicode=True, sort_keys=False)


def _update_app_yaml_memos(
    *,
    config_path: Path,
    base_url_env: str,
    api_token_env: str,
) -> None:
    raw = _read_yaml(config_path) if config_path.exists() else {}
    memos_section = raw.get("memos", {})
    memos_section["base_url_env"] = base_url_env
    memos_section["api_token_env"] = api_token_env
    raw["memos"] = memos_section
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(raw, file, allow_unicode=True, sort_keys=False)


def _memos_tag(tag: str) -> str:
    return tag.strip().removeprefix("#")


def _memo_matches_tag(memo: dict[str, Any], tag: str) -> bool:
    normalized = _memos_tag(tag)
    tags = memo.get("tags")
    if isinstance(tags, list) and any(_tag_path_matches(str(item), normalized) for item in tags):
        return True
    content = memo.get("content")
    return isinstance(content, str) and any(_tag_path_matches(item, normalized) for item in _extract_content_tags(content))


def _tag_path_matches(candidate: str, normalized_tag: str) -> bool:
    normalized_candidate = _memos_tag(candidate)
    return normalized_candidate == normalized_tag or normalized_candidate.startswith(f"{normalized_tag}/")


def _extract_content_tags(content: str) -> list[str]:
    return re.findall(r"#[0-9A-Za-z_\-\u4e00-\u9fff/]+", content)


async def _list_memos_for_tag(
    memos_client: MemosClient,
    *,
    store: Store,
    workspace_id: str,
    tag: str,
    limit: int,
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    matched_by_uid: dict[str, dict[str, Any]] = {}
    source_uids_from_summaries: list[str] = []
    page_token: str | None = None
    scanned = 0
    page_size = min(max(limit, 20), 100)
    max_scan = max(limit * 5, page_size)
    summary_sources = _summary_sources_by_uid(
        store.list_memos(workspace_id=workspace_id, memo_type="ai_summary", limit=max_scan * 2)
    )

    while len(matched) < limit and scanned < max_scan:
        response = await memos_client.list_memos(page_size=page_size, page_token=page_token)
        raw_memos = response.get("memos", [])
        if not isinstance(raw_memos, list):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Memos returned invalid response")

        for memo in raw_memos:
            if isinstance(memo, dict):
                scanned += 1
                memo_uid = _memo_uid_from_name(memo.get("name"))
                if _is_sidecar_generated_memo(memo):
                    if memo_uid and _memo_matches_tag(memo, tag):
                        source_uid = summary_sources.get(memo_uid)
                        if source_uid:
                            source_uids_from_summaries.append(source_uid)
                    continue
                if memo_uid:
                    matched_by_uid[memo_uid] = memo
                if _memo_matches_tag(memo, tag) and memo_uid and _append_unique_memo(matched, memo, limit):
                    if len(matched) >= limit:
                        break

        next_page_token = response.get("nextPageToken")
        if not isinstance(next_page_token, str) or not next_page_token:
            break
        page_token = next_page_token

    for source_uid in source_uids_from_summaries:
        if len(matched) >= limit:
            break
        memo = matched_by_uid.get(source_uid)
        if memo is not None:
            _append_unique_memo(matched, memo, limit)

    return matched


def _summary_sources_by_uid(records: list[MemoRecord]) -> dict[str, str]:
    return {record.memos_uid: record.source_memo_uid for record in records if record.source_memo_uid}


def _append_unique_memo(memos: list[dict[str, Any]], memo: dict[str, Any], limit: int) -> bool:
    uid = _memo_uid_from_name(memo.get("name"))
    if not uid:
        return False
    if any(_memo_uid_from_name(item.get("name")) == uid for item in memos):
        return False
    if len(memos) >= limit:
        return False
    memos.append(memo)
    return True


def _is_sidecar_generated_memo(memo: dict[str, Any]) -> bool:
    sidecar_tags = {"系统/AI整理", "系统/标签总结"}
    tags = memo.get("tags")
    if isinstance(tags, list) and sidecar_tags.intersection({str(tag).lstrip("#") for tag in tags}):
        return True
    content = memo.get("content")
    return isinstance(content, str) and any(
        content.lstrip().startswith(f"#{tag}") for tag in sidecar_tags
    )


def _memos_markdown(memos: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, memo in enumerate(memos, start=1):
        name = str(memo.get("name", "")).removeprefix("memos/")
        create_time = str(memo.get("createTime", ""))
        content = str(memo.get("content", "")).strip()
        blocks.append(f"### {index}. memo UID：{name}\n\n创建时间：{create_time}\n\n{content}")
    return "\n\n---\n\n".join(blocks)


def _tag_summary_memo_content(*, tag: str, summary: str, memos: list[dict[str, Any]]) -> str:
    references = "\n".join(f"- {str(memo.get('name', '')).removeprefix('memos/')}" for memo in memos)
    return (
        f"#系统/标签总结 {tag}\n\n"
        f"# {tag} 整体总结\n\n"
        f"{_sanitize_memo_name_references(summary.strip())}\n\n"
        "## 相关 memo UID\n\n"
        f"{references}\n"
    )


def _sanitize_memo_name_references(text: str) -> str:
    without_links = re.sub(r"\[([^\]]+)\]\(memos/([^)]+)\)", r"\1（memo UID：\2）", text)
    return re.sub(r"\bmemos/([0-9A-Za-z]+)", r"memo UID：\1", without_links)


def _memo_uids_from_memos(memos: list[dict[str, Any]]) -> list[str]:
    uids: list[str] = []
    for memo in memos:
        uid = _memo_uid_from_name(memo.get("name"))
        if uid:
            uids.append(uid)
    return uids


def _memo_uid_from_name(name: Any) -> str | None:
    if not isinstance(name, str) or not name.startswith("memos/"):
        return None
    return name.removeprefix("memos/")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/app.yaml")
    parser.add_argument("--models", default="config/models.yaml")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    uvicorn.run(create_app(args.config, args.models), host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
