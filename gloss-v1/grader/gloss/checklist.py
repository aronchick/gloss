"""Checklist loader — loads and validates YAML checklist items from benchmark data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from pathlib import Path

SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 3,
    "major": 2,
    "minor": 1,
    "informational": 0,
}


@dataclass
class Verification:
    method: str
    selector: str = ""
    expectation: dict[str, Any] = field(default_factory=dict)
    tolerance: dict[str, Any] = field(default_factory=dict)
    semantic_equivalence: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureMode:
    automatic_fail_if: list[str] = field(default_factory=list)
    propagation: str = "zero_item"
    affected_slides: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChecklistItem:
    """A single checklist item loaded from YAML."""

    schema_version: str
    id: str
    scope: str  # "slide" or "deck"
    tier: int
    title: str
    description: str
    kind: str
    severity: str
    source_of_truth: str
    verification: Verification
    failure_mode: FailureMode = field(default_factory=FailureMode)
    slide: int | None = None
    assertion_id: str = ""

    @property
    def weight(self) -> int:
        return SEVERITY_WEIGHTS.get(self.severity, 0)


def load_checklist(checklist_dir: Path, tier: int) -> list[ChecklistItem]:
    """Load all checklist items for a given tier from the benchmark checklist directory.

    Loads deck.yaml and all slide-NN.yaml files, filtering to items
    whose tier <= the requested tier.
    """
    items: list[ChecklistItem] = []

    # Load deck-level items
    deck_path = checklist_dir / "deck.yaml"
    if deck_path.exists():
        items.extend(_load_yaml_file(deck_path))

    # Load slide-level items
    slides_dir = checklist_dir / "slides"
    if slides_dir.exists():
        for yaml_path in sorted(slides_dir.glob("slide-*.yaml")):
            items.extend(_load_yaml_file(yaml_path))

    # Filter to requested tier
    return [item for item in items if item.tier <= tier]


def _load_yaml_file(path: Path) -> list[ChecklistItem]:
    """Load checklist items from a single YAML file.

    A file may contain a single item (dict) or multiple items (list of dicts
    separated by --- document markers).
    """
    items: list[ChecklistItem] = []
    text = path.read_text(encoding="utf-8")

    for doc in yaml.safe_load_all(text):
        if doc is None:
            continue
        if isinstance(doc, list):
            for entry in doc:
                items.append(_parse_item(entry, path))
        elif isinstance(doc, dict):
            items.append(_parse_item(doc, path))

    return items


def _parse_item(raw: dict[str, Any], source_path: Path) -> ChecklistItem:
    """Parse a raw dict into a ChecklistItem."""
    verification_raw = raw.get("verification", {})
    verification = Verification(
        method=verification_raw.get("method", ""),
        selector=verification_raw.get("selector", ""),
        expectation=verification_raw.get("expectation", {}),
        tolerance=verification_raw.get("tolerance", {}),
        semantic_equivalence=verification_raw.get("semantic_equivalence", {}),
    )

    failure_raw = raw.get("failure_mode", {})
    failure_mode = FailureMode(
        automatic_fail_if=failure_raw.get("automatic_fail_if", []),
        propagation=failure_raw.get("propagation", "zero_item"),
        affected_slides=failure_raw.get("affected_slides", {}),
    )

    return ChecklistItem(
        schema_version=raw.get("schema_version", "1.0"),
        id=raw.get("id", f"unknown-{source_path.stem}"),
        scope=raw.get("scope", "slide"),
        tier=raw.get("tier", 1),
        title=raw.get("title", ""),
        description=raw.get("description", ""),
        kind=raw.get("kind", "structure"),
        severity=raw.get("severity", "major"),
        source_of_truth=raw.get("source_of_truth", "ooxml"),
        verification=verification,
        failure_mode=failure_mode,
        slide=raw.get("slide"),
        assertion_id=raw.get("assertion_id", ""),
    )


def validate_checklist_schema(checklist_dir: Path, schema_path: Path) -> list[str]:
    """Validate all YAML files against the JSON schema. Returns list of errors."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed — skipping schema validation"]

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    yaml_files = [checklist_dir / "deck.yaml"]
    slides_dir = checklist_dir / "slides"
    if slides_dir.exists():
        yaml_files.extend(sorted(slides_dir.glob("slide-*.yaml")))

    for yaml_path in yaml_files:
        if not yaml_path.exists():
            continue
        text = yaml_path.read_text(encoding="utf-8")
        for doc in yaml.safe_load_all(text):
            if doc is None:
                continue
            docs = doc if isinstance(doc, list) else [doc]
            for entry in docs:
                try:
                    jsonschema.validate(entry, schema)
                except jsonschema.ValidationError as e:
                    errors.append(f"{yaml_path.name}: {entry.get('id', '?')}: {e.message}")

    return errors
