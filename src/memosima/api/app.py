from __future__ import annotations

import argparse
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from memosima import __version__
from memosima.api.admin_ui import ADMIN_UI_HTML
from memosima.api.security import require_admin
from memosima.api.webhooks import build_idempotency_key, extract_memo_uid
from memosima.core.config import AppConfig, ConfigError, ModelsConfig
from memosima.core.prompts import PromptTemplate, PromptsConfig, load_prompts_or_default
from memosima.db.store import Job, Store, TagCandidateRecord


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


class ReviewTagCandidateRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class PromptTemplateView(BaseModel):
    system: str = Field(min_length=1, max_length=12000)
    user: str = Field(min_length=1, max_length=12000)


class PromptsResponse(BaseModel):
    organize_memo: PromptTemplateView


class RetryJobRequest(BaseModel):
    prompt_override: PromptTemplateView | None = None


class HealthResponse(BaseModel):
    service: str = "memosima"
    version: str
    database: str
    workspace_id: str
    admin_token_configured: bool
    memos_base_url_configured: bool
    models_default_provider: str
    models_default_model: str
    models_api_key_present: bool


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
        provider = models.providers[models.default_provider]
        return HealthResponse(
            version=__version__,
            database=str(config.database_path),
            workspace_id=config.workspace_id,
            admin_token_configured=bool(config.admin_token),
            memos_base_url_configured=bool(config.memos_base_url),
            models_default_provider=models.default_provider,
            models_default_model=provider.default_model,
            models_api_key_present=provider.api_key_present,
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
        return PromptsResponse(organize_memo=_prompt_view(prompts.organize_memo))

    @app.put(
        "/admin/prompts/organize-memo",
        response_model=PromptTemplateView,
        dependencies=[Depends(require_admin)],
    )
    async def update_organize_memo_prompt(prompt: PromptTemplateView) -> PromptTemplateView:
        updated = PromptTemplate(system=prompt.system, user=prompt.user)
        PromptsConfig(organize_memo=updated).save(config.prompts_path)
        return _prompt_view(updated)

    @app.post(
        "/admin/jobs/{job_id}/retry",
        response_model=JobView,
        dependencies=[Depends(require_admin)],
    )
    async def retry_job(job_id: int, retry: RetryJobRequest | None = None) -> JobView:
        payload_patch = None
        if retry and retry.prompt_override:
            payload_patch = {"llm_prompt_override": retry.prompt_override.model_dump()}
        job = store.retry_job_with_payload(job_id, payload_patch)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return _job_view(job)

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

    @app.post(
        "/admin/tag-candidates/{candidate_id}/approve",
        response_model=TagCandidateView,
        dependencies=[Depends(require_admin)],
    )
    async def approve_tag_candidate(
        candidate_id: int,
        review: ReviewTagCandidateRequest | None = None,
    ) -> TagCandidateView:
        candidate = store.review_tag_candidate(
            candidate_id=candidate_id,
            status="approved",
            reviewer_note=review.note if review else None,
        )
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag candidate not found")
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
        return _tag_candidate_view(candidate)

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


def _prompt_view(prompt: PromptTemplate) -> PromptTemplateView:
    return PromptTemplateView(system=prompt.system, user=prompt.user)


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
