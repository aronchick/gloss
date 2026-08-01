"""Tests for the checklist loader."""

from pathlib import Path

import pytest

from gloss.checklist import load_checklist


@pytest.fixture
def checklist_dir(tmp_path: Path) -> Path:
    """Create a minimal checklist directory with test YAML files."""
    slides_dir = tmp_path / "slides"
    slides_dir.mkdir()

    # Deck-level YAML
    (tmp_path / "deck.yaml").write_text(
        """\
schema_version: "1.0"
id: deck.slide-count
scope: deck
tier: 1
title: Slide count
description: Must have 20 slides.
kind: structure
severity: critical
source_of_truth: ooxml
verification:
  method: object_compare
  selector: slide_count
  expectation:
    exact_count: 20
"""
    )

    # Slide-level YAML with multiple documents
    (slides_dir / "slide-03.yaml").write_text(
        """\
schema_version: "1.0"
id: slide-03.native-table
scope: slide
slide: 3
tier: 1
title: Native table required
description: Must have a table.
kind: table
severity: critical
source_of_truth: ooxml
verification:
  method: object_compare
  selector: table
  expectation:
    exact_count: 1
    required: true
failure_mode:
  automatic_fail_if:
    - grouped_lines_and_text_used_as_table
  propagation: zero_slide
---
schema_version: "1.0"
id: slide-03.font-policy
scope: slide
slide: 3
tier: 1
title: Font policy
description: All fonts bundled.
kind: structure
severity: critical
source_of_truth: ooxml
verification:
  method: anti_cheat
  selector: font_policy
"""
    )

    # Tier 3 only slide
    (slides_dir / "slide-15.yaml").write_text(
        """\
schema_version: "1.0"
id: slide-15.rotated-text
scope: slide
slide: 15
tier: 3
title: Rotated text
description: Must have rotated text.
kind: structure
severity: critical
source_of_truth: ooxml
verification:
  method: object_compare
  selector: shape
  expectation:
    min_count: 1
"""
    )
    return tmp_path


def test_load_all_tiers(checklist_dir: Path) -> None:
    """Loading tier 3 should return all items."""
    items = load_checklist(checklist_dir, tier=3)
    assert len(items) == 4  # 1 deck + 2 slide-03 + 1 slide-15


def test_tier_filtering(checklist_dir: Path) -> None:
    """Loading tier 1 should exclude tier 3 items."""
    items = load_checklist(checklist_dir, tier=1)
    assert len(items) == 3  # 1 deck + 2 slide-03
    ids = {i.id for i in items}
    assert "slide-15.rotated-text" not in ids


def test_item_properties(checklist_dir: Path) -> None:
    """Loaded items should have correct properties."""
    items = load_checklist(checklist_dir, tier=1)
    deck_item = next(i for i in items if i.id == "deck.slide-count")
    assert deck_item.scope == "deck"
    assert deck_item.severity == "critical"
    assert deck_item.weight == 3
    assert deck_item.verification.method == "object_compare"
    assert deck_item.verification.selector == "slide_count"
    assert deck_item.verification.expectation["exact_count"] == 20


def test_failure_mode_parsing(checklist_dir: Path) -> None:
    """Failure mode should be correctly parsed."""
    items = load_checklist(checklist_dir, tier=1)
    table_item = next(i for i in items if i.id == "slide-03.native-table")
    assert table_item.failure_mode.propagation == "zero_slide"
    assert "grouped_lines_and_text_used_as_table" in table_item.failure_mode.automatic_fail_if


def test_empty_checklist_dir(tmp_path: Path) -> None:
    """Empty dir should return no items."""
    items = load_checklist(tmp_path, tier=3)
    assert items == []


def test_missing_dir() -> None:
    """Non-existent dir should return no items."""
    items = load_checklist(Path("/nonexistent"), tier=3)
    assert items == []
