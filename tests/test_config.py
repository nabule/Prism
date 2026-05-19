from __future__ import annotations

from memosima.core.config import AppConfig, ModelsConfig

from helpers import app_config_text, models_config_text, write_yaml


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
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("MEMOS_BASE_URL", "http://memos.local")
    monkeypatch.setenv("MEMOS_API_TOKEN", "memos-token")

    config = AppConfig.load(app_path)

    assert config.database_path == db_path
    assert config.admin_token == "admin-token"
    assert config.memos_base_url == "http://memos.local"
    assert config.memos_api_token == "memos-token"
