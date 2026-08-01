"""Deterministic operator-level positive and single-fault mutation fixtures.

These generated fixtures prove that the configured evaluator operator can pass
and can detect one isolated fault. They are not independent prompt, reference,
or asset evidence and must not be used to freeze a checklist assertion.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import rfc8785

from gloss.evaluate import evaluate_checklist
from gloss.inspect_ooxml import DeckGraph, SceneObject, SlideGraph, TextRun
from gloss.models import AntiCheatFlag, ChecklistItemResult, VisualComparisonResult

if TYPE_CHECKING:
    from gloss.checklist import ChecklistItem

OBJECT_SELECTORS = {"chart", "connector", "field", "group", "picture", "shape", "table"}
EVIDENCE_SCOPE = (
    "generated operator behavior only; not independent assertion provenance, review, or evidence"
)


@dataclass
class FixturePair:
    """One passing input and the corresponding one-fault negative input."""

    positive_deck: DeckGraph
    negative_deck: DeckGraph
    positive_visuals: list[VisualComparisonResult]
    negative_visuals: list[VisualComparisonResult]
    mutation_operator: str
    changed_path: str
    before: Any
    after: Any
    expected_negative_affected_slides: tuple[int, ...] = ()


def build_fixture_index(
    items: list[ChecklistItem], assertion_inventory: dict[str, Any]
) -> dict[str, Any]:
    """Build a stable per-candidate fixture index after exact inventory alignment."""
    assertions = assertion_inventory.get("assertions", [])
    if not isinstance(assertions, list):
        raise ValueError("Scored-assertion inventory assertions must be an array")
    assertions_by_item = {
        assertion["checklist_item_id"]: assertion
        for assertion in assertions
        if isinstance(assertion, dict) and "checklist_item_id" in assertion
    }
    item_ids = {item.id for item in items}
    if len(assertions_by_item) != len(assertions) or set(assertions_by_item) != item_ids:
        raise ValueError(
            "Checklist and scored-assertion candidate inventories do not align exactly"
        )

    entries: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda candidate: candidate.id):
        assertion = assertions_by_item[item.id]
        if assertion.get("assertion_id") != item.assertion_id:
            raise ValueError(f"Assertion identity mismatch for {item.id}")
        operator, unresolved_reason = _operator_for(item)
        executable = operator is not None
        entries.append(
            {
                "checklist_item_id": item.id,
                "assertion_id": item.assertion_id,
                "scope": item.scope,
                "slide": item.slide,
                "tier": item.tier,
                "verification_method": item.verification.method,
                "selector": item.verification.selector,
                "operator_coverage_status": "executable" if executable else "unimplemented",
                "mutation_operator": operator,
                "positive_fixture_id": f"fixture.{item.id}.positive" if executable else None,
                "single_fault_negative_fixture_id": (
                    f"fixture.{item.id}.single-fault-negative" if executable else None
                ),
                "mutation_expectation_id": f"mutation.{item.id}" if executable else None,
                "assertion_lifecycle_state": assertion.get("lifecycle_state", "unknown"),
                "assertion_evidence_status": assertion.get("evidence", {}).get("status", "unknown"),
                "release_evidence_claimed": False,
                "unresolved_reason": unresolved_reason,
            }
        )

    executable_count = sum(entry["operator_coverage_status"] == "executable" for entry in entries)
    evidence_complete_count = sum(
        entry["assertion_evidence_status"] == "complete" for entry in entries
    )
    operator_counts = Counter(
        entry["mutation_operator"] for entry in entries if entry["mutation_operator"] is not None
    )
    return {
        "schema_version": "1.0",
        "fixture_index_id": "gloss-generated-mutation-fixture-index-v1",
        "evidence_scope": EVIDENCE_SCOPE,
        "source_inventory_id": assertion_inventory.get("inventory_id"),
        "candidate_contract_sha256": _candidate_contract_sha256(items),
        "summary": {
            "candidate_items": len(entries),
            "executable_items": executable_count,
            "unimplemented_items": len(entries) - executable_count,
            "generated_positive_fixtures": executable_count,
            "generated_single_fault_negative_fixtures": executable_count,
            "generated_mutation_expectations": executable_count,
            "assertion_evidence_complete": evidence_complete_count,
            "assertion_evidence_pending_or_unknown": len(entries) - evidence_complete_count,
            "operator_counts": dict(sorted(operator_counts.items())),
        },
        "entries": entries,
    }


def build_mutation_expectations(fixture_index: dict[str, Any]) -> dict[str, Any]:
    """Build stable expectations for every executable generated mutation."""
    expectations: list[dict[str, Any]] = []
    unresolved: list[dict[str, str]] = []
    for entry in fixture_index["entries"]:
        if entry["operator_coverage_status"] != "executable":
            unresolved.append(
                {
                    "checklist_item_id": entry["checklist_item_id"],
                    "reason": entry["unresolved_reason"],
                }
            )
            continue
        expectations.append(
            {
                "mutation_expectation_id": entry["mutation_expectation_id"],
                "checklist_item_id": entry["checklist_item_id"],
                "assertion_id": entry["assertion_id"],
                "mutation_operator": entry["mutation_operator"],
                "fault_count": 1,
                "positive_expected_outcome": "passed",
                "negative_expected_outcome": "failed",
                "expected_failed_item_ids": [entry["checklist_item_id"]],
                "release_evidence_claimed": False,
            }
        )
    return {
        "schema_version": "1.0",
        "expectation_set_id": "gloss-generated-mutation-expectations-v1",
        "evidence_scope": EVIDENCE_SCOPE,
        "fixture_index_id": fixture_index["fixture_index_id"],
        "summary": {
            "expectations": len(expectations),
            "single_fault_expectations": len(expectations),
            "unimplemented": len(unresolved),
        },
        "expectations": expectations,
        "unresolved": unresolved,
    }


def execute_fixture_matrix(
    items: list[ChecklistItem], fixture_index: dict[str, Any]
) -> dict[str, Any]:
    """Materialize and execute every indexed fixture pair through the evaluator."""
    items_by_id = {item.id: item for item in items}
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for entry in fixture_index["entries"]:
        item_id = entry["checklist_item_id"]
        if entry["operator_coverage_status"] != "executable":
            skipped.append({"checklist_item_id": item_id, "reason": entry["unresolved_reason"]})
            continue
        item = items_by_id[item_id]
        pair = _generate_pair(item)
        positive_result, positive_flags = _evaluate_single(
            item, pair.positive_deck, pair.positive_visuals
        )
        negative_result, negative_flags = _evaluate_single(
            item, pair.negative_deck, pair.negative_visuals
        )
        actual_affected = _affected_slides(negative_flags)
        killed = (
            positive_result.passed
            and not negative_result.passed
            and actual_affected == pair.expected_negative_affected_slides
        )
        results.append(
            {
                "checklist_item_id": item_id,
                "mutation_expectation_id": entry["mutation_expectation_id"],
                "mutation_operator": pair.mutation_operator,
                "changed_path": pair.changed_path,
                "before": pair.before,
                "after": pair.after,
                "positive_passed": positive_result.passed,
                "negative_passed": negative_result.passed,
                "expected_negative_affected_slides": list(pair.expected_negative_affected_slides),
                "actual_negative_affected_slides": list(actual_affected),
                "mutant_killed": killed,
            }
        )

    killed_count = sum(result["mutant_killed"] for result in results)
    return {
        "schema_version": "1.0",
        "execution_report_id": "gloss-generated-mutation-execution-v1",
        "evidence_scope": EVIDENCE_SCOPE,
        "fixture_index_id": fixture_index["fixture_index_id"],
        "summary": {
            "candidate_items": len(fixture_index["entries"]),
            "executed_positive_fixtures": len(results),
            "executed_single_fault_negative_fixtures": len(results),
            "killed_mutants": killed_count,
            "survived_mutants": len(results) - killed_count,
            "unimplemented_items": len(skipped),
            "assertion_evidence_completed_by_this_run": 0,
        },
        "results": results,
        "unimplemented": skipped,
    }


def _operator_for(item: ChecklistItem) -> tuple[str | None, str | None]:
    method = item.verification.method
    selector = item.verification.selector
    if item.scope == "slide" and method == "object_compare" and selector in OBJECT_SELECTORS:
        return f"decrement-{selector}-count", None
    mapping = {
        ("slide", "text_match", "slide_text"): "replace-required-text",
        ("slide", "hash_match", "approved_asset"): "replace-approved-asset-hash",
        ("slide", "layout_check", "placeholder"): "remove-required-placeholder",
        ("slide", "layout_check", "master_ref"): "clear-layout-reference",
        ("slide", "anti_cheat", "font_policy"): "substitute-non-bundled-font",
        ("slide", "visual_ssim", "full_slide"): "lower-ssim-below-threshold",
        ("deck", "object_compare", "slide_count"): "change-exact-slide-count",
        ("deck", "layout_check", "master_count"): "decrement-master-count",
        ("deck", "layout_check", "layout_count"): "decrement-layout-count",
        ("deck", "anti_cheat", "font_policy"): "substitute-non-bundled-font",
        ("deck", "anti_cheat", "no_notes"): "add-speaker-notes-relationship",
        ("deck", "hash_match", "asset_manifest"): "replace-one-approved-asset-hash",
        ("deck", "visual_ssim", "all_slides"): "lower-one-slide-ssim",
    }
    operator = mapping.get((item.scope, method, selector))
    if operator is None:
        return None, f"No executable fixture operator for {item.scope}:{method}:{selector}"
    return operator, None


def _generate_pair(item: ChecklistItem) -> FixturePair:
    operator, unresolved = _operator_for(item)
    if operator is None:
        raise ValueError(unresolved)
    if item.scope == "slide":
        return _generate_slide_pair(item, operator)
    return _generate_deck_pair(item, operator)


def _generate_slide_pair(item: ChecklistItem, operator: str) -> FixturePair:
    slide_number = item.slide or 1
    slide = SlideGraph(slide_number=slide_number)
    positive = DeckGraph(slides=[slide], master_names=["Fixture Master"], layout_names=["Fixture"])
    visuals: list[VisualComparisonResult] = []
    changed_path = f"slides[{slide_number}]"
    before: Any = None
    after: Any = None

    if item.verification.method == "object_compare":
        count = _required_count(item)
        slide.objects = [_object_for_selector(item.verification.selector) for _ in range(count)]
        negative = deepcopy(positive)
        negative.slides[0].objects.pop()
        changed_path += f".objects[{count - 1}]"
        before, after = "present", "removed"
    elif item.verification.method == "text_match":
        expected = item.verification.expectation.get("contains")
        if not isinstance(expected, str) or not expected:
            raise ValueError(f"Unsupported text expectation for {item.id}")
        slide.objects = [SceneObject(obj_type="shape", text_runs=[TextRun(text=expected)])]
        negative = deepcopy(positive)
        negative.slides[0].objects[0].text_runs[0].text = "single-fault replacement"
        changed_path += ".objects[0].text_runs[0].text"
        before, after = expected, "single-fault replacement"
    elif item.verification.method == "hash_match":
        expected_hash = item.verification.expectation.get("sha256")
        if not isinstance(expected_hash, str) or not expected_hash:
            raise ValueError(f"Unsupported asset hash expectation for {item.id}")
        slide.objects = [SceneObject(obj_type="picture")]
        positive.media_hashes = {"ppt/media/fixture.bin": expected_hash}
        negative = deepcopy(positive)
        negative.media_hashes["ppt/media/fixture.bin"] = "0" * 64
        changed_path = "media_hashes[ppt/media/fixture.bin]"
        before, after = expected_hash, "0" * 64
    elif item.verification.method == "layout_check" and item.verification.selector == "placeholder":
        count = max(1, int(item.verification.expectation.get("min_count", 1)))
        placeholder_type = str(item.verification.expectation.get("placeholder_type", "title"))
        slide.objects = [
            SceneObject(obj_type="shape", placeholder_type=placeholder_type) for _ in range(count)
        ]
        negative = deepcopy(positive)
        negative.slides[0].objects.pop()
        changed_path += f".objects[{count - 1}]"
        before, after = "required placeholder", "removed"
    elif item.verification.method == "layout_check":
        slide.layout_ref = "../slideLayouts/slideLayout1.xml"
        negative = deepcopy(positive)
        negative.slides[0].layout_ref = ""
        changed_path += ".layout_ref"
        before, after = slide.layout_ref, ""
    elif item.verification.method == "anti_cheat":
        slide.objects = [
            SceneObject(
                obj_type="shape",
                text_runs=[TextRun(text="fixture", font_family="Carlito")],
            )
        ]
        negative = deepcopy(positive)
        negative.slides[0].objects[0].text_runs[0].font_family = "Arial"
        changed_path += ".objects[0].text_runs[0].font_family"
        before, after = "Carlito", "Arial"
    elif item.verification.method == "visual_ssim":
        threshold = float(item.verification.expectation.get("min_ssim", 0.9999))
        visuals = [VisualComparisonResult(slide_number, 1.0, True)]
        negative = deepcopy(positive)
        negative_visuals = [
            VisualComparisonResult(slide_number, max(0.0, threshold - 0.0001), False)
        ]
        return FixturePair(
            positive,
            negative,
            visuals,
            negative_visuals,
            operator,
            f"visual_results[{slide_number}].ssim",
            1.0,
            negative_visuals[0].ssim,
        )
    else:
        raise ValueError(f"Unsupported slide fixture operator for {item.id}")

    affected = (slide_number,) if item.failure_mode.automatic_fail_if else ()
    return FixturePair(
        positive,
        negative,
        visuals,
        deepcopy(visuals),
        operator,
        changed_path,
        before,
        after,
        affected,
    )


def _generate_deck_pair(item: ChecklistItem, operator: str) -> FixturePair:
    expectation = item.verification.expectation
    visuals: list[VisualComparisonResult] = []
    before: Any
    after: Any
    if operator == "change-exact-slide-count":
        count = int(expectation.get("exact_count", 20))
        positive = DeckGraph(slides=[SlideGraph(number) for number in range(1, count + 1)])
        negative = deepcopy(positive)
        if count:
            negative.slides.pop()
            before, after = count, count - 1
        else:
            negative.slides.append(SlideGraph(1))
            before, after = 0, 1
        changed_path = "slides.length"
    elif operator in {"decrement-master-count", "decrement-layout-count"}:
        count = max(1, int(expectation.get("min_count", 1)))
        positive = DeckGraph(slides=[SlideGraph(1)])
        attribute = "master_names" if operator == "decrement-master-count" else "layout_names"
        setattr(positive, attribute, [f"Fixture {index}" for index in range(count)])
        negative = deepcopy(positive)
        getattr(negative, attribute).pop()
        changed_path = f"{attribute}.length"
        before, after = count, count - 1
    elif operator == "substitute-non-bundled-font":
        positive = DeckGraph(
            slides=[
                SlideGraph(
                    1,
                    objects=[
                        SceneObject(
                            obj_type="shape",
                            text_runs=[TextRun(text="one", font_family="Carlito")],
                        )
                    ],
                ),
                SlideGraph(
                    2,
                    objects=[
                        SceneObject(
                            obj_type="shape",
                            text_runs=[TextRun(text="two", font_family="Noto Sans")],
                        )
                    ],
                ),
            ]
        )
        negative = deepcopy(positive)
        negative.slides[1].objects[0].text_runs[0].font_family = "Arial"
        changed_path = "slides[2].objects[0].text_runs[0].font_family"
        before, after = "Noto Sans", "Arial"
        return FixturePair(
            positive,
            negative,
            visuals,
            deepcopy(visuals),
            operator,
            changed_path,
            before,
            after,
            (2,),
        )
    elif operator == "add-speaker-notes-relationship":
        positive = DeckGraph(slides=[SlideGraph(1)])
        negative = deepcopy(positive)
        negative.notes_slides.add(1)
        changed_path = "notes_slides"
        before, after = [], [1]
        return FixturePair(
            positive,
            negative,
            visuals,
            deepcopy(visuals),
            operator,
            changed_path,
            before,
            after,
            (1,),
        )
    elif operator == "replace-one-approved-asset-hash":
        expected_hashes = expectation.get("asset_hashes", {})
        if not isinstance(expected_hashes, dict) or not expected_hashes:
            raise ValueError(f"Unsupported deck hash expectation for {item.id}")
        positive = DeckGraph(
            slides=[SlideGraph(1)],
            media_hashes={
                f"ppt/media/{asset_id}.bin": digest
                for asset_id, digest in sorted(expected_hashes.items())
            },
        )
        negative = deepcopy(positive)
        first_asset = sorted(expected_hashes)[0]
        key = f"ppt/media/{first_asset}.bin"
        negative.media_hashes[key] = "0" * 64
        changed_path = f"media_hashes[{key}]"
        before, after = positive.media_hashes[key], "0" * 64
    elif operator == "lower-one-slide-ssim":
        threshold = float(expectation.get("min_ssim", 0.9999))
        positive = DeckGraph(slides=[SlideGraph(1), SlideGraph(2)])
        negative = deepcopy(positive)
        visuals = [VisualComparisonResult(1, 1.0, True), VisualComparisonResult(2, 1.0, True)]
        negative_visuals = deepcopy(visuals)
        negative_visuals[1].ssim = max(0.0, threshold - 0.0001)
        negative_visuals[1].pixel_exact = False
        return FixturePair(
            positive,
            negative,
            visuals,
            negative_visuals,
            operator,
            "visual_results[2].ssim",
            1.0,
            negative_visuals[1].ssim,
        )
    else:
        raise ValueError(f"Unsupported deck fixture operator for {item.id}")

    return FixturePair(
        positive,
        negative,
        visuals,
        deepcopy(visuals),
        operator,
        changed_path,
        before,
        after,
    )


def _required_count(item: ChecklistItem) -> int:
    expectation = item.verification.expectation
    if "exact_count" in expectation:
        count = int(expectation["exact_count"])
    else:
        count = int(expectation.get("min_count", 1 if expectation.get("required") else 0))
    if count < 1:
        raise ValueError(f"Cannot generate a decrement mutation for zero-count item {item.id}")
    return count


def _object_for_selector(selector: str) -> SceneObject:
    if selector == "chart":
        return SceneObject(obj_type="chart", is_chart=True)
    if selector == "field":
        return SceneObject(obj_type="shape", field_type="slidenum")
    if selector == "picture":
        return SceneObject(obj_type="picture")
    if selector == "table":
        return SceneObject(obj_type="table", is_table=True)
    return SceneObject(obj_type=selector)


def _evaluate_single(
    item: ChecklistItem,
    deck: DeckGraph,
    visuals: list[VisualComparisonResult],
) -> tuple[ChecklistItemResult, list[AntiCheatFlag]]:
    tier_slides = [slide.slide_number for slide in deck.slides]
    slide_results, deck_results, flags = evaluate_checklist(
        deck,
        [item],
        visuals,
        tier_slides=tier_slides,
    )
    if item.scope == "deck":
        if len(deck_results) != 1:
            raise ValueError(f"Expected one deck result for {item.id}")
        return deck_results[0], flags
    item_results = [result for slide in slide_results for result in slide.items]
    if len(item_results) != 1:
        raise ValueError(f"Expected one slide result for {item.id}")
    return item_results[0], flags


def _affected_slides(flags: list[AntiCheatFlag]) -> tuple[int, ...]:
    return tuple(sorted({slide for flag in flags for slide in flag.affected_slides}))


def _candidate_contract_sha256(items: list[ChecklistItem]) -> str:
    normalized: list[dict[str, Any]] = [
        {
            "id": item.id,
            "assertion_id": item.assertion_id,
            "scope": item.scope,
            "slide": item.slide,
            "tier": item.tier,
            "verification": {
                "method": item.verification.method,
                "selector": item.verification.selector,
                "expectation": item.verification.expectation,
            },
            "failure_mode": {
                "automatic_fail_if": item.failure_mode.automatic_fail_if,
                "propagation": item.failure_mode.propagation,
                "affected_slides": item.failure_mode.affected_slides,
            },
        }
        for item in sorted(items, key=lambda candidate: candidate.id)
    ]
    payload: Any = normalized
    return f"sha256:{hashlib.sha256(rfc8785.dumps(payload)).hexdigest()}"
