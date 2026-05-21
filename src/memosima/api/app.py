from __future__ import annotations

import argparse
import os
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
from memosima.llm.provider import OpenAICompatibleClient
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


class ReviewTagCandidateRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class PromptTemplateView(BaseModel):
    system: str = Field(min_length=1, max_length=12000)
    user: str = Field(min_length=1, max_length=12000)


class PromptsResponse(BaseModel):
    organize_memo: PromptTemplateView
    tag_summary: PromptTemplateView


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
        return PromptsResponse(
            organize_memo=_prompt_view(prompts.organize_memo),
            tag_summary=_prompt_view(prompts.tag_summary),
        )

    @app.put(
        "/admin/prompts/organize-memo",
        response_model=PromptTemplateView,
        dependencies=[Depends(require_admin)],
    )
    async def update_organize_memo_prompt(prompt: PromptTemplateView) -> PromptTemplateView:
        updated = PromptTemplate(system=prompt.system, user=prompt.user)
        prompts = load_prompts_or_default(config.prompts_path)
        PromptsConfig(organize_memo=updated, tag_summary=prompts.tag_summary).save(config.prompts_path)
        return _prompt_view(updated)

    @app.put(
        "/admin/prompts/tag-summary",
        response_model=PromptTemplateView,
        dependencies=[Depends(require_admin)],
    )
    async def update_tag_summary_prompt(prompt: PromptTemplateView) -> PromptTemplateView:
        updated = PromptTemplate(system=prompt.system, user=prompt.user)
        prompts = load_prompts_or_default(config.prompts_path)
        PromptsConfig(organize_memo=prompts.organize_memo, tag_summary=updated).save(config.prompts_path)
        return _prompt_view(updated)

    @app.post(
        "/admin/tag-summaries",
        response_model=TagSummaryResponse,
        dependencies=[Depends(require_admin)],
    )
    async def create_tag_summary(request: TagSummaryRequest) -> TagSummaryResponse:
        if not config.memos_base_url or not config.memos_api_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Memos is not configured")
        provider = models.providers[models.default_provider]
        api_key = os.getenv(provider.api_key_env)
        if not api_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="LLM key is not configured")

        memos_client = MemosClient(
            base_url=config.memos_base_url,
            api_token=config.memos_api_token,
            timeout_seconds=config.memos_timeout_seconds,
        )
        memos = await _list_memos_for_tag(memos_client, tag=request.tag, limit=request.limit)
        if not memos:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No memos found for tag")

        memos_markdown = _memos_markdown(memos)
        prompts = load_prompts_or_default(config.prompts_path)
        llm_client = OpenAICompatibleClient(
            provider=provider,
            api_key=api_key,
            timeout_seconds=config.memos_timeout_seconds,
        )
        summary = await llm_client.summarize_tag(
            tag=request.tag,
            memos_markdown=memos_markdown,
            memo_count=len(memos),
            prompt_template=prompts.tag_summary,
        )
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


def _memos_tag(tag: str) -> str:
    return tag.strip().removeprefix("#")


def _memo_matches_tag(memo: dict[str, Any], tag: str) -> bool:
    normalized = _memos_tag(tag)
    tags = memo.get("tags")
    if isinstance(tags, list) and normalized in {str(item).lstrip("#") for item in tags}:
        return True
    content = memo.get("content")
    return isinstance(content, str) and f"#{normalized}" in content


async def _list_memos_for_tag(memos_client: MemosClient, *, tag: str, limit: int) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    page_token: str | None = None
    scanned = 0
    page_size = min(max(limit, 20), 100)
    max_scan = max(limit * 5, page_size)

    while len(matched) < limit and scanned < max_scan:
        response = await memos_client.list_memos(page_size=page_size, page_token=page_token)
        raw_memos = response.get("memos", [])
        if not isinstance(raw_memos, list):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Memos returned invalid response")

        for memo in raw_memos:
            if isinstance(memo, dict) and not _is_sidecar_generated_memo(memo):
                scanned += 1
                if _memo_matches_tag(memo, tag):
                    matched.append(memo)
                    if len(matched) >= limit:
                        break

        next_page_token = response.get("nextPageToken")
        if not isinstance(next_page_token, str) or not next_page_token:
            break
        page_token = next_page_token

    return matched


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
        name = str(memo.get("name", ""))
        create_time = str(memo.get("createTime", ""))
        content = str(memo.get("content", "")).strip()
        blocks.append(f"### {index}. {name}\n\n创建时间：{create_time}\n\n{content}")
    return "\n\n---\n\n".join(blocks)


def _tag_summary_memo_content(*, tag: str, summary: str, memos: list[dict[str, Any]]) -> str:
    references = "\n".join(f"- {str(memo.get('name', '')).removeprefix('memos/')}" for memo in memos)
    return (
        f"#系统/标签总结 {tag}\n\n"
        f"# {tag} 整体总结\n\n"
        f"{summary.strip()}\n\n"
        "## 相关 memo UID\n\n"
        f"{references}\n"
    )


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
