from __future__ import annotations

import os

import pytest

from memosima.core.config import AppConfig, ConfigError, ModelsConfig
from memosima.core.prompts import PromptsConfig
from memosima.core.taxonomy import TaxonomyConfig

from helpers import app_config_text, models_config_text, prompts_config_text, taxonomy_config_text, write_yaml


def test_models_config_uses_openrouter_gemma_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
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
    deepseek = config.providers["deepseek"]
    assert deepseek.base_url == "https://api.deepseek.com"
    assert deepseek.api_key_env == "DEEPSEEK_API_KEY"
    assert deepseek.default_model == "deepseek-v4-flash"
    assert deepseek.response_format == "json_object"
    assert deepseek.extra_body == {"thinking": {"type": "disabled"}}
    assert deepseek.api_key_present is True


def test_repository_models_config_defaults_to_deepseek_v4_flash(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    config = ModelsConfig.load("config/models.yaml")

    provider = config.providers[config.default_provider]
    assert config.default_provider == "deepseek"
    assert provider.base_url == "https://api.deepseek.com"
    assert provider.api_key_env == "DEEPSEEK_API_KEY"
    assert provider.default_model == "deepseek-v4-flash"
    assert provider.extra_body == {"thinking": {"type": "enabled"}}
    assert provider.api_key_present is True


def test_models_config_reads_api_key_presence_from_local_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "old-secret")
    models_path = write_yaml(
        tmp_path / "models.yaml",
        """
default_provider: deepseek
providers:
  deepseek:
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    default_model: deepseek-v4-flash
    temperature: 0.2
    max_tokens:
    response_format: json_object
    extra_body: {}
""",
    )
    (tmp_path / ".env.local").write_text("DEEPSEEK_API_KEY=local-secret\n", encoding="utf-8")

    config = ModelsConfig.load(models_path)

    assert config.providers["deepseek"].api_key_present is True
    assert os.getenv("DEEPSEEK_API_KEY") == "local-secret"


def test_app_config_reads_secret_values_from_environment(tmp_path, monkeypatch):
    db_path = tmp_path / "sidecar.db"
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(db_path))
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    prompts_path = write_yaml(tmp_path / "prompts.yaml", prompts_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    monkeypatch.setenv("MEMOS_WEBHOOK_URL", "https://sidecar.example.com/webhooks/memos")
    monkeypatch.setenv("REMINDER_WEBHOOK_URL", "https://notify.example.com/reminders")

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
    assert config.memos_show_candidate_tags is False
    assert config.memos_admin_entry_enabled is True
    assert config.memos_admin_entry_title == "Memosima 管理入口"
    assert config.memos_admin_entry_visibility == "PRIVATE"
    assert config.max_attachment_bytes == 1024 * 1024
    assert config.allowed_parse_extensions == (".txt", ".md")
    assert config.max_ai_active_tags == 5
    assert config.max_ai_candidate_tags == 2
    assert config.document_parser_provider == "mineru"
    assert config.document_parser_token_env == "MINERU_API_TOKEN"
    assert config.document_parser_base_url == "https://mineru.net"
    assert config.document_parser_timeout_seconds == 60
    assert config.document_parser_poll_interval_seconds == 3
    assert config.document_parser_max_polls == 60
    assert config.mineru_model_version == "vlm"
    assert config.mineru_language == "ch"
    assert config.mineru_enable_table is True
    assert config.mineru_enable_formula is True
    assert config.mineru_is_ocr is False
    assert config.reminders_enabled is True
    assert config.reminders_trigger_tag == "#提醒"
    assert config.reminders_webhook_url_env == "REMINDER_WEBHOOK_URL"
    assert config.reminders_webhook_url == "https://notify.example.com/reminders"
    assert config.reminders_confidence_threshold == 0.75
    assert config.reminders_request_timeout_seconds == 10


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


def test_prompts_config_loads_provider_and_reminder_template(tmp_path):
    prompts_path = write_yaml(
        tmp_path / "prompts.yaml",
        prompts_config_text()
        + """
reminder_extraction:
  provider: 
  system: |-
    自定义提醒系统 {trigger_tag}
  user: |-
    自定义提醒用户
    {now}
    {timezone}
    {content}
""",
    )

    config = PromptsConfig.load(prompts_path)
    rendered = config.reminder_extraction.render(
        {
            "trigger_tag": "#提醒",
            "now": "2026-05-23T12:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "content": "#提醒 明天 09:30 提交周报",
        }
    )

    assert config.organize_memo.provider is None
    assert config.tag_summary.provider is None
    assert config.reminder_extraction.provider == ""
    assert "自定义提醒系统 #提醒" == rendered.system
    assert "2026-05-23T12:00:00+08:00" in rendered.user
    assert "Asia/Shanghai" in rendered.user
    assert "#提醒 明天 09:30 提交周报" in rendered.user


def test_prompts_config_save_preserves_provider_fields(tmp_path):
    prompts_path = write_yaml(
        tmp_path / "prompts.yaml",
        """
organize_memo:
  provider: deepseek
  system: 整理系统 {active_tags}
  user: 整理用户 {content}
tag_summary:
  provider: openai
  system: 标签系统
  user: 标签用户 {tag} {memos_markdown}
reminder_extraction:
  provider: 
  system: 提醒系统
  user: 提醒用户 {content}
""",
    )

    config = PromptsConfig.load(prompts_path)
    config.save(prompts_path)
    loaded = PromptsConfig.load(prompts_path)

    assert loaded.organize_memo.provider == "deepseek"
    assert loaded.tag_summary.provider == "openai"
    assert loaded.reminder_extraction.provider == ""
    text = prompts_path.read_text(encoding="utf-8")
    assert "provider: deepseek" in text
    assert "provider: openai" in text
    assert "provider: " in text


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


def test_taxonomy_ignores_markdown_headings_as_tags(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)

    plan = taxonomy.build_organization_plan("# 附件标题\n\n## 二级标题\n\n正文 #AI知识库")

    assert plan.active_tags == ("#项目/个人AI知识库",)
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


def test_taxonomy_config_marks_short_content_as_waiting_user(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)

    plan = taxonomy.build_organization_plan("啥？")

    assert "#系统/待澄清" in plan.system_tags
    assert plan.needs_clarification is True
    assert plan.clarification_reason is not None


def test_taxonomy_config_ignores_question_marks_for_clear_length_content(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)

    plan = taxonomy.build_organization_plan("这是一条包含 URL 参数 https://example.com/search?q=memo 的完整记录？")

    assert "#系统/待澄清" not in plan.system_tags
    assert plan.needs_clarification is False
    assert plan.clarification_reason is None
