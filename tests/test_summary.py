from __future__ import annotations

from memosima.core.summary import build_summary_memo_content
from memosima.core.taxonomy import TaxonomyConfig

from helpers import taxonomy_config_text, write_yaml


def test_build_summary_memo_content_contains_source_tags_and_excerpt(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)
    plan = taxonomy.build_organization_plan("个人 AI 知识库开发记录 #AI知识库 #项目/新方向")

    content = build_summary_memo_content(
        source_memo_uid="abc123",
        source_content="个人 AI 知识库开发记录 #AI知识库 #项目/新方向",
        organization_plan=plan,
        taxonomy=taxonomy,
    )

    assert content.startswith("#系统/AI整理")
    assert "#系统/原始记录" in content
    assert "#系统/标签待审核" in content
    assert "#项目/个人AI知识库" in content
    assert "#项目/新方向" in content
    assert "来源 memo：memos/abc123" in content
    assert "> 个人 AI 知识库开发记录 #AI知识库 #项目/新方向" in content
