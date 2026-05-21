from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from memosima.core.config import ConfigError


DEFAULT_ORGANIZE_MEMO_SYSTEM = """你是个人知识库整理助手。请只输出 JSON 对象，不要输出 Markdown 代码块。
必须优先从已有正式标签中选择 active_tags。
只有正文确实需要且没有合适正式标签时，才在 candidate_tags 中提出新标签；不要把新标签放入 active_tags。
如果内容指代不明或缺少关键信息，将 needs_clarification 设为 true，并给出 clarification_question。
JSON 字段：title, summary, key_points, todos, active_tags, candidate_tags, needs_clarification, clarification_question。
candidate_tags 每项字段：path, reason, confidence。标签 path 必须以 # 开头，不含空格。
已有正式标签：
{active_tags}"""

DEFAULT_ORGANIZE_MEMO_USER = """请整理以下 memo，并遵守本地标签治理草案。

本地标签治理草案：
{local_plan_json}

原始 memo：
{content}"""

DEFAULT_TAG_SUMMARY_SYSTEM = """你是个人知识库专题整理助手。请输出 Markdown，不要输出 JSON。
目标是把同一标签下零散 memo 整理成适合人阅读的整体展示。
请保留事实边界，不要编造未出现的信息。
建议结构：总览、关键主题、时间线或进展、已完成、问题与风险、待办、相关 memo。"""

DEFAULT_TAG_SUMMARY_USER = """请为标签 {tag} 生成整体总结。

memo 数量：{memo_count}

memo 列表：
{memos_markdown}"""


@dataclass(frozen=True)
class PromptTemplate:
    system: str
    user: str

    def render(self, context: dict[str, str]) -> "RenderedPrompt":
        return RenderedPrompt(
            system=_replace_placeholders(self.system, context),
            user=_replace_placeholders(self.user, context),
        )

    def to_dict(self) -> dict[str, str]:
        return {"system": self.system, "user": self.user}


@dataclass(frozen=True)
class RenderedPrompt:
    system: str
    user: str


@dataclass(frozen=True)
class PromptsConfig:
    organize_memo: PromptTemplate
    tag_summary: PromptTemplate

    @classmethod
    def load(cls, path: str | Path = "config/prompts.yaml") -> "PromptsConfig":
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigError(f"Prompts config not found: {config_path}")
        with config_path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
        if not isinstance(raw, dict):
            raise ConfigError(f"Prompts config must contain a mapping: {config_path}")

        organize_memo = raw.get("organize_memo", {})
        if not isinstance(organize_memo, dict):
            raise ConfigError("prompts organize_memo must be a mapping")
        tag_summary = raw.get("tag_summary", {})
        if tag_summary and not isinstance(tag_summary, dict):
            raise ConfigError("prompts tag_summary must be a mapping")
        return cls(
            organize_memo=_template_from_mapping(organize_memo, "organize_memo"),
            tag_summary=_template_from_mapping(tag_summary, "tag_summary") if tag_summary else default_tag_summary_prompt(),
        )

    def save(self, path: str | Path) -> None:
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "organize_memo": self.organize_memo.to_dict(),
            "tag_summary": self.tag_summary.to_dict(),
        }
        with config_path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(payload, file, allow_unicode=True, sort_keys=False)


def load_prompts_or_default(path: str | Path) -> PromptsConfig:
    config_path = Path(path)
    if config_path.exists():
        return PromptsConfig.load(config_path)
    return PromptsConfig(
        organize_memo=default_organize_memo_prompt(),
        tag_summary=default_tag_summary_prompt(),
    )


def default_organize_memo_prompt() -> PromptTemplate:
    return PromptTemplate(
        system=DEFAULT_ORGANIZE_MEMO_SYSTEM,
        user=DEFAULT_ORGANIZE_MEMO_USER,
    )


def default_tag_summary_prompt() -> PromptTemplate:
    return PromptTemplate(
        system=DEFAULT_TAG_SUMMARY_SYSTEM,
        user=DEFAULT_TAG_SUMMARY_USER,
    )


def _template_from_mapping(raw: dict[str, Any], name: str) -> PromptTemplate:
    system = str(raw.get("system", "")).strip()
    user = str(raw.get("user", "")).strip()
    if not system:
        raise ConfigError(f"{name} system prompt must not be empty")
    if not user:
        raise ConfigError(f"{name} user prompt must not be empty")
    return PromptTemplate(system=system, user=user)


def _replace_placeholders(text: str, context: dict[str, str]) -> str:
    result = text
    for key, value in context.items():
        result = result.replace("{" + key + "}", value)
    return result
