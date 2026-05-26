from __future__ import annotations

from memosima.core.summary import build_summary_memo_content
from memosima.core.taxonomy import TaxonomyConfig

from helpers import taxonomy_config_text, write_yaml


def test_build_summary_memo_content_keeps_business_tags_as_plain_text(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)
    plan = taxonomy.build_organization_plan("个人 AI 知识库开发记录 #AI知识库 #项目/新方向")

    content = build_summary_memo_content(
        source_memo_uid="abc123",
        source_content="个人 AI 知识库开发记录 #AI知识库 #项目/新方向",
        organization_plan=plan,
        taxonomy=taxonomy,
        show_candidate_tags=True,
    )

    assert content.startswith("#系统/AI整理")
    assert "#系统/原始记录" not in content
    assert "#系统/标签待审核" in content
    first_line = content.splitlines()[0]
    assert "#项目/个人AI知识库" in first_line
    assert "#项目/新方向" not in content
    assert "已使用：项目/个人AI知识库" in content
    assert "待审核：项目/新方向" in content
    assert "## AI整理：个人 AI 知识库开发记录 #AI知识库 项目/新方向" in content
    assert "来源 memo UID：abc123" in content
    assert "> 个人 AI 知识库开发记录 #AI知识库 项目/新方向" in content


def test_build_summary_memo_content_can_append_admin_links(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)
    plan = taxonomy.build_organization_plan("个人 AI 知识库开发记录 #AI知识库")

    content = build_summary_memo_content(
        source_memo_uid="abc123",
        source_content="个人 AI 知识库开发记录 #AI知识库",
        organization_plan=plan,
        taxonomy=taxonomy,
        admin_links="### 管理\n\n- [打开管理界面](http://localhost:5230/admin/ui)",
    )

    assert "### 管理" in content
    assert "http://localhost:5230/admin/ui" in content


def test_build_summary_memo_content_can_hide_candidate_tags_from_memos(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)
    plan = taxonomy.build_organization_plan("个人 AI 知识库开发记录 #AI知识库 #项目/新方向")

    content = build_summary_memo_content(
        source_memo_uid="abc123",
        source_content="个人 AI 知识库开发记录 #AI知识库 #项目/新方向",
        organization_plan=plan,
        taxonomy=taxonomy,
        show_candidate_tags=False,
    )

    first_line = content.splitlines()[0]
    assert "#系统/标签待审核" in first_line
    assert "#项目/新方向" not in content
    assert "#项目/个人AI知识库" in first_line
    assert "已使用：项目/个人AI知识库" in content
    assert "待审核：项目/新方向" in content
    assert "> 个人 AI 知识库开发记录 #AI知识库 项目/新方向" in content


def test_tag_path_matches():
    from memosima.api.app import _tag_path_matches
    
    # 1. 完全一致
    assert _tag_path_matches("project/deploy", "project/deploy")
    assert _tag_path_matches("#project/deploy", "project/deploy")
    
    # 2. 前缀级联匹配
    assert _tag_path_matches("project/deploy/test", "project/deploy")
    assert _tag_path_matches("#project/deploy/test", "project/deploy")
    
    # 3. 后缀匹配
    assert _tag_path_matches("project/deploy", "deploy")
    assert _tag_path_matches("project/deploy/test", "test")
    assert _tag_path_matches("#project/deploy", "deploy")
    
    # 4. 中间路径段匹配
    assert _tag_path_matches("project/deploy/test/daily", "deploy/test")
    assert _tag_path_matches("project/deploy/test/daily", "test")
    
    # 5. 不匹配的情况
    assert not _tag_path_matches("project/deploy", "depl")
    assert not _tag_path_matches("project/deploy", "project/de")
    assert not _tag_path_matches("project/deploy", "oy")


def test_extract_title_and_cleanup_summary():
    from memosima.api.app import _extract_title_and_cleanup_summary
    
    dirty_summary = """# 非结构化文档分类分级项目整体总结

好的，收到您的指令。我将为标签 #技术/分类分级系统 和 #项目/非结构化文档分类分级 下的 8 条 memo 生成一份整体总结。

经检查，memo列表中未包含任何URL，因此不涉及获取真实内容并分析的操作。

现在为您呈现总结：

## 1. 总览
本专题针对非结构化文档分类分级...
"""
    title, cleaned = _extract_title_and_cleanup_summary(dirty_summary)
    
    assert title == "非结构化文档分类分级项目整体总结"
    assert "好的" not in cleaned
    assert "经检查" not in cleaned
    assert "现在为您呈现" not in cleaned
    assert "## 1. 总览" in cleaned


