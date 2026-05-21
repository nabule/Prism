from __future__ import annotations

import pytest

from memosima.core.config import AppConfig, ConfigError, ModelsConfig
from memosima.core.prompts import PromptsConfig
from memosima.core.taxonomy import TaxonomyConfig

from helpers import app_config_text, models_config_text, prompts_config_text, taxonomy_config_text, write_yaml


def test_models_config_uses_openrouter_gemma_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())

    config = ModelsConfig.load(models_path)

    provider = config.providers[config.default_provider]
    assert config.default_provider == "openrouter"
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.api_key_env == "OPENROUTER_API_KEY"
    assert provider.default_model == "google/gemma-3-27b-it"
    assert provider.temperature == 0.1
    assert provider.max_tokens is None
    assert provider.response_format == "json_object"
    assert provider.extra_body == {}
    assert provider.api_key_present is True


def test_app_config_reads_secret_values_from_environment(tmp_path, monkeypatch):
    db_path = tmp_path / "sidecar.db"
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(db_path))
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    prompts_path = write_yaml(tmp_path / "prompts.yaml", prompts_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    monkeypatch.setenv("MEMOS_WEBHOOK_URL", "https://sidecar.example.com/webhooks/memos")

    config = AppConfig.load(app_path)

    assert config.database_path == db_path
    assert config.taxonomy_path == taxonomy_path
    assert config.prompts_path == prompts_path
    assert config.admin_token == "admin-token"
    assert config.memos_base_url == "http://memos.local"
    assert config.memos_api_token == "memos-token"
    assert config.memos_webhook_url == "https://sidecar.example.com/webhooks/memos"
    assert config.memos_ingestion_mode == "webhook"
    assert config.memos_poll_page_size == 20
    assert config.max_attachment_bytes == 1024 * 1024
    assert config.allowed_parse_extensions == (".txt", ".md")
    assert config.max_ai_active_tags == 5
    assert config.max_ai_candidate_tags == 2


def test_prompts_config_loads_and_renders_template(tmp_path):
    prompts_path = write_yaml(tmp_path / "prompts.yaml", prompts_config_text())

    config = PromptsConfig.load(prompts_path)
    rendered = config.organize_memo.render(
        {
            "active_tags": "- #项目/个人AI知识库",
            "local_plan_json": '{"active_tags":[]}',
            "content": "原始内容",
        }
    )

    assert "测试系统提示词" in rendered.system
    assert "- #项目/个人AI知识库" in rendered.system
    assert '{"active_tags":[]}' in rendered.user
    assert "原始内容" in rendered.user
    tag_rendered = config.tag_summary.render(
        {
            "tag": "#项目/个人AI知识库",
            "memo_count": "2",
            "memos_markdown": "- memo",
        }
    )
    assert "测试标签总结系统提示词" in tag_rendered.system
    assert "#项目/个人AI知识库" in tag_rendered.user


def test_taxonomy_config_builds_local_organization_plan(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)

    plan = taxonomy.build_organization_plan(
        "整理个人 AI 知识库开发记录 #AI知识库 #项目/新方向 #杂项"
    )

    assert plan.system_tags == ("#系统/原始记录", "#系统/标签待审核")
    assert plan.active_tags == ("#项目/个人AI知识库",)
    assert plan.disabled_tags == ("#杂项",)
    assert plan.candidate_tags[0].path == "#项目/新方向"
    assert plan.candidate_tags[0].parent_path == "#项目"
    assert plan.needs_clarification is False


def test_taxonomy_keeps_business_tag_leaf_unique_across_levels(tmp_path):
    taxonomy_path = write_yaml(
        tmp_path / "taxonomy.yaml",
        """
system_tags:
  original: "#系统/原始记录"
  pending_clarification: "#系统/待澄清"
  tag_candidate: "#系统/标签待审核"
business_tags:
  - path: "#项目/个人AI知识库"
    status: active
  - path: "#项目/数管"
    status: active
aliases: []
disabled: []
""",
    )
    taxonomy = TaxonomyConfig.load(taxonomy_path)

    plan = taxonomy.build_organization_plan("数管项目记录 #数管 #其他/数管")

    assert plan.active_tags == ("#项目/数管",)
    assert plan.candidate_tags == ()


def test_taxonomy_rejects_duplicate_business_tag_leaf_across_levels(tmp_path):
    taxonomy_path = write_yaml(
        tmp_path / "taxonomy.yaml",
        """
system_tags:
  original: "#系统/原始记录"
business_tags:
  - path: "#项目/数管"
    status: active
  - path: "#数管"
    status: active
aliases: []
disabled: []
""",
    )

    with pytest.raises(ConfigError, match="Duplicate business tag leaf"):
        TaxonomyConfig.load(taxonomy_path)


def test_taxonomy_config_marks_short_or_question_content_as_waiting_user(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)

    plan = taxonomy.build_organization_plan("这个怎么处理？")

    assert "#系统/待澄清" in plan.system_tags
    assert plan.needs_clarification is True
    assert plan.clarification_reason is not None
