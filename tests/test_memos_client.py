from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from memosima.memos.client import MemosClient


@pytest.mark.asyncio
async def test_memos_client_reads_memo_and_creates_comment(monkeypatch):
    app = FastAPI()
    seen_headers: list[str | None] = []

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/memos/{memo_uid}")
    async def get_memo(memo_uid: str):
        return {"name": f"memos/{memo_uid}", "content": "hello"}

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
    assert await client.get_memo("abc") == {"name": "memos/abc", "content": "hello"}
    assert await client.create_comment("abc", "comment") == {
        "name": "memos/abc/comments/1",
        "content": "comment",
    }
    assert seen_headers == ["Bearer token", "Bearer token", "Bearer token"]

