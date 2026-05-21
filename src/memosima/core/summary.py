from __future__ import annotations

from memosima.core.taxonomy import OrganizationPlan, TaxonomyConfig
from memosima.llm.provider import LLMOrganizationDraft


def build_summary_memo_content(
    *,
    source_memo_uid: str,
    source_content: str,
    organization_plan: OrganizationPlan,
    taxonomy: TaxonomyConfig,
    llm_draft: LLMOrganizationDraft | None = None,
    show_candidate_tags: bool = False,
) -> str:
    ai_summary_tag = taxonomy.system_tags.get("ai_summary", "#系统/AI整理")
    hidden_candidate_paths = [] if show_candidate_tags else [candidate.path for candidate in organization_plan.candidate_tags]
    tags = _dedupe(
        [
            ai_summary_tag,
            *organization_plan.system_tags,
            *organization_plan.active_tags,
            *(candidate.path for candidate in organization_plan.candidate_tags if show_candidate_tags),
        ]
    )

    lines = [
        f"{ai_summary_tag} {' '.join(tag for tag in tags if tag != ai_summary_tag)}".strip(),
        "",
        f"## AI整理：{_sanitize_candidate_tag_markers(_summary_title(source_content, llm_draft), hidden_candidate_paths)}",
        "",
        f"来源 memo：memos/{source_memo_uid}",
        "",
        "### 摘要",
        "",
        _sanitize_candidate_tag_markers(
            llm_draft.summary if llm_draft else _summary_text(source_content),
            hidden_candidate_paths,
        ),
        "",
    ]

    if llm_draft and llm_draft.key_points:
        lines.extend(["### 要点", ""])
        lines.extend(f"- {_sanitize_candidate_tag_markers(point, hidden_candidate_paths)}" for point in llm_draft.key_points)
        lines.append("")

    if llm_draft and llm_draft.todos:
        lines.extend(["### 待办", ""])
        lines.extend(f"- {_sanitize_candidate_tag_markers(todo, hidden_candidate_paths)}" for todo in llm_draft.todos)
        lines.append("")

    lines.extend(
        [
        "### 标签",
        "",
        ]
    )

    if organization_plan.active_tags:
        lines.extend(f"- 已使用：{tag}" for tag in organization_plan.active_tags)
    else:
        lines.append("- 已使用：无")

    if organization_plan.candidate_tags:
        lines.extend(
            f"- 待审核：{_display_candidate_tag(candidate.path, show_candidate_tags)}"
            for candidate in organization_plan.candidate_tags
        )
    else:
        lines.append("- 待审核：无")

    if organization_plan.disabled_tags:
        lines.extend(f"- 已禁用：{tag}" for tag in organization_plan.disabled_tags)

    if organization_plan.needs_clarification:
        lines.extend(
            [
                "",
                "### 待澄清",
                "",
                organization_plan.clarification_reason or "内容需要进一步澄清。",
            ]
        )

    lines.extend(
        [
            "",
            "### 原文摘录",
            "",
            _sanitize_candidate_tag_markers(_excerpt(source_content), hidden_candidate_paths),
        ]
    )

    return "\n".join(lines).strip() + "\n"


def _summary_text(content: str) -> str:
    text = " ".join(content.split())
    if not text:
        return "当前 memo 没有可整理的文本内容。"
    if len(text) <= 120:
        return text
    return f"{text[:117]}..."


def _summary_title(content: str, llm_draft: LLMOrganizationDraft | None) -> str:
    if llm_draft and llm_draft.title.strip():
        title = llm_draft.title.strip()
    else:
        title = _summary_text(content)
    return title.removeprefix("AI整理：").removeprefix("AI整理").strip() or "未命名"


def _excerpt(content: str) -> str:
    text = content.strip()
    if not text:
        return "> 无文本内容"
    excerpt = text if len(text) <= 500 else f"{text[:497]}..."
    return "\n".join(f"> {line}" if line else ">" for line in excerpt.splitlines())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _display_candidate_tag(tag: str, show_candidate_tags: bool) -> str:
    return tag if show_candidate_tags else tag.removeprefix("#")


def _sanitize_candidate_tag_markers(text: str, candidate_tags: list[str]) -> str:
    result = text
    for tag in candidate_tags:
        result = result.replace(tag, tag.removeprefix("#"))
    return result
