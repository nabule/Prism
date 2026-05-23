from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from memosima.core.config import ConfigError


DEFAULT_ORGANIZE_MEMO_SYSTEM = """你是个人知识库整理助手。请只输出 JSON 对象，不要输出 Markdown 代码块。
必须优先从已有正式标签中选择 active_tags。
只选择与正文核心主题直接相关的少量标签，active_tags 通常不超过 5 个。
只有正文确实需要且没有合适正式标签时，才在 candidate_tags 中提出新标签；不要把新标签放入 active_tags，candidate_tags 通常不超过 2 个。
不同层级的业务标签必须保证最后一级名称唯一，例如已有 #项目/数管 时，不要再提出 #数管 或 #其他/数管。
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

DEFAULT_REMINDER_EXTRACTION_SYSTEM = (
    "你是提醒时间抽取器，只返回 JSON 对象，不要输出 Markdown。"
    "只处理用户明确使用触发标签的提醒请求。"
    "把相对时间换算成带时区的 ISO 8601 时间；无法确定具体时间时要求澄清。"
)

DEFAULT_REMINDER_EXTRACTION_USER = """触发标签：{trigger_tag}
当前时间：{now}
默认时区：{timezone}

请返回 JSON：
{"has_reminder": boolean, "items": [{"title": string, "body": string, "due_at": string, "timezone": string, "confidence": number, "raw_text": string}], "needs_clarification": boolean, "clarification_question": string|null}

规则：
- 只有正文包含触发标签时才提取提醒。
- due_at 必须是可解析的 ISO 8601 时间，优先包含时区偏移。
- 如果只有日期没有具体时刻、时间已无法确定或语义模糊，needs_clarification=true。
- title 简短概括提醒事项，body 保留必要上下文。

memo 内容：
{content}"""


@dataclass(frozen=True)
class PromptTemplate:
    system: str
    user: str
    provider: str | None = None

    def render(self, context: dict[str, str]) -> "RenderedPrompt":
        return RenderedPrompt(
            system=_replace_placeholders(self.system, context),
            user=_replace_placeholders(self.user, context),
        )

    def to_dict(self) -> dict[str, str]:
        payload = {"system": self.system, "user": self.user}
        if self.provider:
            payload["provider"] = self.provider
        return payload


@dataclass(frozen=True)
class RenderedPrompt:
    system: str
    user: str


@dataclass(frozen=True)
class PromptsConfig:
    organize_memo: PromptTemplate
    tag_summary: PromptTemplate
    reminder_extraction: PromptTemplate

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
        reminder_extraction = raw.get("reminder_extraction", {})
        if reminder_extraction and not isinstance(reminder_extraction, dict):
            raise ConfigError("prompts reminder_extraction must be a mapping")
        return cls(
            organize_memo=_template_from_mapping(organize_memo, "organize_memo"),
            tag_summary=_template_from_mapping(tag_summary, "tag_summary") if tag_summary else default_tag_summary_prompt(),
            reminder_extraction=_template_from_mapping(reminder_extraction, "reminder_extraction")
            if reminder_extraction
            else default_reminder_extraction_prompt(),
        )

    def save(self, path: str | Path) -> None:
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "organize_memo": self.organize_memo.to_dict(),
            "tag_summary": self.tag_summary.to_dict(),
            "reminder_extraction": self.reminder_extraction.to_dict(),
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
        reminder_extraction=default_reminder_extraction_prompt(),
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


def default_reminder_extraction_prompt() -> PromptTemplate:
    return PromptTemplate(
        system=DEFAULT_REMINDER_EXTRACTION_SYSTEM,
        user=DEFAULT_REMINDER_EXTRACTION_USER,
    )


def _template_from_mapping(raw: dict[str, Any], name: str) -> PromptTemplate:
    provider = _optional_prompt_provider(raw.get("provider"))
    system = str(raw.get("system", "")).strip()
    user = str(raw.get("user", "")).strip()
    if not system:
        raise ConfigError(f"{name} system prompt must not be empty")
    if not user:
        raise ConfigError(f"{name} user prompt must not be empty")
    return PromptTemplate(system=system, user=user, provider=provider)


def _optional_prompt_provider(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _replace_placeholders(text: str, context: dict[str, str]) -> str:
    result = text
    for key, value in context.items():
        result = result.replace("{" + key + "}", value)
    return result
