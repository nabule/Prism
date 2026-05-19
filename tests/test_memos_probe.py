from __future__ import annotations

import pytest

from memosima.memos.probe import ensure_user_webhook, wait_for_sidecar_job


@pytest.mark.asyncio
async def test_ensure_user_webhook_creates_missing_webhook():
    class FakeClient:
        async def list_user_webhooks(self, parent):
            assert parent == "users/test"
            return {"webhooks": []}

        async def create_user_webhook(self, *, parent, url, display_name):
            return {
                "name": f"{parent}/webhooks/new",
                "url": url,
                "displayName": display_name,
            }

    result = await ensure_user_webhook(
        FakeClient(),
        parent="users/test",
        url="https://sidecar.example.com/webhooks/memos",
        display_name="Memosima Sidecar",
    )

    assert result == {
        "action": "created",
        "webhook": {
            "name": "users/test/webhooks/new",
            "url": "https://sidecar.example.com/webhooks/memos",
            "displayName": "Memosima Sidecar",
        },
    }


@pytest.mark.asyncio
async def test_ensure_user_webhook_updates_existing_display_name():
    class FakeClient:
        async def list_user_webhooks(self, parent):
            return {
                "webhooks": [
                    {
                        "name": f"{parent}/webhooks/old",
                        "url": "https://sidecar.example.com/webhooks/memos",
                        "displayName": "Old",
                    }
                ]
            }

        async def update_user_webhook(self, *, name, url, display_name):
            return {"name": name, "url": url, "displayName": display_name}

    result = await ensure_user_webhook(
        FakeClient(),
        parent="users/test",
        url="https://sidecar.example.com/webhooks/memos",
        display_name="Memosima Sidecar",
    )

    assert result["action"] == "updated"
    assert result["webhook"] == {
        "name": "users/test/webhooks/old",
        "url": "https://sidecar.example.com/webhooks/memos",
        "displayName": "Memosima Sidecar",
    }


@pytest.mark.asyncio
async def test_wait_for_sidecar_job_returns_succeeded_job(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "jobs": [
                    {
                        "id": 1,
                        "type": "process_memo",
                        "status": "succeeded",
                        "idempotency_key": "memo.created:abc:v1",
                        "payload": {"memo_uid": "abc"},
                        "result": {"memo_uid": "abc"},
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, *, headers, params):
            assert url == "https://sidecar.example.com/admin/jobs"
            assert headers == {"Authorization": "Bearer token"}
            assert params == {"limit": 50}
            return FakeResponse()

    monkeypatch.setattr("memosima.memos.probe.httpx.AsyncClient", FakeAsyncClient)

    result = await wait_for_sidecar_job(
        sidecar_url="https://sidecar.example.com",
        admin_token="token",
        memo_uid="abc",
        timeout_seconds=0,
    )

    assert result["status"] == "succeeded"
    assert result["job"]["id"] == 1
    assert result["job"]["memo_uid"] == "abc"
