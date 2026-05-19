from __future__ import annotations

import argparse
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from memosima import __version__
from memosima.api.security import require_admin
from memosima.api.webhooks import build_idempotency_key, extract_memo_uid
from memosima.core.config import AppConfig, ConfigError, ModelsConfig
from memosima.db.store import Job, Store


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

    @app.post(
        "/admin/jobs/{job_id}/retry",
        response_model=JobView,
        dependencies=[Depends(require_admin)],
    )
    async def retry_job(job_id: int) -> JobView:
        job = store.retry_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return _job_view(job)

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
