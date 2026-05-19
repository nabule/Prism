from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class MemosClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class MemosClient:
    base_url: str
    api_token: str
    timeout_seconds: float = 15

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"}

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    async def get_memo(self, memo_uid: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/memos/{memo_uid}")

    async def create_memo(self, content: str, visibility: str = "PRIVATE") -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/memos",
            json={"content": content, "visibility": visibility},
        )

    async def create_comment(self, memo_uid: str, content: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/memos/{memo_uid}/comments",
            json={"content": content},
        )

    async def download_resource(self, resource_name: str) -> bytes:
        response = await self._raw_request("GET", resource_name)
        return response.content

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = await self._raw_request(method, path, **kwargs)
        try:
            data = response.json()
        except ValueError as exc:
            raise MemosClientError(f"Memos returned non-JSON response for {path}") from exc
        if not isinstance(data, dict):
            raise MemosClientError(f"Memos returned unexpected response for {path}")
        return data

    async def _raw_request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(
                method,
                self._url(path),
                headers=self._headers(),
                **kwargs,
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MemosClientError(
                f"Memos request failed: {method} {path} -> {response.status_code}"
            ) from exc
        return response

