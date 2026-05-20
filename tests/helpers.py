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
taxonomy:
  path: {db_path.parent / "taxonomy.yaml"}
prompts:
  path: {db_path.parent / "prompts.yaml"}
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
limits:
  max_attachment_mb: 1
  allowed_parse_extensions:
    - .txt
    - .md
"""


def prompts_config_text() -> str:
    return """
organize_memo:
  system: |-
    测试系统提示词
    {active_tags}
  user: |-
    测试用户提示词
    {local_plan_json}
    {content}
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


def taxonomy_config_text() -> str:
    return """
system_tags:
  original: "#系统/原始记录"
  ai_summary: "#系统/AI整理"
  pending_clarification: "#系统/待澄清"
  tag_candidate: "#系统/标签待审核"
business_tags:
  - path: "#项目/个人AI知识库"
    status: active
aliases:
  - alias: "#AI知识库"
    target: "#项目/个人AI知识库"
disabled:
  - "#杂项"
"""
