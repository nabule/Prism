from __future__ import annotations

import io
import zipfile

import pytest

from memosima.core.document_parsers import DocumentParserError, _extract_markdown_from_zip


def test_extract_markdown_from_mineru_zip_prefers_full_md():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("images/ignored.txt", "ignored")
        archive.writestr("result/other.md", "other")
        archive.writestr("result/full.md", "# 转换结果\n\n正文")

    assert _extract_markdown_from_zip(buffer.getvalue()) == "# 转换结果\n\n正文"


def test_extract_markdown_from_mineru_zip_requires_markdown():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("result/plain.txt", "正文")

    with pytest.raises(DocumentParserError, match="does not contain markdown"):
        _extract_markdown_from_zip(buffer.getvalue())
