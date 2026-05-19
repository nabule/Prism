from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from memosima.core.config import ConfigError


@dataclass(frozen=True)
class BusinessTag:
    path: str
    status: str


@dataclass(frozen=True)
class TagCandidate:
    path: str
    reason: str
    parent_path: str | None = None
    similar_existing_tags: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True)
class OrganizationPlan:
    system_tags: tuple[str, ...]
    active_tags: tuple[str, ...]
    candidate_tags: tuple[TagCandidate, ...]
    disabled_tags: tuple[str, ...]
    needs_clarification: bool
    clarification_reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "system_tags": list(self.system_tags),
            "active_tags": list(self.active_tags),
            "candidate_tags": [
                {
                    "path": candidate.path,
                    "parent_path": candidate.parent_path,
                    "reason": candidate.reason,
                    "similar_existing_tags": list(candidate.similar_existing_tags),
                    "confidence": candidate.confidence,
                }
                for candidate in self.candidate_tags
            ],
            "disabled_tags": list(self.disabled_tags),
            "needs_clarification": self.needs_clarification,
            "clarification_reason": self.clarification_reason,
        }


@dataclass(frozen=True)
class TaxonomyConfig:
    system_tags: dict[str, str]
    business_tags: tuple[BusinessTag, ...]
    aliases: dict[str, str]
    disabled: tuple[str, ...]

    @classmethod
    def load(cls, path: str | Path = "config/taxonomy.yaml") -> "TaxonomyConfig":
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigError(f"Taxonomy config not found: {config_path}")
        with config_path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
        if not isinstance(raw, dict):
            raise ConfigError(f"Taxonomy config must contain a mapping: {config_path}")

        system_tags = raw.get("system_tags", {})
        if not isinstance(system_tags, dict):
            raise ConfigError("taxonomy system_tags must be a mapping")

        aliases: dict[str, str] = {}
        raw_aliases = raw.get("aliases", [])
        if not isinstance(raw_aliases, list):
            raise ConfigError("taxonomy aliases must be a list")
        for item in raw_aliases:
            if not isinstance(item, dict):
                raise ConfigError("taxonomy alias item must be a mapping")
            aliases[_normalize_tag(item.get("alias"))] = _normalize_tag(item.get("target"))

        business_tags: list[BusinessTag] = []
        raw_business_tags = raw.get("business_tags", [])
        if not isinstance(raw_business_tags, list):
            raise ConfigError("taxonomy business_tags must be a list")
        for item in raw_business_tags:
            if not isinstance(item, dict):
                raise ConfigError("taxonomy business tag item must be a mapping")
            business_tags.append(
                BusinessTag(
                    path=_normalize_tag(item.get("path")),
                    status=str(item.get("status", "active")),
                )
            )

        raw_disabled = raw.get("disabled", [])
        if not isinstance(raw_disabled, list):
            raise ConfigError("taxonomy disabled must be a list")
        disabled = tuple(_normalize_tag(item) for item in raw_disabled)

        return cls(
            system_tags={str(key): _normalize_tag(value) for key, value in system_tags.items()},
            business_tags=tuple(business_tags),
            aliases=aliases,
            disabled=disabled,
        )

    @property
    def active_tag_paths(self) -> tuple[str, ...]:
        return tuple(tag.path for tag in self.business_tags if tag.status == "active")

    def build_organization_plan(self, content: str) -> OrganizationPlan:
        raw_tags = _extract_tags(content)
        system_original = self.system_tags.get("original", "#系统/原始记录")
        system_pending = self.system_tags.get("pending_clarification", "#系统/待澄清")
        system_candidate = self.system_tags.get("tag_candidate", "#系统/标签待审核")

        active: list[str] = []
        disabled: list[str] = []
        candidates: list[TagCandidate] = []
        for raw_tag in raw_tags:
            tag = self.aliases.get(raw_tag, raw_tag)
            if tag in self.disabled:
                disabled.append(tag)
            elif tag in self.active_tag_paths:
                active.append(tag)
            elif not tag.startswith("#系统/"):
                candidates.append(
                    TagCandidate(
                        path=tag,
                        parent_path=_parent_tag(tag),
                        reason="memo contains a tag outside the approved taxonomy",
                        similar_existing_tags=_similar_tags(tag, self.active_tag_paths),
                    )
                )

        needs_clarification = _needs_clarification(content)
        system_tags = [system_original]
        if needs_clarification:
            system_tags.append(system_pending)
        if candidates:
            system_tags.append(system_candidate)

        return OrganizationPlan(
            system_tags=tuple(_dedupe(system_tags)),
            active_tags=tuple(_dedupe(active)),
            candidate_tags=tuple(candidates),
            disabled_tags=tuple(_dedupe(disabled)),
            needs_clarification=needs_clarification,
            clarification_reason="content is too short or contains an explicit question mark"
            if needs_clarification
            else None,
        )


def _normalize_tag(value: Any) -> str:
    text = str(value or "").strip()
    if not text.startswith("#") or len(text) == 1:
        raise ConfigError(f"Invalid tag path: {value}")
    if "//" in text or " " in text:
        raise ConfigError(f"Invalid tag path: {value}")
    return text


def _extract_tags(content: str) -> tuple[str, ...]:
    tags: list[str] = []
    for token in content.replace("\n", " ").split():
        if token.startswith("#"):
            tags.append(token.rstrip(".,;:!?，。；：！？）)"))
    return tuple(_dedupe(tags))


def _parent_tag(tag: str) -> str | None:
    if "/" not in tag:
        return None
    return tag.rsplit("/", maxsplit=1)[0]


def _similar_tags(tag: str, active_tags: tuple[str, ...]) -> tuple[str, ...]:
    parent = _parent_tag(tag)
    if not parent:
        return ()
    return tuple(candidate for candidate in active_tags if candidate.startswith(f"{parent}/"))[:3]


def _needs_clarification(content: str) -> bool:
    text = content.strip()
    return len(text) < 12 or "?" in text or "？" in text


def _dedupe(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
