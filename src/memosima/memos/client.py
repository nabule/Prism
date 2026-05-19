from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class MemosClientError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class MemosClient:
    base_url: str
    api_token: str
    timeout_seconds: float = 15

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"}

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    async def get_health(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/health")

    async def create_user(
        self,
        *,
        username: str,
        password: str,
        email: str = "",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/users",
            json={"username": username, "password": password, "email": email},
            include_auth=False,
        )

    async def sign_in(self, *, username: str, password: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/auth/signin",
            json={"passwordCredentials": {"username": username, "password": password}},
            include_auth=False,
        )

    async def get_current_user(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/auth/me")

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

    async def list_user_webhooks(self, parent: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/{parent}/webhooks")

    async def create_user_webhook(
        self,
        *,
        parent: str,
        url: str,
        display_name: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/{parent}/webhooks",
            json={"url": url, "displayName": display_name},
        )

    async def update_user_webhook(
        self,
        *,
        name: str,
        url: str,
        display_name: str,
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/api/v1/{name}",
            json={"name": name, "url": url, "displayName": display_name},
        )

    async def delete_user_webhook(self, name: str) -> None:
        await self._raw_request("DELETE", f"/api/v1/{name}")

    async def list_personal_access_tokens(self, parent: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/{parent}/personalAccessTokens")

    async def create_personal_access_token(
        self,
        *,
        parent: str,
        description: str,
        expires_in_days: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/{parent}/personalAccessTokens",
            json={"description": description, "expiresInDays": expires_in_days},
        )

    async def delete_personal_access_token(self, name: str) -> None:
        await self._raw_request("DELETE", f"/api/v1/{name}")

    async def download_resource(self, resource_name: str) -> bytes:
        response = await self._raw_request("GET", resource_name)
        return response.content

    async def _request(
        self,
        method: str,
        path: str,
        *,
        include_auth: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        response = await self._raw_request(method, path, include_auth=include_auth, **kwargs)
        try:
            data = response.json()
        except ValueError as exc:
            raise MemosClientError(f"Memos returned non-JSON response for {path}") from exc
        if not isinstance(data, dict):
            raise MemosClientError(f"Memos returned unexpected response for {path}")
        return data

    async def _raw_request(
        self,
        method: str,
        path: str,
        *,
        include_auth: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = self._headers() if include_auth else {}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(
                method,
                self._url(path),
                headers=headers,
                **kwargs,
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MemosClientError(
                f"Memos request failed: {method} {path} -> {response.status_code}",
                status_code=response.status_code,
            ) from exc
        return response
