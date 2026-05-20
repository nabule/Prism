from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from memosima.core.config import ProviderConfig
from memosima.core.taxonomy import OrganizationPlan, TaxonomyConfig


class LLMClientError(RuntimeError):
    pass


class LLMTagCandidate(BaseModel):
    path: str = Field(min_length=2, max_length=120)
    reason: str = Field(min_length=1, max_length=500)
    confidence: float = Field(default=0.5, ge=0, le=1)


class LLMOrganizationDraft(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=2000)
    key_points: list[str] = Field(default_factory=list, max_length=20)
    todos: list[str] = Field(default_factory=list, max_length=20)
    active_tags: list[str] = Field(default_factory=list, max_length=20)
    candidate_tags: list[LLMTagCandidate] = Field(default_factory=list, max_length=20)
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=1000)


@dataclass(frozen=True)
class OpenAICompatibleClient:
    provider: ProviderConfig
    api_key: str
    timeout_seconds: float = 30

    async def organize_memo(
        self,
        *,
        content: str,
        taxonomy: TaxonomyConfig,
        local_plan: OrganizationPlan,
    ) -> LLMOrganizationDraft:
        payload = {
            "model": self.provider.default_model,
            "messages": [
                {"role": "system", "content": _system_prompt(taxonomy)},
                {"role": "user", "content": _user_prompt(content, local_plan)},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        response = await self._request("POST", "/chat/completions", json=payload)
        return _parse_draft_response(response)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(
                method,
                _join_url(self.provider.base_url, path),
                headers=headers,
                **kwargs,
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(
                f"LLM request failed: {method} {path} -> {response.status_code}"
            ) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMClientError("LLM returned non-JSON response") from exc
        if not isinstance(data, dict):
            raise LLMClientError("LLM returned unexpected response shape")
        return data


def _parse_draft_response(response: dict[str, Any]) -> LLMOrganizationDraft:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMClientError("LLM response is missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise LLMClientError("LLM response choice has unexpected shape")
    message = first.get("message")
    if not isinstance(message, dict):
        raise LLMClientError("LLM response is missing message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LLMClientError("LLM response is missing message content")
    try:
        raw = json.loads(content)
    except ValueError as exc:
        raise LLMClientError("LLM message content is not valid JSON") from exc
    try:
        return LLMOrganizationDraft.model_validate(raw)
    except ValidationError as exc:
        raise LLMClientError("LLM JSON does not match organization schema") from exc


def _system_prompt(taxonomy: TaxonomyConfig) -> str:
    active_tags = "\n".join(f"- {tag}" for tag in taxonomy.active_tag_paths) or "- 无"
    return "\n".join(
        [
            "你是个人知识库整理助手。请只输出 JSON 对象，不要输出 Markdown 代码块。",
            "必须优先从已有正式标签中选择 active_tags。",
            "只有正文确实需要且没有合适正式标签时，才在 candidate_tags 中提出新标签；不要把新标签放入 active_tags。",
            "如果内容指代不明或缺少关键信息，将 needs_clarification 设为 true，并给出 clarification_question。",
            "JSON 字段：title, summary, key_points, todos, active_tags, candidate_tags, needs_clarification, clarification_question。",
            "candidate_tags 每项字段：path, reason, confidence。标签 path 必须以 # 开头，不含空格。",
            "已有正式标签：",
            active_tags,
        ]
    )


def _user_prompt(content: str, local_plan: OrganizationPlan) -> str:
    return "\n".join(
        [
            "请整理以下 memo，并遵守本地标签治理草案。",
            "",
            "本地标签治理草案：",
            json.dumps(local_plan.to_dict(), ensure_ascii=False, sort_keys=True),
            "",
            "原始 memo：",
            content,
        ]
    )


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
