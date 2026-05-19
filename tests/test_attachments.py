from __future__ import annotations

from memosima.core.attachments import (
    ParsedAttachment,
    SkippedAttachment,
    extract_attachment_resources,
    parse_text_attachment,
)


def test_extract_attachment_resources_from_memo_resources():
    resources = extract_attachment_resources(
        {
            "resources": [
                {
                    "name": "resources/file1",
                    "filename": "note.txt",
                    "contentType": "text/plain",
                    "size": "5",
                }
            ]
        }
    )

    assert len(resources) == 1
    assert resources[0].name == "resources/file1"
    assert resources[0].filename == "note.txt"
    assert resources[0].content_type == "text/plain"
    assert resources[0].size == 5


def test_parse_text_attachment_accepts_txt_and_skips_unsupported():
    resource = extract_attachment_resources(
        {"resources": [{"name": "resources/file1", "filename": "note.txt", "contentType": "text/plain"}]}
    )[0]

    parsed = parse_text_attachment(
        resource=resource,
        data=b"hello\nworld\n",
        max_bytes=1024,
        allowed_extensions=(".txt", ".md"),
    )

    assert isinstance(parsed, ParsedAttachment)
    assert parsed.kind == "attachment_text"
    assert parsed.content_markdown == "hello\nworld\n"
    assert parsed.metadata["filename"] == "note.txt"

    skipped = parse_text_attachment(
        resource=resource,
        data=b"hello",
        max_bytes=4,
        allowed_extensions=(".txt", ".md"),
    )

    assert isinstance(skipped, SkippedAttachment)
    assert skipped.reason == "file_too_large"
