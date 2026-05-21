from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from httpx import ASGITransport, AsyncClient

from memosima.memos.client import MemosClient, MemosClientError


@pytest.mark.asyncio
async def test_memos_client_reads_memo_and_creates_comment(monkeypatch):
    app = FastAPI()
    seen_headers: list[str | None] = []
    seen_webhook_payloads: list[dict[str, object]] = []
    seen_relation_payloads: list[dict[str, object]] = []

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/v1/users")
    async def create_user():
        return {"name": "users/test", "username": "test"}

    @app.post("/api/v1/auth/signin")
    async def sign_in():
        return {"accessToken": "access-token", "user": {"name": "users/test"}}

    @app.get("/api/v1/auth/me")
    async def get_current_user():
        return {"user": {"name": "users/test", "username": "test"}}

    @app.get("/api/v1/memos/{memo_uid}")
    async def get_memo(memo_uid: str):
        return {"name": f"memos/{memo_uid}", "content": "hello"}

    @app.get("/api/v1/memos")
    async def list_memos(pageSize: int, pageToken: str | None = None, filter: str | None = None):
        return {
            "memos": [{"name": "memos/abc", "content": "hello"}],
            "nextPageToken": "",
            "pageSize": pageSize,
            "pageToken": pageToken,
            "filter": filter,
        }

    @app.post("/api/v1/memos")
    async def create_memo():
        return {"name": "memos/new", "content": "created"}

    @app.post("/api/v1/memos/{memo_uid}/comments")
    async def create_comment(memo_uid: str):
        return {"name": f"memos/{memo_uid}/comments/1", "content": "comment"}

    @app.get("/api/v1/memos/{memo_uid}/relations")
    async def list_relations(memo_uid: str):
        return {"relations": [], "nextPageToken": ""}

    @app.patch("/api/v1/memos/{memo_uid}/relations")
    async def update_relations(memo_uid: str, payload: dict[str, object]):
        seen_relation_payloads.append(payload)
        return {}

    @app.get("/api/v1/users/{username}/webhooks")
    async def list_webhooks(username: str):
        return {"webhooks": [{"name": f"users/{username}/webhooks/1", "url": "https://old.example"}]}

    @app.post("/api/v1/users/{username}/webhooks")
    async def create_webhook(username: str, payload: dict[str, object]):
        seen_webhook_payloads.append(payload)
        return {
            "name": f"users/{username}/webhooks/2",
            "url": payload["url"],
            "displayName": payload["displayName"],
        }

    @app.patch("/api/v1/users/{username}/webhooks/{webhook_id}")
    async def update_webhook(username: str, webhook_id: str, payload: dict[str, object]):
        seen_webhook_payloads.append(payload)
        return {
            "name": f"users/{username}/webhooks/{webhook_id}",
            "url": payload["url"],
            "displayName": payload["displayName"],
        }

    @app.delete("/api/v1/users/{username}/webhooks/{webhook_id}")
    async def delete_webhook(username: str, webhook_id: str):
        return {}

    @app.get("/api/v1/users/{username}/personalAccessTokens")
    async def list_tokens(username: str):
        return {
            "personalAccessTokens": [
                {"name": f"users/{username}/personalAccessTokens/1", "description": "old"}
            ]
        }

    @app.post("/api/v1/users/{username}/personalAccessTokens")
    async def create_token(username: str, payload: dict[str, object]):
        seen_webhook_payloads.append(payload)
        return {
            "personalAccessToken": {
                "name": f"users/{username}/personalAccessTokens/2",
                "description": payload["description"],
            },
            "token": "pat-token",
        }

    @app.delete("/api/v1/users/{username}/personalAccessTokens/{token_id}")
    async def delete_token(username: str, token_id: str):
        return {}

    @app.get("/file/resources/{resource_id}")
    async def download_resource(resource_id: str):
        return Response(content=b"downloaded", media_type="text/plain")

    original_async_client = AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = ASGITransport(app=app)
        kwargs["base_url"] = "http://testserver"
        client = original_async_client(*args, **kwargs)
        original_request = client.request

        async def request_with_header_capture(method, url, **request_kwargs):
            seen_headers.append(request_kwargs["headers"].get("Authorization"))
            return await original_request(method, url, **request_kwargs)

        client.request = request_with_header_capture
        return client

    monkeypatch.setattr("memosima.memos.client.httpx.AsyncClient", fake_async_client)
    client = MemosClient("http://memos.local", "token")

    assert await client.get_health() == {"status": "ok"}
    assert await client.create_user(username="test", password="secret") == {
        "name": "users/test",
        "username": "test",
    }
    assert await client.sign_in(username="test", password="secret") == {
        "accessToken": "access-token",
        "user": {"name": "users/test"},
    }
    assert await client.get_current_user() == {"user": {"name": "users/test", "username": "test"}}
    assert await client.get_memo("abc") == {"name": "memos/abc", "content": "hello"}
    assert await client.list_memos(page_size=10) == {
        "memos": [{"name": "memos/abc", "content": "hello"}],
        "nextPageToken": "",
        "pageSize": 10,
        "pageToken": None,
        "filter": None,
    }
    assert await client.list_memos(
        page_size=10,
        page_token="next",
        filter_text='tag == "项目/个人AI知识库"',
    ) == {
        "memos": [{"name": "memos/abc", "content": "hello"}],
        "nextPageToken": "",
        "pageSize": 10,
        "pageToken": "next",
        "filter": 'tag == "项目/个人AI知识库"',
    }
    assert await client.create_memo("created") == {"name": "memos/new", "content": "created"}
    assert await client.create_comment("abc", "comment") == {
        "name": "memos/abc/comments/1",
        "content": "comment",
    }
    assert await client.list_memo_relations("abc") == {"relations": [], "nextPageToken": ""}
    assert await client.upsert_memo_reference_relation(
        source_memo_uid="abc",
        related_memo_uid="new",
    ) == {}
    assert await client.list_user_webhooks("users/test") == {
        "webhooks": [{"name": "users/test/webhooks/1", "url": "https://old.example"}]
    }
    assert await client.create_user_webhook(
        parent="users/test",
        url="https://sidecar.example.com/webhooks/memos",
        display_name="Memosima Sidecar",
    ) == {
        "name": "users/test/webhooks/2",
        "url": "https://sidecar.example.com/webhooks/memos",
        "displayName": "Memosima Sidecar",
    }
    assert await client.update_user_webhook(
        name="users/test/webhooks/1",
        url="https://sidecar.example.com/webhooks/memos",
        display_name="Memosima Sidecar Updated",
    ) == {
        "name": "users/test/webhooks/1",
        "url": "https://sidecar.example.com/webhooks/memos",
        "displayName": "Memosima Sidecar Updated",
    }
    await client.delete_user_webhook("users/test/webhooks/1")
    assert await client.list_personal_access_tokens("users/test") == {
        "personalAccessTokens": [{"name": "users/test/personalAccessTokens/1", "description": "old"}]
    }
    assert await client.create_personal_access_token(
        parent="users/test",
        description="Memosima Sidecar Worker",
        expires_in_days=0,
    ) == {
        "personalAccessToken": {
            "name": "users/test/personalAccessTokens/2",
            "description": "Memosima Sidecar Worker",
        },
        "token": "pat-token",
    }
    await client.delete_personal_access_token("users/test/personalAccessTokens/1")
    assert await client.download_resource("resources/file1") == b"downloaded"
    assert seen_webhook_payloads == [
        {
            "url": "https://sidecar.example.com/webhooks/memos",
            "displayName": "Memosima Sidecar",
        },
        {
            "name": "users/test/webhooks/1",
            "url": "https://sidecar.example.com/webhooks/memos",
            "displayName": "Memosima Sidecar Updated",
        },
        {"description": "Memosima Sidecar Worker", "expiresInDays": 0},
    ]
    assert seen_relation_payloads == [
        {
            "relations": [
                {
                    "memo": {"name": "memos/abc"},
                    "relatedMemo": {"name": "memos/new"},
                    "type": "REFERENCE",
                }
            ]
        }
    ]
    auth_header = " ".join(["Bearer", "token"])
    assert seen_headers == [
        auth_header,
        None,
        None,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
        auth_header,
    ]


@pytest.mark.asyncio
async def test_memos_client_error_includes_status_code(monkeypatch):
    app = FastAPI()

    @app.get("/api/v1/health")
    async def health():
        return JSONResponse({}, status_code=404)

    original_async_client = AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = ASGITransport(app=app)
        kwargs["base_url"] = "http://testserver"
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr("memosima.memos.client.httpx.AsyncClient", fake_async_client)
    client = MemosClient("http://memos.local", "token")

    with pytest.raises(MemosClientError) as exc_info:
        await client.get_health()

    assert exc_info.value.status_code == 404
