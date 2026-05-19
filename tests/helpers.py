from __future__ import annotations

from pathlib import Path


def write_yaml(path: Path, content: str) -> Path:
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def app_config_text(db_path: Path) -> str:
    return f"""
app:
  workspace_id: default
  public_base_url: http://localhost:5230
  timezone: Asia/Shanghai
database:
  path: {db_path}
security:
  admin_token_env: SIDECAR_ADMIN_TOKEN
memos:
  base_url_env: MEMOS_BASE_URL
  api_token_env: MEMOS_API_TOKEN
  webhook_url_env: MEMOS_WEBHOOK_URL
  request_timeout_seconds: 5
worker:
  poll_interval_seconds: 0.01
  max_attempts: 2
  create_probe_comment: false
"""


def models_config_text() -> str:
    return """
default_provider: openrouter
providers:
  openrouter:
    base_url: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
    default_model: deepseek/deepseek-v4-flash:free
"""
