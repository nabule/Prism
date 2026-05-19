from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


@dataclass(frozen=True)
class AttachmentResource:
    name: str
    filename: str
    content_type: str | None
    size: int | None


@dataclass(frozen=True)
class ParsedAttachment:
    resource: AttachmentResource
    kind: str
    content_markdown: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SkippedAttachment:
    resource: AttachmentResource
    reason: str
    metadata: dict[str, Any]


def extract_attachment_resources(memo: dict[str, Any]) -> tuple[AttachmentResource, ...]:
    raw_resources = memo.get("resources")
    if not isinstance(raw_resources, list):
        raw_resources = memo.get("attachments")
    if not isinstance(raw_resources, list):
        return ()

    resources: list[AttachmentResource] = []
    for item in raw_resources:
        if not isinstance(item, dict):
            continue
        name = _first_string(item, "name", "resourceName")
        filename = _first_string(item, "filename", "filenameSlug", "externalLink")
        if not name:
            continue
        resources.append(
            AttachmentResource(
                name=name,
                filename=filename or PurePosixPath(name).name,
                content_type=_first_string(item, "contentType", "type"),
                size=_first_int(item, "size", "sizeBytes"),
            )
        )
    return tuple(resources)


def parse_text_attachment(
    *,
    resource: AttachmentResource,
    data: bytes,
    max_bytes: int,
    allowed_extensions: tuple[str, ...],
) -> ParsedAttachment | SkippedAttachment:
    extension = _extension(resource.filename)
    metadata: dict[str, Any] = {
        "resource_name": resource.name,
        "filename": resource.filename,
        "content_type": resource.content_type,
        "size": resource.size if resource.size is not None else len(data),
        "extension": extension,
    }
    if extension not in allowed_extensions:
        return SkippedAttachment(resource, "extension_not_allowed", metadata)
    if extension not in {".txt", ".md"} and not _is_text_content_type(resource.content_type):
        return SkippedAttachment(resource, "parser_not_implemented", metadata)
    if len(data) > max_bytes:
        return SkippedAttachment(resource, "file_too_large", metadata)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return SkippedAttachment(resource, "decode_failed", metadata)
    content = text if extension == ".md" else _plain_text_to_markdown(text)
    return ParsedAttachment(
        resource=resource,
        kind="attachment_text",
        content_markdown=content.strip() + "\n",
        metadata=metadata,
    )


def _plain_text_to_markdown(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _extension(filename: str) -> str:
    if filename.endswith(".drawio.svg"):
        return ".drawio.svg"
    return PurePosixPath(filename).suffix.lower()


def _is_text_content_type(content_type: str | None) -> bool:
    return bool(content_type and content_type.startswith("text/"))


def _first_string(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _first_int(item: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None
