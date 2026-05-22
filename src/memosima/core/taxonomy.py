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

        taxonomy = cls(
            system_tags={str(key): _normalize_tag(value) for key, value in system_tags.items()},
            business_tags=tuple(business_tags),
            aliases=aliases,
            disabled=disabled,
        )
        taxonomy.validate_unique_business_leaves()
        return taxonomy

    @property
    def active_tag_paths(self) -> tuple[str, ...]:
        return tuple(tag.path for tag in self.business_tags if tag.status == "active")

    def validate_unique_business_leaves(self) -> None:
        seen: dict[str, str] = {}
        for path in [*self.active_tag_paths, *self.disabled]:
            leaf = _tag_leaf(path)
            existing = seen.get(leaf)
            if existing and existing != path:
                raise ConfigError(f"Duplicate business tag leaf across levels: {existing} and {path}")
            seen[leaf] = path

    def with_active_tags(self, tag_paths: list[str] | tuple[str, ...]) -> "TaxonomyConfig":
        existing = {tag.path for tag in self.business_tags}
        existing_leafs = {_tag_leaf(tag.path) for tag in self.business_tags if tag.status == "active"}
        business_tags = list(self.business_tags)
        for path in tag_paths:
            normalized = _normalize_tag(path)
            leaf = _tag_leaf(normalized)
            if normalized not in existing and leaf not in existing_leafs:
                business_tags.append(BusinessTag(path=normalized, status="active"))
                existing.add(normalized)
                existing_leafs.add(leaf)
        taxonomy = TaxonomyConfig(
            system_tags=self.system_tags,
            business_tags=tuple(business_tags),
            aliases=self.aliases,
            disabled=self.disabled,
        )
        taxonomy.validate_unique_business_leaves()
        return taxonomy

    def build_organization_plan(self, content: str) -> OrganizationPlan:
        raw_tags = _extract_tags(content)
        return self.build_organization_plan_from_tags(content, raw_tags)

    def build_organization_plan_from_tags(
        self,
        content: str,
        raw_tags: tuple[str, ...] | list[str],
    ) -> OrganizationPlan:
        system_original = self.system_tags.get("original", "#系统/原始记录")
        system_pending = self.system_tags.get("pending_clarification", "#系统/待澄清")
        system_candidate = self.system_tags.get("tag_candidate", "#系统/标签待审核")

        active: list[str] = []
        disabled: list[str] = []
        candidates: list[TagCandidate] = []
        candidate_leafs: set[str] = set()

        def add_candidate(tag: str, reason: str) -> None:
            leaf = _tag_leaf(tag)
            if leaf in candidate_leafs:
                return
            candidates.append(
                TagCandidate(
                    path=tag,
                    parent_path=_parent_tag(tag),
                    reason=reason,
                    similar_existing_tags=_similar_tags(tag, self.active_tag_paths),
                )
            )
            candidate_leafs.add(leaf)

        for raw_tag in raw_tags:
            tag, status = self.resolve_business_tag(raw_tag)
            if status == "disabled":
                disabled.append(tag)
            elif status == "active":
                active.append(tag)
            elif not tag.startswith("#系统/"):
                add_candidate(tag, "memo contains a tag outside the approved taxonomy")

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

    def normalize_tag(self, value: Any) -> str:
        return _normalize_tag(value)

    def resolve_business_tag(self, value: Any) -> tuple[str, str]:
        tag = self.aliases.get(_normalize_tag(value), _normalize_tag(value))
        if tag in self.disabled:
            return tag, "disabled"
        if tag in self.active_tag_paths:
            return tag, "active"
        active_leaf_match = _same_leaf_tag(tag, self.active_tag_paths)
        if active_leaf_match:
            return active_leaf_match, "active"
        disabled_leaf_match = _same_leaf_tag(tag, self.disabled)
        if disabled_leaf_match:
            return disabled_leaf_match, "disabled"
        return tag, "unknown"

    def parent_tag(self, tag: str) -> str | None:
        return _parent_tag(tag)

    def similar_tags(self, tag: str) -> tuple[str, ...]:
        return _similar_tags(tag, self.active_tag_paths)


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
            tag = token.rstrip(".,;:!?，。；：！？）)")
            if tag.strip("#"):
                tags.append(tag)
    return tuple(_dedupe(tags))


def _parent_tag(tag: str) -> str | None:
    if "/" not in tag:
        return None
    return tag.rsplit("/", maxsplit=1)[0]


def _tag_leaf(tag: str) -> str:
    return tag.rsplit("/", maxsplit=1)[-1].removeprefix("#")


def _same_leaf_tag(tag: str, candidates: tuple[str, ...]) -> str | None:
    leaf = _tag_leaf(tag)
    for candidate in candidates:
        if _tag_leaf(candidate) == leaf:
            return candidate
    return None


def _similar_tags(tag: str, active_tags: tuple[str, ...]) -> tuple[str, ...]:
    parent = _parent_tag(tag)
    same_leaf = tuple(candidate for candidate in active_tags if _tag_leaf(candidate) == _tag_leaf(tag))
    if same_leaf:
        return same_leaf[:3]
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
