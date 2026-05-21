from __future__ import annotations

import asyncio
import hashlib
import io
import os
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Protocol

import httpx

from memosima.core.attachments import AttachmentResource, ParsedAttachment
from memosima.core.config import AppConfig


class DocumentParserError(RuntimeError):
    pass


class DocumentParser(Protocol):
    async def parse(self, *, resource: AttachmentResource, data: bytes) -> ParsedAttachment:
        pass


@dataclass(frozen=True)
class MinerUDocumentParser:
    api_token: str
    base_url: str = "https://mineru.net"
    timeout_seconds: float = 60
    poll_interval_seconds: float = 3
    max_polls: int = 60
    model_version: str = "vlm"
    language: str = "ch"
    enable_table: bool = True
    enable_formula: bool = True
    is_ocr: bool = False

    async def parse(self, *, resource: AttachmentResource, data: bytes) -> ParsedAttachment:
        data_id = _data_id(resource, data)
        batch_id, file_url = await self._create_upload_url(resource=resource, data_id=data_id)
        await self._upload_file(file_url=file_url, data=data)
        result = await self._wait_result(batch_id=batch_id, data_id=data_id, filename=resource.filename)
        markdown = await self._download_markdown(result)
        metadata = {
            "provider": "mineru",
            "resource_name": resource.name,
            "filename": resource.filename,
            "content_type": resource.content_type,
            "size": resource.size if resource.size is not None else len(data),
            "extension": _extension(resource.filename),
            "batch_id": batch_id,
            "data_id": data_id,
            "state": result.get("state"),
            "model_version": self.model_version,
        }
        return ParsedAttachment(
            resource=resource,
            kind="attachment_document",
            content_markdown=markdown.strip() + "\n",
            metadata=metadata,
        )

    async def _create_upload_url(self, *, resource: AttachmentResource, data_id: str) -> tuple[str, str]:
        payload = {
            "model_version": self.model_version,
            "language": self.language,
            "enable_table": self.enable_table,
            "enable_formula": self.enable_formula,
            "files": [
                {
                    "name": PurePosixPath(resource.filename).name,
                    "data_id": data_id,
                    "is_ocr": self.is_ocr,
                }
            ],
        }
        data = await self._request_json("POST", "/api/v4/file-urls/batch", json=payload)
        batch_id = _required_string(data, "batch_id")
        file_urls = data.get("file_urls")
        if not isinstance(file_urls, list) or not file_urls or not isinstance(file_urls[0], str):
            raise DocumentParserError("MinerU upload-url response is missing file_urls")
        return batch_id, file_urls[0]

    async def _upload_file(self, *, file_url: str, data: bytes) -> None:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.put(file_url, content=data)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DocumentParserError(f"MinerU file upload failed: {response.status_code}") from exc

    async def _wait_result(self, *, batch_id: str, data_id: str, filename: str) -> dict[str, Any]:
        for _ in range(self.max_polls):
            data = await self._request_json("GET", f"/api/v4/extract-results/batch/{batch_id}")
            result = _find_extract_result(data, data_id=data_id, filename=filename)
            if result is None:
                await asyncio.sleep(self.poll_interval_seconds)
                continue
            state = str(result.get("state", "")).lower()
            if state == "done":
                return result
            if state in {"failed", "error"}:
                error_message = result.get("err_msg") or result.get("error") or "unknown error"
                raise DocumentParserError(f"MinerU document parse failed: {error_message}")
            await asyncio.sleep(self.poll_interval_seconds)
        raise DocumentParserError("MinerU document parse timed out")

    async def _download_markdown(self, result: dict[str, Any]) -> str:
        zip_url = _required_string(result, "full_zip_url")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(zip_url)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DocumentParserError(f"MinerU result download failed: {response.status_code}") from exc
        return _extract_markdown_from_zip(response.content)

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(method, _join_url(self.base_url, path), headers=headers, **kwargs)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DocumentParserError(f"MinerU request failed: {method} {path} -> {response.status_code}") from exc
        try:
            raw = response.json()
        except ValueError as exc:
            raise DocumentParserError("MinerU returned non-JSON response") from exc
        if not isinstance(raw, dict):
            raise DocumentParserError("MinerU returned unexpected response shape")
        if raw.get("code") not in (0, "0", None):
            message = raw.get("msg") or raw.get("message") or "unknown error"
            raise DocumentParserError(f"MinerU request failed: {message}")
        data = raw.get("data", raw)
        if not isinstance(data, dict):
            raise DocumentParserError("MinerU response data has unexpected shape")
        return data


def create_document_parser(config: AppConfig) -> DocumentParser | None:
    provider = config.document_parser_provider.lower().strip()
    if provider in {"", "disabled", "none"}:
        return None
    if provider != "mineru":
        raise DocumentParserError(f"Unsupported document parser provider: {config.document_parser_provider}")
    token = os.getenv(config.document_parser_token_env)
    if not token:
        return None
    return MinerUDocumentParser(
        api_token=token,
        base_url=config.document_parser_base_url,
        timeout_seconds=config.document_parser_timeout_seconds,
        poll_interval_seconds=config.document_parser_poll_interval_seconds,
        max_polls=config.document_parser_max_polls,
        model_version=config.mineru_model_version,
        language=config.mineru_language,
        enable_table=config.mineru_enable_table,
        enable_formula=config.mineru_enable_formula,
        is_ocr=config.mineru_is_ocr,
    )


def _find_extract_result(data: dict[str, Any], *, data_id: str, filename: str) -> dict[str, Any] | None:
    results = data.get("extract_result")
    if not isinstance(results, list):
        return None
    fallback: dict[str, Any] | None = None
    filename_name = PurePosixPath(filename).name
    for item in results:
        if not isinstance(item, dict):
            continue
        if fallback is None:
            fallback = item
        if item.get("data_id") == data_id or item.get("file_name") == filename_name:
            return item
    return fallback


def _extract_markdown_from_zip(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            markdown_name = next((name for name in names if name.endswith("/full.md") or name == "full.md"), None)
            if markdown_name is None:
                markdown_name = next((name for name in names if name.endswith(".md")), None)
            if markdown_name is None:
                raise DocumentParserError("MinerU result zip does not contain markdown")
            return archive.read(markdown_name).decode("utf-8")
    except zipfile.BadZipFile as exc:
        raise DocumentParserError("MinerU result is not a valid zip file") from exc
    except UnicodeDecodeError as exc:
        raise DocumentParserError("MinerU markdown decode failed") from exc


def _data_id(resource: AttachmentResource, data: bytes) -> str:
    payload = resource.name.encode("utf-8") + b"\0" + data
    return hashlib.sha256(payload).hexdigest()[:32]


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise DocumentParserError(f"MinerU response is missing {key}")
    return value


def _extension(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower()


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
