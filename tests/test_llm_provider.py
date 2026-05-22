from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from memosima.core.config import ModelsConfig
from memosima.core.prompts import PromptTemplate
from memosima.core.taxonomy import TaxonomyConfig
from memosima.llm.provider import OpenAICompatibleClient

from helpers import models_config_text, taxonomy_config_text, write_yaml


@pytest.mark.asyncio
async def test_openai_compatible_client_parses_structured_draft(tmp_path, monkeypatch):
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    taxonomy_path = write_yaml(tmp_path / "taxonomy.yaml", taxonomy_config_text())
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    models = ModelsConfig.load(models_path)
    provider = models.providers[models.default_provider]
    taxonomy = TaxonomyConfig.load(taxonomy_path)
    local_plan = taxonomy.build_organization_plan("整理个人 AI 知识库开发记录 #AI知识库")
    app = FastAPI()
    seen: dict[str, object] = {}

    @app.post("/api/v1/chat/completions")
    async def chat_completions(request: Request):
        seen["authorization"] = request.headers.get("authorization")
        seen["payload"] = await request.json()
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"title":"整理记录","summary":"结构化摘要",'
                            '"key_points":["要点一"],"todos":["待办一"],'
                            '"active_tags":["#项目/个人AI知识库"],'
                            '"candidate_tags":[{"path":"#项目/新方向","reason":"正文主题明确","confidence":0.82}],'
                            '"needs_clarification":false,"clarification_question":null}'
                        )
                    }
                }
            ]
        }

    original_async_client = AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = ASGITransport(app=app)
        kwargs["base_url"] = "http://testserver"
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr("memosima.llm.provider.httpx.AsyncClient", fake_async_client)

    draft = await OpenAICompatibleClient(provider, "test-key").organize_memo(
        content="整理个人 AI 知识库开发记录 #AI知识库",
        taxonomy=taxonomy,
        local_plan=local_plan,
        prompt_template=PromptTemplate(
            system="自定义系统提示\n{active_tags}",
            user="自定义用户提示\n{local_plan_json}\n{content}",
        ),
    )

    assert draft.summary == "结构化摘要"
    assert draft.key_points == ["要点一"]
    assert draft.todos == ["待办一"]
    assert draft.active_tags == ["#项目/个人AI知识库"]
    assert len(draft.candidate_tags) == 1
    assert draft.candidate_tags[0].path == "#项目/新方向"
    assert draft.candidate_tags[0].confidence == 0.82
    assert draft.needs_clarification is False
    assert seen["authorization"] == " ".join(["Bearer", "test-key"])
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "google/gemma-3-27b-it"
    assert payload["temperature"] == 0.1
    assert "max_tokens" not in payload
    assert payload["response_format"] == {"type": "json_object"}
    assert "chat_template_kwargs" not in payload
    messages = payload["messages"]
    assert messages[0]["content"].startswith("自定义系统提示")
    assert messages[1]["content"].startswith("自定义用户提示")
    assert "#项目/个人AI知识库" in messages[0]["content"]
    assert "active_tags" in messages[1]["content"]
    assert "整理个人 AI 知识库开发记录" in messages[1]["content"]


@pytest.mark.asyncio
async def test_openai_compatible_client_parses_reminder_extraction(tmp_path, monkeypatch):
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    models = ModelsConfig.load(models_path)
    provider = models.providers[models.default_provider]
    app = FastAPI()
    seen: dict[str, object] = {}

    @app.post("/api/v1/chat/completions")
    async def chat_completions(request: Request):
        seen["payload"] = await request.json()
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"has_reminder":true,'
                            '"items":[{"title":"提交周报","body":"周报发给团队",'
                            '"due_at":"2026-05-22T09:30:00+08:00","timezone":"Asia/Shanghai",'
                            '"confidence":0.92,"raw_text":"#提醒 明天 09:30 提交周报"}],'
                            '"needs_clarification":false,"clarification_question":null}'
                        )
                    }
                }
            ]
        }

    original_async_client = AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = ASGITransport(app=app)
        kwargs["base_url"] = "http://testserver"
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr("memosima.llm.provider.httpx.AsyncClient", fake_async_client)

    extraction = await OpenAICompatibleClient(provider, "test-key").extract_reminders(
        content="#提醒 明天 09:30 提交周报",
        timezone="Asia/Shanghai",
        now="2026-05-21T10:00:00+08:00",
        trigger_tag="#提醒",
    )

    assert extraction.has_reminder is True
    assert extraction.needs_clarification is False
    assert len(extraction.items) == 1
    assert extraction.items[0].title == "提交周报"
    assert extraction.items[0].confidence == 0.92
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["response_format"] == {"type": "json_object"}
    assert "#提醒" in payload["messages"][1]["content"]
    assert "2026-05-21T10:00:00+08:00" in payload["messages"][1]["content"]
