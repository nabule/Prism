from __future__ import annotations

from memosima.core.config import AppConfig, ModelsConfig
from memosima.core.taxonomy import TaxonomyConfig

from helpers import app_config_text, models_config_text, taxonomy_config_text, write_yaml


def test_models_config_uses_openrouter_free_model(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())

    config = ModelsConfig.load(models_path)

    provider = config.providers[config.default_provider]
    assert config.default_provider == "openrouter"
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.api_key_env == "OPENROUTER_API_KEY"
    assert provider.default_model == "deepseek/deepseek-v4-flash:free"
    assert provider.api_key_present is True


def test_app_config_reads_secret_values_from_environment(tmp_path, monkeypatch):
    db_path = tmp_path / "sidecar.db"
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(db_path))
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")
    monkeypatch.setenv("MEMOS_WEBHOOK_URL", "https://sidecar.example.com/webhooks/memos")

    config = AppConfig.load(app_path)

    assert config.database_path == db_path
    assert config.taxonomy_path == taxonomy_path
    assert config.admin_token == "admin-token"
    assert config.memos_base_url == "http://memos.local"
    assert config.memos_api_token == "memos-token"
    assert config.memos_webhook_url == "https://sidecar.example.com/webhooks/memos"


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


def test_taxonomy_config_marks_short_or_question_content_as_waiting_user(tmp_path):
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    taxonomy = TaxonomyConfig.load(taxonomy_path)

    plan = taxonomy.build_organization_plan("这个怎么处理？")

    assert "#系统/待澄清" in plan.system_tags
    assert plan.needs_clarification is True
    assert plan.clarification_reason is not None
