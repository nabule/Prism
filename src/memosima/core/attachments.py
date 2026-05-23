import base64
from dataclasses import dataclass
import json
from pathlib import PurePosixPath
import re
from typing import Any
import urllib.parse
import xml.etree.ElementTree as ET
import zlib


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


def _strip_html(text: str) -> str:
    clean = re.sub(r'<[^>]*>', ' ', text)
    clean = clean.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    return ' '.join(clean.split())


def _decompress_drawio_diagram(diagram_text: str) -> str:
    try:
        decoded = base64.b64decode(diagram_text.strip())
        decompressed = zlib.decompress(decoded, -15)
        return urllib.parse.unquote(decompressed.decode("utf-8"))
    except Exception:
        return diagram_text


def _extract_drawio_xml_cells(element: ET.Element) -> list[str]:
    cells = []
    for cell in element.iter("mxCell"):
        value = cell.get("value")
        if value:
            cleaned = _strip_html(value)
            if cleaned:
                cells.append(cleaned)
    return cells


def parse_drawio(data: bytes) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "Error: Draw.io file is not valid UTF-8"
    
    try:
        root = ET.fromstring(text)
    except Exception:
        return "Error: Failed to parse Draw.io XML structure"
    
    cells = []
    diagrams = root.findall(".//diagram")
    if diagrams:
        for diag in diagrams:
            diag_text = diag.text
            if diag_text and diag_text.strip():
                decompressed_str = _decompress_drawio_diagram(diag_text)
                try:
                    diag_root = ET.fromstring(decompressed_str)
                    cells.extend(_extract_drawio_xml_cells(diag_root))
                except Exception:
                    found = re.findall(r'value="([^"]*)"', decompressed_str)
                    for val in found:
                        cleaned = _strip_html(urllib.parse.unquote(val) if '%' in val else val)
                        if cleaned:
                            cells.append(cleaned)
            else:
                cells.extend(_extract_drawio_xml_cells(diag))
    else:
        cells.extend(_extract_drawio_xml_cells(root))
        
    if not cells:
        return "Draw.io 图标 (无文本内容)"
    
    markdown_lines = ["# Draw.io 流程图组件清单\n"]
    for i, cell_val in enumerate(cells, 1):
        markdown_lines.append(f"{i}. {cell_val}")
    return "\n".join(markdown_lines)


def parse_mind_elixir(data: bytes) -> str:
    try:
        content = json.loads(data.decode("utf-8"))
    except Exception as exc:
        return f"Error: Mind Elixir file is not valid JSON ({exc})"
    
    node_data = content.get("nodeData") if isinstance(content, dict) else None
    if not isinstance(node_data, dict):
        node_data = content if isinstance(content, dict) else {}
        
    if not node_data:
        return "思维导图 (空)"
    
    lines = ["# 思维导图大纲\n"]
    
    def _traverse(node: dict, depth: int = 0) -> None:
        topic = node.get("topic")
        if isinstance(topic, str) and topic.strip():
            lines.append("  " * depth + f"- {topic.strip()}")
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    _traverse(child, depth + 1)
                    
    _traverse(node_data, 0)
    return "\n".join(lines)


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
        
    if extension in {".drawio", ".drawio.svg"}:
        if len(data) > max_bytes:
            return SkippedAttachment(resource, "file_too_large", metadata)
        parsed_content = parse_drawio(data)
        return ParsedAttachment(
            resource=resource,
            kind="attachment_drawio",
            content_markdown=parsed_content.strip() + "\n",
            metadata=metadata,
        )
        
    if extension == ".json":
        if len(data) > max_bytes:
            return SkippedAttachment(resource, "file_too_large", metadata)
        parsed_content = parse_mind_elixir(data)
        return ParsedAttachment(
            resource=resource,
            kind="attachment_mind_elixir",
            content_markdown=parsed_content.strip() + "\n",
            metadata=metadata,
        )

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


def is_document_attachment(resource: AttachmentResource) -> bool:
    return _extension(resource.filename) in {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf"}


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
