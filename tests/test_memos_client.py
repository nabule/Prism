from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from memosima.memos.client import MemosClient, MemosClientError


@pytest.mark.asyncio
async def test_memos_client_reads_memo_and_creates_comment(monkeypatch):
    app = FastAPI()
    seen_headers: list[str | None] = []

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/v1/users")
    async def create_user():
        return {"name": "users/test", "username": "test"}

    @app.post("/api/v1/auth/signin")
    async def sign_in():
        return {"accessToken": "access-token", "user": {"name": "users/test"}}

    @app.get("/api/v1/memos/{memo_uid}")
    async def get_memo(memo_uid: str):
        return {"name": f"memos/{memo_uid}", "content": "hello"}

    @app.post("/api/v1/memos")
    async def create_memo():
        return {"name": "memos/new", "content": "created"}

    @app.post("/api/v1/memos/{memo_uid}/comments")
    async def create_comment(memo_uid: str):
        return {"name": f"memos/{memo_uid}/comments/1", "content": "comment"}

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
    assert await client.get_memo("abc") == {"name": "memos/abc", "content": "hello"}
    assert await client.create_memo("created") == {"name": "memos/new", "content": "created"}
    assert await client.create_comment("abc", "comment") == {
        "name": "memos/abc/comments/1",
        "content": "comment",
    }
    assert seen_headers == [
        "Bearer token",
        None,
        None,
        "Bearer token",
        "Bearer token",
        "Bearer token",
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
