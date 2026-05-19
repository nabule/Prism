from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    pass


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a mapping: {path}")
    return data


def _env_value(name: str | None, default: str | None = None) -> str | None:
    if not name:
        return default
    return os.getenv(name, default)


@dataclass(frozen=True)
class AppConfig:
    workspace_id: str
    public_base_url: str
    timezone: str
    database_path: Path
    admin_token_env: str
    admin_token: str | None
    memos_base_url: str | None
    memos_api_token: str | None
    memos_webhook_url: str | None
    memos_timeout_seconds: float
    worker_poll_interval_seconds: float
    worker_max_attempts: int
    worker_create_probe_comment: bool

    @classmethod
    def load(cls, path: str | Path = "config/app.yaml") -> "AppConfig":
        config_path = Path(path)
        raw = _read_yaml(config_path)
        app = raw.get("app", {})
        database = raw.get("database", {})
        security = raw.get("security", {})
        memos = raw.get("memos", {})
        worker = raw.get("worker", {})

        admin_token_env = str(security.get("admin_token_env", "SIDECAR_ADMIN_TOKEN"))
        memos_base_url_env = memos.get("base_url_env", "MEMOS_BASE_URL")
        memos_api_token_env = memos.get("api_token_env", "MEMOS_API_TOKEN")
        memos_webhook_url_env = memos.get("webhook_url_env", "MEMOS_WEBHOOK_URL")
        db_path = Path(str(database.get("path", "data/sidecar/sidecar.db")))

        return cls(
            workspace_id=str(app.get("workspace_id", "default")),
            public_base_url=str(app.get("public_base_url", "http://localhost:5230")),
            timezone=str(app.get("timezone", "Asia/Shanghai")),
            database_path=db_path,
            admin_token_env=admin_token_env,
            admin_token=_env_value(admin_token_env),
            memos_base_url=_env_value(str(memos_base_url_env)) if memos_base_url_env else None,
            memos_api_token=_env_value(str(memos_api_token_env)) if memos_api_token_env else None,
            memos_webhook_url=_env_value(str(memos_webhook_url_env)) if memos_webhook_url_env else None,
            memos_timeout_seconds=float(memos.get("request_timeout_seconds", 15)),
            worker_poll_interval_seconds=float(worker.get("poll_interval_seconds", 2)),
            worker_max_attempts=int(worker.get("max_attempts", 3)),
            worker_create_probe_comment=bool(worker.get("create_probe_comment", False)),
        )


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: str
    default_model: str
    api_key_present: bool


@dataclass(frozen=True)
class ModelsConfig:
    default_provider: str
    providers: dict[str, ProviderConfig]

    @classmethod
    def load(cls, path: str | Path = "config/models.yaml") -> "ModelsConfig":
        raw = _read_yaml(Path(path))
        default_provider = str(raw.get("default_provider", "openrouter"))
        raw_providers = raw.get("providers", {})
        if not isinstance(raw_providers, dict):
            raise ConfigError("models.yaml providers must be a mapping")

        providers: dict[str, ProviderConfig] = {}
        for name, value in raw_providers.items():
            if not isinstance(value, dict):
                raise ConfigError(f"Provider config must be a mapping: {name}")
            api_key_env = str(value.get("api_key_env", ""))
            providers[str(name)] = ProviderConfig(
                name=str(name),
                base_url=str(value.get("base_url", "")),
                api_key_env=api_key_env,
                default_model=str(value.get("default_model", "")),
                api_key_present=bool(os.getenv(api_key_env)) if api_key_env else False,
            )

        if default_provider not in providers:
            raise ConfigError(f"Default provider is not configured: {default_provider}")
        return cls(default_provider=default_provider, providers=providers)
