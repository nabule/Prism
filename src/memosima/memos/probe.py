from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

from memosima.core.config import AppConfig
from memosima.memos.client import MemosClient, MemosClientError


async def run_probe(
    *,
    config_path: str,
    memo_uid: str | None,
    create_memo_content: str | None,
    create_comment: bool,
    configure_webhook_url: str | None,
    webhook_display_name: str,
    create_pat: bool,
    pat_description: str,
    pat_expires_in_days: int,
    pat_output_env_file: str | None,
    reveal_pat_token: bool,
    verify_sidecar_url: str | None,
    verify_sidecar_token: str | None,
    verify_timeout_seconds: float,
    bootstrap_username: str | None,
    bootstrap_password: str | None,
    bootstrap_email: str,
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
        "bootstrap_user_created": False,
        "sign_in_ok": False,
        "memo_created": False,
        "memo_read_ok": False,
        "comment_created": False,
        "webhook_configured": False,
        "pat_created": False,
    }

    try:
        result["health"] = await client.get_health()
        result["health_ok"] = True
    except MemosClientError as exc:
        result["health_error"] = str(exc)
        if exc.status_code == 404:
            result["health_note"] = "Memos 0.28 does not expose /api/v1/health; continuing probe."
    except Exception as exc:
        result["health_error"] = str(exc)

    if bootstrap_username and bootstrap_password:
        try:
            user = await client.create_user(
                username=bootstrap_username,
                password=bootstrap_password,
                email=bootstrap_email,
            )
            result["bootstrap_user"] = _summarize_memo(user)
            result["bootstrap_user_created"] = True
        except MemosClientError as exc:
            result["bootstrap_user_error"] = str(exc)
            if exc.status_code in {400, 409, 500}:
                result["bootstrap_user_note"] = "User may already exist; continuing with sign-in."
        except Exception as exc:
            result["bootstrap_user_error"] = str(exc)
        sign_in = await client.sign_in(username=bootstrap_username, password=bootstrap_password)
        token = sign_in.get("accessToken")
        if isinstance(token, str) and token:
            client = MemosClient(
                base_url=config.memos_base_url,
                api_token=token,
                timeout_seconds=config.memos_timeout_seconds,
            )
            result["sign_in_ok"] = True
            result["signed_in_user"] = _summarize_memo(sign_in.get("user", {}))

    webhook_url = configure_webhook_url or config.memos_webhook_url
    if webhook_url:
        current_user = await client.get_current_user()
        result["current_user"] = _summarize_user_response(current_user)
        user_name = _extract_user_name(current_user)
        if not user_name:
            raise RuntimeError("Could not determine current Memos user for webhook configuration")
        result["webhook_owner"] = user_name
        webhook_result = await ensure_user_webhook(
            client,
            parent=user_name,
            url=webhook_url,
            display_name=webhook_display_name,
        )
        result["webhook"] = _summarize_memo(webhook_result["webhook"])
        result["webhook_action"] = webhook_result["action"]
        result["webhook_configured"] = True

    if create_pat:
        current_user = await client.get_current_user()
        result.setdefault("current_user", _summarize_user_response(current_user))
        user_name = _extract_user_name(current_user)
        if not user_name:
            raise RuntimeError("Could not determine current Memos user for PAT creation")
        pat_result = await client.create_personal_access_token(
            parent=user_name,
            description=pat_description,
            expires_in_days=pat_expires_in_days,
        )
        result["personal_access_token"] = _summarize_pat_response(pat_result)
        token = pat_result.get("token")
        if isinstance(token, str) and token:
            if pat_output_env_file:
                token_file = Path(pat_output_env_file)
                token_file.write_text(f"MEMOS_API_TOKEN={token}\n", encoding="utf-8")
                token_file.chmod(0o600)
                result["personal_access_token_env_file"] = str(token_file)
            if reveal_pat_token:
                result["personal_access_token_value"] = token
            else:
                result["personal_access_token_value_redacted"] = True
        result["pat_created"] = True

    if create_memo_content:
        memo = await client.create_memo(create_memo_content)
        result["created_memo"] = _summarize_memo(memo)
        result["memo_created"] = True
        name = memo.get("name")
        if isinstance(name, str) and name.startswith("memos/"):
            memo_uid = name.split("/", maxsplit=1)[1]

    if verify_sidecar_url:
        if not memo_uid:
            raise RuntimeError("Sidecar verification requires --memo-uid or --create-memo")
        result["sidecar_verification"] = await wait_for_sidecar_job(
            sidecar_url=verify_sidecar_url,
            admin_token=verify_sidecar_token or config.admin_token,
            memo_uid=memo_uid,
            timeout_seconds=verify_timeout_seconds,
        )

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


async def wait_for_sidecar_job(
    *,
    sidecar_url: str,
    admin_token: str | None,
    memo_uid: str,
    timeout_seconds: float,
) -> dict[str, object]:
    if not admin_token:
        raise RuntimeError("Sidecar admin token is required for webhook verification")

    deadline = time.monotonic() + timeout_seconds
    last_jobs: list[dict[str, object]] = []
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            response = await client.get(
                f"{sidecar_url.rstrip('/')}/admin/jobs",
                headers=headers,
                params={"limit": 50},
            )
            response.raise_for_status()
            data = response.json()
            jobs = data.get("jobs", [])
            if not isinstance(jobs, list):
                raise RuntimeError("Sidecar returned unexpected jobs response")
            last_jobs = [_as_dict(job) for job in jobs]
            matching = [job for job in last_jobs if _job_memo_uid(job) == memo_uid]
            succeeded = [job for job in matching if job.get("status") == "succeeded"]
            if succeeded:
                return {
                    "memo_uid": memo_uid,
                    "status": "succeeded",
                    "job": _summarize_job(succeeded[0]),
                }
            failed = [job for job in matching if job.get("status") == "failed"]
            if failed:
                return {
                    "memo_uid": memo_uid,
                    "status": "failed",
                    "job": _summarize_job(failed[0]),
                }
            if time.monotonic() >= deadline:
                return {
                    "memo_uid": memo_uid,
                    "status": "timeout",
                    "matching_jobs": [_summarize_job(job) for job in matching],
                    "recent_jobs": [_summarize_job(job) for job in last_jobs[:5]],
                }
            await asyncio.sleep(1)


