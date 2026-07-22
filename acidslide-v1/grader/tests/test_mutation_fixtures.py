"""Tests for deterministic generated operator-level mutation fixtures."""

from __future__ import annotations

import json
import runpy
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from acidslide.affected_slides import (
    NON_BUNDLED_FONT_SELECTOR,
    AffectedSlideSelectorError,
    resolve_named_selector,
    selector_binding,
)
from acidslide.checklist import ChecklistItem, load_checklist
from acidslide.evaluate import BUNDLED_FONTS, evaluate_checklist
from acidslide.inspect_ooxml import DeckGraph, extract_deck_graph
from acidslide.mutation_fixtures import (
    build_fixture_index,
    build_mutation_expectations,
    execute_fixture_matrix,
)

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmark"


@dataclass
class _ValidationResult:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


@pytest.fixture(scope="module")
def generated_matrix() -> tuple[
    list[ChecklistItem], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    items = load_checklist(BENCHMARK / "checklist", tier=3)
    inventory = json.loads(
        (BENCHMARK / "requirements" / "scored-assertion-inventory.json").read_text(encoding="utf-8")
    )
    index = build_fixture_index(items, inventory)
    expectations = build_mutation_expectations(index)
    execution = execute_fixture_matrix(items, index)
    return items, index, expectations, execution


def test_all_candidates_have_executed_positive_and_single_fault_negative_fixtures(
    generated_matrix: tuple[list[ChecklistItem], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    _, index, expectations, execution = generated_matrix

    assert index["summary"]["candidate_items"] == 280
    assert index["summary"]["executable_items"] == 280
    assert index["summary"]["unimplemented_items"] == 0
    assert expectations["summary"] == {
        "expectations": 280,
        "single_fault_expectations": 280,
        "unimplemented": 0,
    }
    assert execution["summary"]["executed_positive_fixtures"] == 280
    assert execution["summary"]["executed_single_fault_negative_fixtures"] == 280
    assert execution["summary"]["killed_mutants"] == 280
    assert execution["summary"]["survived_mutants"] == 0


def test_operator_fixtures_do_not_claim_independent_release_evidence(
    generated_matrix: tuple[list[ChecklistItem], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    _, index, expectations, execution = generated_matrix

    assert index["summary"]["assertion_evidence_complete"] == 0
    assert index["summary"]["assertion_evidence_pending_or_unknown"] == 280
    assert all(entry["release_evidence_claimed"] is False for entry in index["entries"])
    assert all(
        expectation["release_evidence_claimed"] is False
        for expectation in expectations["expectations"]
    )
    assert execution["summary"]["assertion_evidence_completed_by_this_run"] == 0


def test_chart_primary_composites_verify_native_charts(
    generated_matrix: tuple[list[ChecklistItem], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    items, index, expectations, execution = generated_matrix
    builder = runpy.run_path(str(BENCHMARK / "tools" / "build_corpus.py"))
    items_by_id = {item.id: item for item in items}
    index_by_id = {entry["checklist_item_id"]: entry for entry in index["entries"]}
    expectations_by_id = {
        entry["checklist_item_id"]: entry for entry in expectations["expectations"]
    }
    execution_by_id = {entry["checklist_item_id"]: entry for entry in execution["results"]}

    for item_id in ("slide-13.native-primary", "slide-20.native-primary"):
        item = items_by_id[item_id]
        slide_number = item.slide
        assert slide_number is not None
        built_item = next(
            candidate
            for candidate in builder["slide_items"](slide_number, {})
            if candidate["id"] == item_id
        )
        assert built_item["verification"] == {
            "method": "object_compare",
            "selector": "chart",
            "expectation": {"min_count": 1, "required": True},
        }
        assert item.verification.method == "object_compare"
        assert item.verification.selector == "chart"
        assert item.verification.expectation == {"min_count": 1, "required": True}
        assert index_by_id[item_id]["mutation_operator"] == "decrement-chart-count"
        assert expectations_by_id[item_id]["mutation_operator"] == "decrement-chart-count"
        assert execution_by_id[item_id]["mutation_operator"] == "decrement-chart-count"
        assert execution_by_id[item_id]["mutant_killed"] is True


def test_checked_in_mutation_documents_are_current(
    generated_matrix: tuple[list[ChecklistItem], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    _, index, expectations, execution = generated_matrix
    generated_dir = BENCHMARK / "fixtures" / "mutations"

    assert json.loads((generated_dir / "fixture-index-v1.json").read_text()) == index
    assert json.loads((generated_dir / "mutation-expectations-v1.json").read_text()) == expectations
    assert json.loads((generated_dir / "execution-report-v1.json").read_text()) == execution


def test_scene_graph_package_binding_waits_for_gold_evidence() -> None:
    validator = runpy.run_path(str(BENCHMARK / "validate_normative.py"))
    validate_scene_graph = validator["_validate_scene_graph_semantics"]
    scene_graph = {
        "profile_sha256": "sha256:profile",
        "mce_resolved_package_sha256": "sha256:resolved",
        "slides": [
            {
                "slide": 1,
                "part_name": "ppt/slides/slide1.xml",
                "relationships": [],
                "nodes": [],
            }
        ],
    }
    missing_root = _ValidationResult()

    validate_scene_graph(
        missing_root,
        scene_graph,
        expected_profile_sha256="sha256:profile",
        expected_package_sha256=None,
        expected_slides=[1],
        label="slide-01.json",
    )

    assert missing_root.errors == []

    wrong_binding = _ValidationResult()
    validate_scene_graph(
        wrong_binding,
        scene_graph,
        expected_profile_sha256="sha256:profile",
        expected_package_sha256="sha256:different",
        expected_slides=[1],
        label="slide-01.json",
    )
    assert wrong_binding.errors == [
        "release mode: slide-01.json is bound to the wrong resolved gold package"
    ]


def test_named_selector_hash_tampering_fails_closed() -> None:
    binding = selector_binding(NON_BUNDLED_FONT_SELECTOR)

    with pytest.raises(AffectedSlideSelectorError, match="hash mismatch"):
        resolve_named_selector(
            NON_BUNDLED_FONT_SELECTOR,
            f"sha256:{'0' * 64}",
            DeckGraph(),
            BUNDLED_FONTS,
        )

    assert binding["selector_sha256"].startswith("sha256:")


def test_notes_and_comments_are_extracted_and_zero_only_the_related_slide(
    tmp_path: Path,
) -> None:
    pptx = tmp_path / "notes-comments.pptx"
    _write_relationship_fixture(pptx)
    deck = extract_deck_graph(pptx)
    item = next(
        candidate
        for candidate in load_checklist(BENCHMARK / "checklist", tier=3)
        if candidate.id == "deck.no-notes"
    )

    _, deck_results, flags = evaluate_checklist(deck, [item], tier_slides=[1])

    assert deck.notes_slides == {1}
    assert deck.comment_slides == {1}
    assert deck_results[0].passed is False
    assert flags[0].affected_slides == (1,)
    assert flags[0].tier_affected_slides == (1,)


def _write_relationship_fixture(path: Path) -> None:
    presentation_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    office_rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "ppt/presentation.xml",
            f'<p:presentation xmlns:p="{presentation_ns}" xmlns:r="{office_rel_ns}">'
            '<p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>'
            "</p:presentation>",
        )
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            f'<Relationships xmlns="{package_rel_ns}">'
            '<Relationship Id="rId1" '
            f'Type="{office_rel_ns}/slide" Target="slides/slide1.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "ppt/slides/slide1.xml",
            f'<p:sld xmlns:p="{presentation_ns}"><p:cSld><p:spTree/></p:cSld></p:sld>',
        )
        archive.writestr(
            "ppt/slides/_rels/slide1.xml.rels",
            f'<Relationships xmlns="{package_rel_ns}">'
            '<Relationship Id="rId1" '
            f'Type="{office_rel_ns}/notesSlide" Target="../notesSlides/notesSlide1.xml"/>'
            '<Relationship Id="rId2" '
            f'Type="{office_rel_ns}/comments" Target="../comments/comment1.xml"/>'
            "</Relationships>",
        )
