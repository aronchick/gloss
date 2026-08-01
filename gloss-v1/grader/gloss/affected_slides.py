"""Content-addressed affected-slide selectors for deck-scoped automatic failures."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import rfc8785

from gloss.resources import resolve_benchmark_dir

if TYPE_CHECKING:
    from pathlib import Path

    from gloss.inspect_ooxml import DeckGraph, SceneObject

SELECTOR_REGISTRY = "requirements/affected-slide-selectors-v1.json"
NON_BUNDLED_FONT_SELECTOR = "gloss.affected-slides.non-bundled-font.v1"
NOTES_COMMENTS_SELECTOR = "gloss.affected-slides.notes-comments.v1"


class AffectedSlideSelectorError(ValueError):
    """Raised when a named selector is missing, altered, or unsupported."""


def selector_binding(selector_id: str, registry_path: Path | None = None) -> dict[str, str]:
    """Return the verified identifier/hash binding for one selector."""
    registry = _load_registry(str(registry_path) if registry_path is not None else "")
    try:
        entry = registry[selector_id]
    except KeyError as exc:
        raise AffectedSlideSelectorError(f"Unknown affected-slide selector: {selector_id}") from exc
    return {
        "selector_id": selector_id,
        "selector_sha256": entry["selector_sha256"],
    }


def resolve_named_selector(
    selector_id: str,
    selector_sha256: str,
    deck: DeckGraph,
    bundled_fonts: set[str],
    registry_path: Path | None = None,
) -> list[int]:
    """Verify and execute one frozen named selector against a deck graph."""
    binding = selector_binding(selector_id, registry_path)
    if binding["selector_sha256"] != selector_sha256:
        raise AffectedSlideSelectorError(
            f"Affected-slide selector hash mismatch for {selector_id}: "
            f"expected {binding['selector_sha256']}, got {selector_sha256}"
        )
    if selector_id == NON_BUNDLED_FONT_SELECTOR:
        return _non_bundled_font_slides(deck, bundled_fonts)
    if selector_id == NOTES_COMMENTS_SELECTOR:
        return _notes_or_comment_slides(deck)
    raise AffectedSlideSelectorError(f"Unsupported affected-slide selector: {selector_id}")


@lru_cache(maxsize=4)
def _load_registry(registry_path: str) -> dict[str, dict[str, Any]]:
    path = (
        resolve_benchmark_dir() / SELECTOR_REGISTRY
        if not registry_path
        else _path_from_string(registry_path)
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("registry_id") != "gloss-affected-slide-selectors-v1":
        raise AffectedSlideSelectorError(f"Unsupported affected-slide selector registry: {path}")

    result: dict[str, dict[str, Any]] = {}
    for entry in document.get("selectors", []):
        selector_id = entry.get("selector_id")
        descriptor = entry.get("descriptor")
        claimed_hash = entry.get("selector_sha256")
        if not isinstance(selector_id, str) or not isinstance(descriptor, dict):
            raise AffectedSlideSelectorError(f"Malformed selector entry in {path}")
        actual_hash = f"sha256:{hashlib.sha256(rfc8785.dumps(descriptor)).hexdigest()}"
        if claimed_hash != actual_hash:
            raise AffectedSlideSelectorError(
                f"Affected-slide selector descriptor hash mismatch for {selector_id}"
            )
        if descriptor.get("selector_id") != selector_id or selector_id in result:
            raise AffectedSlideSelectorError(f"Invalid selector identity in {path}: {selector_id}")
        result[selector_id] = entry
    if not result:
        raise AffectedSlideSelectorError(f"Affected-slide selector registry is empty: {path}")
    return result


def _path_from_string(value: str) -> Path:
    from pathlib import Path

    return Path(value)


def _non_bundled_font_slides(deck: DeckGraph, bundled_fonts: set[str]) -> list[int]:
    affected: list[int] = []
    for slide in deck.slides:
        if any(
            run.font_family
            and not run.font_family.startswith("+")
            and run.font_family.lower() not in bundled_fonts
            for obj in _collect_objects_recursive(slide.objects)
            for run in obj.text_runs
        ):
            affected.append(slide.slide_number)
    return sorted(set(affected))


def _notes_or_comment_slides(deck: DeckGraph) -> list[int]:
    return sorted(deck.notes_slides | deck.comment_slides)


def _collect_objects_recursive(objects: list[SceneObject]) -> list[SceneObject]:
    result: list[SceneObject] = []
    for obj in objects:
        result.append(obj)
        result.extend(_collect_objects_recursive(obj.children))
    return result