async def ensure_user_webhook(
    client: MemosClient,
    *,
    parent: str,
    url: str,
    display_name: str,
) -> dict[str, object]:
    webhooks_response = await client.list_user_webhooks(parent)
    webhooks = webhooks_response.get("webhooks", [])
    if not isinstance(webhooks, list):
        raise RuntimeError("Memos returned unexpected webhooks response")

    same_url = [_as_dict(webhook) for webhook in webhooks if _as_dict(webhook).get("url") == url]
    if same_url:
        webhook = same_url[0]
        name = webhook.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError("Memos returned a webhook without name")
        if webhook.get("displayName") == display_name:
            return {"action": "unchanged", "webhook": webhook}
        updated = await client.update_user_webhook(
            name=name,
            url=url,
            display_name=display_name,
        )
        return {"action": "updated", "webhook": updated}

    created = await client.create_user_webhook(
        parent=parent,
        url=url,
        display_name=display_name,
    )
    return {"action": "created", "webhook": created}


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _job_memo_uid(job: dict[str, object]) -> str | None:
    payload = job.get("payload")
    if isinstance(payload, dict):
        memo_uid = payload.get("memo_uid")
        if isinstance(memo_uid, str):
            return memo_uid
    result = job.get("result")
    if isinstance(result, dict):
        memo_uid = result.get("memo_uid")
        if isinstance(memo_uid, str):
            return memo_uid
    return None


def _summarize_job(job: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for key in ("id", "type", "status", "idempotency_key", "retry_count", "created_at", "updated_at"):
        if key in job:
            summary[key] = job[key]
    memo_uid = _job_memo_uid(job)
    if memo_uid:
        summary["memo_uid"] = memo_uid
    error = job.get("error")
    if isinstance(error, str) and error:
        summary["error"] = error[:160]
    return summary


def _summarize_memo(value: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for key in ("name", "uid", "id", "url", "displayName", "displayTime", "createTime", "updateTime"):
        if key in value:
            summary[key] = value[key]
    content = value.get("content")
    if isinstance(content, str):
        summary["content_preview"] = content[:80]
    return summary or {"keys": sorted(value.keys())}


def _summarize_user_response(value: dict[str, object]) -> dict[str, object]:
    user = value.get("user")
    if isinstance(user, dict):
        return _summarize_memo(user)
    return _summarize_memo(value)


def _summarize_pat_response(value: dict[str, object]) -> dict[str, object]:
    pat = value.get("personalAccessToken")
    if not isinstance(pat, dict):
        pat = value.get("personal_access_token")
    if isinstance(pat, dict):
        summary: dict[str, object] = {}
        for key in ("name", "description", "createdAt", "expiresAt", "lastUsedAt"):
            if key in pat:
                summary[key] = pat[key]
        return summary or {"keys": sorted(pat.keys())}
    return {"keys": sorted(value.keys())}


def _extract_user_name(value: dict[str, object]) -> str | None:
    user = value.get("user")
    if isinstance(user, dict):
        name = user.get("name")
    else:
        name = value.get("name")
    return name if isinstance(name, str) and name else None


async def _run(args: argparse.Namespace) -> None:
    result = await run_probe(
        config_path=args.config,
        memo_uid=args.memo_uid,
        create_memo_content=args.create_memo,
        create_comment=args.create_comment,
        configure_webhook_url=args.configure_webhook_url,
        webhook_display_name=args.webhook_display_name,
        create_pat=args.create_pat,
        pat_description=args.pat_description,
        pat_expires_in_days=args.pat_expires_in_days,
        pat_output_env_file=args.pat_output_env_file,
        reveal_pat_token=args.reveal_pat_token,
        verify_sidecar_url=args.verify_sidecar_url,
        verify_sidecar_token=args.verify_sidecar_token,
        verify_timeout_seconds=args.verify_timeout_seconds,
        bootstrap_username=args.bootstrap_username,
        bootstrap_password=args.bootstrap_password,
        bootstrap_email=args.bootstrap_email,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe a real Memos API instance.")
    parser.add_argument("--config", default="config/app.yaml")
    parser.add_argument("--memo-uid")
    parser.add_argument("--create-memo")
    parser.add_argument("--create-comment", action="store_true")
    parser.add_argument("--configure-webhook-url")
    parser.add_argument("--webhook-display-name", default="Memosima Sidecar")
    parser.add_argument("--create-pat", action="store_true")
    parser.add_argument("--pat-description", default="Memosima Sidecar Worker")
    parser.add_argument("--pat-expires-in-days", type=int, default=0)
    parser.add_argument("--pat-output-env-file")
    parser.add_argument("--reveal-pat-token", action="store_true")
    parser.add_argument("--verify-sidecar-url")
    parser.add_argument("--verify-sidecar-token")
    parser.add_argument("--verify-timeout-seconds", type=float, default=30)
    parser.add_argument("--bootstrap-username")
    parser.add_argument("--bootstrap-password")
    parser.add_argument("--bootstrap-email", default="")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
