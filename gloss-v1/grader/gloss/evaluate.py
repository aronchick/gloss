"""Checklist evaluator — runs verification methods against extracted scene graphs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gloss.affected_slides import resolve_named_selector
from gloss.checklist import SEVERITY_WEIGHTS, ChecklistItem
from gloss.models import (
    AntiCheatFlag,
    ChecklistItemResult,
    Severity,
    SlideResult,
    SourceOfTruth,
)

if TYPE_CHECKING:
    from gloss.inspect_ooxml import DeckGraph, SceneObject, SlideGraph
    from gloss.models import VisualComparisonResult

# Allowed fonts per §3 / §4.3
BUNDLED_FONTS = {
    "carlito",
    "caladea",
    "liberation sans",
    "liberation serif",
    "liberation mono",
    "noto sans",
    "noto sans arabic",
    "noto sans jp",
    "noto sans cjk",
    "noto sans cjk jp",
    "noto serif",
    "noto serif cjk",
    "noto serif cjk jp",
    # Theme font references (these are placeholders, not real names)
    "+mj-lt",
    "+mn-lt",
    "+mj-ea",
    "+mn-ea",
    "+mj-cs",
    "+mn-cs",
}


def evaluate_checklist(
    deck_graph: DeckGraph,
    items: list[ChecklistItem],
    visual_results: list[VisualComparisonResult] | None = None,
    tier_slides: list[int] | None = None,
) -> tuple[list[SlideResult], list[ChecklistItemResult], list[AntiCheatFlag]]:
    """Evaluate all checklist items against the deck graph.

    Returns:
        - slide_results: per-slide results with item pass/fail
        - deck_item_results: deck-scoped item results
        - anti_cheat_flags: triggered anti-cheat rules and exact propagation
    """
    visual_by_slide: dict[int, VisualComparisonResult] = {}
    if visual_results:
        for vr in visual_results:
            visual_by_slide[vr.slide_number] = vr

    slide_graph_by_num: dict[int, SlideGraph] = {}
    for slide_graph in deck_graph.slides:
        slide_graph_by_num[slide_graph.slide_number] = slide_graph

    # Separate slide-level and deck-level items
    slide_items: dict[int, list[ChecklistItem]] = {}
    deck_items: list[ChecklistItem] = []
    for item in items:
        if item.scope == "deck":
            deck_items.append(item)
        elif item.slide is not None:
            slide_items.setdefault(item.slide, []).append(item)

    effective_tier_slides = sorted(
        set(tier_slides) if tier_slides is not None else set(slide_graph_by_num)
    )
    anti_cheat_flags: list[AntiCheatFlag] = []
    zeroed_slides: set[int] = set()

    # Evaluate deck-level items
    deck_item_results: list[ChecklistItemResult] = []
    for item in deck_items:
        result = _evaluate_deck_item(item, deck_graph, list(visual_by_slide.values()))
        _decorate_result(result, item, effective_tier_slides)
        deck_item_results.append(result)
        if not result.passed and item.failure_mode.automatic_fail_if:
            affected = _failure_affected_slides(item, None, deck_graph)
            tier_affected = sorted(set(affected) & set(effective_tier_slides))
            zeroed_slides.update(tier_affected)
            anti_cheat_flags.extend(_build_anti_cheat_flags(item, result, affected, tier_affected))

    # Evaluate slide-level items
    all_slide_nums = sorted(set(slide_graph_by_num.keys()) | set(slide_items.keys()))
    if tier_slides is not None:
        all_slide_nums = [n for n in all_slide_nums if n in tier_slides]

    slide_results: list[SlideResult] = []
    for slide_num in all_slide_nums:
        sg = slide_graph_by_num.get(slide_num)
        vis = visual_by_slide.get(slide_num)
        items_for_slide = slide_items.get(slide_num, [])

        item_results: list[ChecklistItemResult] = []
        for item in items_for_slide:
            if sg is not None:
                result = _evaluate_slide_item(item, sg, deck_graph, vis)
            else:
                result = ChecklistItemResult(
                    id=item.id,
                    passed=False,
                    severity=Severity(item.severity),
                    source_of_truth=SourceOfTruth(item.source_of_truth),
                    details=f"Slide {slide_num} not found in submission",
                )
            _decorate_result(result, item, [slide_num])

            # Check for auto-fail propagation
            if not result.passed and item.failure_mode.automatic_fail_if:
                affected = _failure_affected_slides(item, slide_num, deck_graph)
                tier_affected = sorted(set(affected) & set(effective_tier_slides))
                anti_cheat_flags.extend(
                    _build_anti_cheat_flags(item, result, affected, tier_affected)
                )
                if item.failure_mode.propagation == "zero_slide":
                    zeroed_slides.update(tier_affected)

            item_results.append(result)

        sr = SlideResult(
            slide_number=slide_num,
            tier=_slide_tier(slide_num),
            visual_ssim=vis.ssim if vis else 0.0,
            visual_pixel_exact=vis.pixel_exact if vis else False,
            items=item_results,
        )
        slide_results.append(sr)

    # Apply zero_slide propagation: force-fail all items on zeroed slides
    for sr in slide_results:
        if sr.slide_number in zeroed_slides:
            for item_result in sr.items:
                if item_result.passed:
                    item_result.passed = False
                    item_result.details = f"Zeroed by anti-cheat rule on slide {sr.slide_number}"
                    item_result.outcome_code = "zeroed_by_anti_cheat"

    return slide_results, deck_item_results, anti_cheat_flags


def _decorate_result(
    result: ChecklistItemResult,
    item: ChecklistItem,
    tier_affected_slides: list[int],
) -> None:
    result.assertion_id = item.assertion_id or _derived_assertion_id(item.id)
    result.weight = item.weight
    result.outcome_code = "passed" if result.passed else "failed"
    result.tier_affected_slides = sorted(set(tier_affected_slides))


def _derived_assertion_id(item_id: str) -> str:
    prefix, separator, suffix = item_id.partition(".")
    if not separator:
        return f"deck.assert-{item_id}"
    return f"{prefix}.assert-{suffix}"


def _failure_affected_slides(
    item: ChecklistItem,
    current_slide: int | None,
    deck: DeckGraph,
) -> list[int]:
    mode = item.failure_mode.affected_slides.get("mode")
    if mode == "named_selector":
        selector_id = item.failure_mode.affected_slides.get("selector_id")
        selector_sha256 = item.failure_mode.affected_slides.get("selector_sha256")
        if not isinstance(selector_id, str) or not isinstance(selector_sha256, str):
            raise ValueError(f"Incomplete named affected-slide selector for {item.id}")
        return resolve_named_selector(selector_id, selector_sha256, deck, BUNDLED_FONTS)

    configured = item.failure_mode.affected_slides.get("slides", [])
    if (
        configured
        and isinstance(configured, list)
        and all(isinstance(value, int) and not isinstance(value, bool) for value in configured)
    ):
        return sorted(set(configured))
    return [current_slide] if current_slide is not None else []


def _build_anti_cheat_flags(
    item: ChecklistItem,
    result: ChecklistItemResult,
    affected_slides: list[int],
    tier_affected_slides: list[int],
) -> list[AntiCheatFlag]:
    disposition = item.failure_mode.propagation
    if disposition not in {"zero_slide", "zero_affected_slides"}:
        disposition = "warning"
    return [
        AntiCheatFlag(
            rule_id=rule_id,
            disposition=disposition,
            affected_slides=tuple(affected_slides),
            tier_affected_slides=tuple(tier_affected_slides),
            details=result.details,
        )
        for rule_id in item.failure_mode.automatic_fail_if
    ]


def compute_fidelity_score(
    slide_results: list[SlideResult],
    deck_item_results: list[ChecklistItemResult],
) -> tuple[float, int, int]:
    """Compute the weighted fidelity score per §10.2.

    Returns (fidelity_score, passed_items, total_items).
    """
    total_weight = 0
    passed_weight = 0
    total_items = 0
    passed_items = 0

    for sr in slide_results:
        for item in sr.items:
            w = SEVERITY_WEIGHTS.get(item.severity.value, 0)
            if w == 0:
                continue  # informational items excluded from scoring
            total_weight += w
            total_items += 1
            if item.passed:
                passed_weight += w
                passed_items += 1

    for item in deck_item_results:
        w = SEVERITY_WEIGHTS.get(item.severity.value, 0)
        if w == 0:
            continue
        total_weight += w
        total_items += 1
        if item.passed:
            passed_weight += w
            passed_items += 1

    fidelity = passed_weight / total_weight if total_weight > 0 else 0.0
    return fidelity, passed_items, total_items


def compute_tier_scores(
    slide_results: list[SlideResult],
    deck_item_results: list[ChecklistItemResult],
    tier: int,
) -> dict[str, dict[str, int | float] | None]:
    """Compute only the targeted tier score; non-targeted tiers are null."""
    tier_map: dict[int, list[int]] = {
        1: list(range(1, 6)),
        2: list(range(1, 13)),
        3: list(range(1, 21)),
    }

    scores: dict[str, dict[str, int | float] | None] = {}
    for t in range(1, 4):
        if t != tier:
            scores[f"level_{t}"] = None
            continue

        tier_slide_nums = set(tier_map[t])
        tier_slide_results = [sr for sr in slide_results if sr.slide_number in tier_slide_nums]

        # Deck items apply to all tiers
        fidelity, passed, total = compute_fidelity_score(tier_slide_results, deck_item_results)
        scores[f"level_{t}"] = {
            "fidelity_score": round(fidelity, 4),
            "passed": passed,
            "total": total,
        }

    return scores


# --- Verification method dispatch ---


def _evaluate_slide_item(
    item: ChecklistItem,
    slide: SlideGraph,
    deck: DeckGraph,
    visual: VisualComparisonResult | None,
) -> ChecklistItemResult:
    """Evaluate a single slide-level checklist item."""
    method = item.verification.method
    if method == "object_compare":
        return _verify_object_compare(item, slide)
    if method == "text_match":
        return _verify_text_match(item, slide)
    if method == "hash_match":
        return _verify_hash_match(item, slide, deck)
    if method == "field_check":
        return _verify_field_check(item, slide)
    if method == "layout_check":
        return _verify_layout_check(item, slide, deck)
    if method == "anti_cheat":
        return _verify_anti_cheat(item, slide, deck)
    if method == "visual_ssim":
        return _verify_visual_ssim(item, visual)
    return ChecklistItemResult(
        id=item.id,
        passed=False,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Unknown verification method: {method}",
    )


def _evaluate_deck_item(
    item: ChecklistItem,
    deck: DeckGraph,
    visual_results: list[VisualComparisonResult],
) -> ChecklistItemResult:
    """Evaluate a single deck-level checklist item."""
    method = item.verification.method
    if method == "object_compare":
        return _verify_deck_object_compare(item, deck)
    if method == "layout_check":
        return _verify_deck_layout_check(item, deck)
    if method == "anti_cheat":
        return _verify_deck_anti_cheat(item, deck)
    if method == "hash_match":
        return _verify_deck_hash_match(item, deck)
    if method == "visual_ssim":
        return _verify_deck_visual_ssim(item, visual_results)
    return ChecklistItemResult(
        id=item.id,
        passed=False,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Unknown deck verification method: {method}",
    )


# --- Verification implementations ---


def _verify_object_compare(item: ChecklistItem, slide: SlideGraph) -> ChecklistItemResult:
    """Verify object presence/count on a slide by type selector."""
    selector = item.verification.selector
    expectation = item.verification.expectation
    all_objects = _collect_objects_recursive(slide.objects)

    matched = [o for o in all_objects if _matches_selector(o, selector)]
    count = len(matched)

    exact_count = expectation.get("exact_count")
    min_count = expectation.get("min_count", 0)
    required = expectation.get("required", False)

    passed = True
    details = f"Found {count} {selector} object(s)"

    if required and count == 0:
        passed = False
        details = f"Required {selector} not found"
    elif exact_count is not None and count != exact_count:
        passed = False
        details = f"Expected {exact_count} {selector}, found {count}"
    elif count < min_count:
        passed = False
        details = f"Expected at least {min_count} {selector}, found {count}"

    return ChecklistItemResult(
        id=item.id,
        passed=passed,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=details,
    )


def _verify_text_match(item: ChecklistItem, slide: SlideGraph) -> ChecklistItemResult:
    """Verify text content exists on a slide."""
    expectation = item.verification.expectation
    expected_text = expectation.get("contains", "")
    exact_text = expectation.get("exact", "")
    not_contains = expectation.get("not_contains", "")

    all_text = _collect_all_text(slide)

    passed = True
    details = ""

    if expected_text and expected_text not in all_text:
        passed = False
        details = f"Expected text containing '{expected_text}' not found"
    elif exact_text and exact_text != all_text.strip():
        passed = False
        details = "Text does not exactly match expected"
    elif not_contains and not_contains in all_text:
        passed = False
        details = f"Found prohibited text '{not_contains}'"
    else:
        details = "Text match passed"

    return ChecklistItemResult(
        id=item.id,
        passed=passed,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=details,
    )


def _verify_hash_match(
    item: ChecklistItem, slide: SlideGraph, deck: DeckGraph
) -> ChecklistItemResult:
    """Verify embedded media hashes match the asset manifest."""
    expectation = item.verification.expectation
    expected_hash = expectation.get("sha256", "")
    asset_id = expectation.get("asset_id", "")

    # Collect picture objects on this slide
    all_objects = _collect_objects_recursive(slide.objects)
    pictures = [o for o in all_objects if o.is_picture]

    if not pictures:
        return ChecklistItemResult(
            id=item.id,
            passed=False,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details="No picture objects found on slide",
        )

    if expected_hash:
        # Check if any embedded media matches the expected hash
        found = any(h == expected_hash for h in deck.media_hashes.values())
        return ChecklistItemResult(
            id=item.id,
            passed=found,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details=f"Asset hash {'matched' if found else 'not found'}: {asset_id}",
        )

    return ChecklistItemResult(
        id=item.id,
        passed=True,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details="Hash check skipped (no expected hash provided)",
    )


def _verify_field_check(item: ChecklistItem, slide: SlideGraph) -> ChecklistItemResult:
    """Verify native field presence (slidenum, datetime, etc.)."""
    expectation = item.verification.expectation
    expected_field = expectation.get("field_type", "")

    all_objects = _collect_objects_recursive(slide.objects)
    fields = [o for o in all_objects if o.field_type]

    if expected_field:
        found = any(o.field_type == expected_field for o in fields)
        return ChecklistItemResult(
            id=item.id,
            passed=found,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details=f"Field '{expected_field}' {'found' if found else 'not found'}",
        )

    return ChecklistItemResult(
        id=item.id,
        passed=len(fields) > 0,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Found {len(fields)} field(s)",
    )


def _verify_layout_check(
    item: ChecklistItem, slide: SlideGraph, deck: DeckGraph
) -> ChecklistItemResult:
    """Verify placeholder usage and layout/master binding."""
    expectation = item.verification.expectation
    selector = item.verification.selector

    all_objects = _collect_objects_recursive(slide.objects)

    if selector == "placeholder":
        expected_type = expectation.get("placeholder_type", "")
        min_count = expectation.get("min_count", 1)

        placeholders = [o for o in all_objects if o.placeholder_type]
        if expected_type:
            placeholders = [o for o in placeholders if o.placeholder_type == expected_type]

        passed = len(placeholders) >= min_count
        return ChecklistItemResult(
            id=item.id,
            passed=passed,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details=(
                f"Found {len(placeholders)} '{expected_type or 'any'}' placeholder(s), "
                f"need {min_count}"
            ),
        )

    if selector == "master_ref":
        has_layout = bool(slide.layout_ref)
        return ChecklistItemResult(
            id=item.id,
            passed=has_layout,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details=f"Layout ref: {slide.layout_ref or 'none'}",
        )

    return ChecklistItemResult(
        id=item.id,
        passed=False,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Unknown layout_check selector: {selector}",
    )


def _verify_anti_cheat(
    item: ChecklistItem, slide: SlideGraph, deck: DeckGraph
) -> ChecklistItemResult:
    """Run anti-cheat checks on a slide."""
    selector = item.verification.selector
    all_objects = _collect_objects_recursive(slide.objects)

    if selector == "font_policy":
        return _check_font_policy(item, all_objects)
    if selector == "no_full_slide_raster":
        return _check_no_full_slide_raster(item, all_objects)
    if selector == "no_notes":
        # This is a deck-level check typically, but can be slide-scoped
        return ChecklistItemResult(
            id=item.id,
            passed=True,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details="Notes check requires deck-level inspection",
        )

    return ChecklistItemResult(
        id=item.id,
        passed=True,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Anti-cheat selector '{selector}' not applicable at slide level",
    )


def _verify_visual_ssim(
    item: ChecklistItem,
    visual: VisualComparisonResult | None,
) -> ChecklistItemResult:
    """Verify visual SSIM against threshold."""
    if visual is None:
        return ChecklistItemResult(
            id=item.id,
            passed=False,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details="No visual comparison data available",
        )

    threshold = item.verification.expectation.get("min_ssim", 0.9999)
    passed = visual.ssim >= threshold
    return ChecklistItemResult(
        id=item.id,
        passed=passed,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"SSIM={visual.ssim:.6f} (threshold={threshold})",
    )


# --- Deck-level verification ---


def _verify_deck_object_compare(item: ChecklistItem, deck: DeckGraph) -> ChecklistItemResult:
    """Deck-level object count/presence check."""
    expectation = item.verification.expectation
    selector = item.verification.selector

    if selector == "slide_count":
        expected = expectation.get("exact_count", 20)
        actual = len(deck.slides)
        return ChecklistItemResult(
            id=item.id,
            passed=actual == expected,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details=f"Slide count: {actual} (expected {expected})",
        )

    return ChecklistItemResult(
        id=item.id,
        passed=False,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Unknown deck object_compare selector: {selector}",
    )


def _verify_deck_layout_check(item: ChecklistItem, deck: DeckGraph) -> ChecklistItemResult:
    """Verify deck-level layout/master usage."""
    expectation = item.verification.expectation
    selector = item.verification.selector

    if selector == "master_count":
        min_count = expectation.get("min_count", 1)
        actual = len(deck.master_names)
        return ChecklistItemResult(
            id=item.id,
            passed=actual >= min_count,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details=f"Master count: {actual} (need >= {min_count})",
        )

    if selector == "layout_count":
        min_count = expectation.get("min_count", 1)
        actual = len(deck.layout_names)
        return ChecklistItemResult(
            id=item.id,
            passed=actual >= min_count,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details=f"Layout count: {actual} (need >= {min_count})",
        )

    return ChecklistItemResult(
        id=item.id,
        passed=False,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Unknown deck layout_check selector: {selector}",
    )


def _verify_deck_anti_cheat(item: ChecklistItem, deck: DeckGraph) -> ChecklistItemResult:
    """Deck-level anti-cheat checks."""
    selector = item.verification.selector

    if selector == "font_policy":
        # v1 policy: only check fonts that actually appear in text runs on slides
        # (what will render). Theme/master fallback fonts for unused scripts are
        # informational only — flagged but not auto-failed.
        rendered_fonts: set[str] = set()
        for sg in deck.slides:
            for obj in _collect_objects_recursive(sg.objects):
                for run in obj.text_runs:
                    if run.font_family and not run.font_family.startswith("+"):
                        rendered_fonts.add(run.font_family)

        bad_rendered = {f for f in rendered_fonts if f.lower() not in BUNDLED_FONTS}

        # Also note theme fonts for informational purposes
        theme_only = deck.all_fonts - rendered_fonts
        bad_theme = {
            f for f in theme_only if f.lower() not in BUNDLED_FONTS and not f.startswith("+")
        }

        passed = len(bad_rendered) == 0
        details_parts: list[str] = []
        if bad_rendered:
            details_parts.append(f"Non-bundled rendered fonts: {sorted(bad_rendered)}")
        if bad_theme:
            details_parts.append(f"Non-bundled theme fallbacks (informational): {len(bad_theme)}")
        if not details_parts:
            details_parts.append("All rendered fonts in bundled set")

        return ChecklistItemResult(
            id=item.id,
            passed=passed,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details="; ".join(details_parts),
        )

    if selector == "no_notes":
        affected = sorted(deck.notes_slides | deck.comment_slides)
        return ChecklistItemResult(
            id=item.id,
            passed=not affected,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details=(
                f"Notes or comments found on slides: {affected}"
                if affected
                else "No slide notes or comments detected"
            ),
        )

    return ChecklistItemResult(
        id=item.id,
        passed=True,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Deck anti-cheat '{selector}' check passed",
    )


def _verify_deck_hash_match(item: ChecklistItem, deck: DeckGraph) -> ChecklistItemResult:
    """Verify deck-level asset hash requirements."""
    expectation = item.verification.expectation
    expected_hashes = expectation.get("asset_hashes", {})

    if not expected_hashes:
        has_media = len(deck.media_hashes) > 0
        return ChecklistItemResult(
            id=item.id,
            passed=has_media,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details=f"Deck has {len(deck.media_hashes)} embedded media file(s)",
        )

    actual_hashes = set(deck.media_hashes.values())
    missing = {k: v for k, v in expected_hashes.items() if v not in actual_hashes}
    passed = len(missing) == 0
    return ChecklistItemResult(
        id=item.id,
        passed=passed,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Missing asset hashes: {list(missing.keys())}"
        if missing
        else "All asset hashes matched",
    )


def _verify_deck_visual_ssim(
    item: ChecklistItem,
    visual_results: list[VisualComparisonResult],
) -> ChecklistItemResult:
    """Require every targeted slide render to meet the deck-level SSIM floor."""
    threshold = float(item.verification.expectation.get("min_ssim", 0.9999))
    if not visual_results:
        return ChecklistItemResult(
            id=item.id,
            passed=False,
            severity=Severity(item.severity),
            source_of_truth=SourceOfTruth(item.source_of_truth),
            details="No visual comparison results available",
        )

    failures = [result for result in visual_results if result.ssim < threshold]
    minimum = min(result.ssim for result in visual_results)
    average = sum(result.ssim for result in visual_results) / len(visual_results)
    return ChecklistItemResult(
        id=item.id,
        passed=not failures,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=(
            f"{len(visual_results) - len(failures)}/{len(visual_results)} slides meet "
            f"SSIM {threshold:.4f}; minimum={minimum:.4f}, mean={average:.4f}"
        ),
    )


# --- Helpers ---


def _collect_objects_recursive(objects: list[SceneObject]) -> list[SceneObject]:
    """Flatten the object tree into a list."""
    result: list[SceneObject] = []
    for obj in objects:
        result.append(obj)
        if obj.children:
            result.extend(_collect_objects_recursive(obj.children))
    return result


def _matches_selector(obj: SceneObject, selector: str) -> bool:
    """Check if an object matches a type selector."""
    if selector == "table":
        return obj.is_table
    if selector == "chart":
        return obj.is_chart
    if selector == "picture":
        return obj.is_picture
    if selector == "group":
        return obj.obj_type == "group"
    if selector == "connector":
        return obj.obj_type == "connector"
    if selector == "placeholder":
        return bool(obj.placeholder_type)
    if selector == "shape":
        return obj.obj_type in {
            "shape",
            "picture",
            "table",
            "chart",
            "group",
            "connector",
            "graphicFrame",
        }
    if selector == "field":
        return bool(obj.field_type)
    return obj.obj_type == selector


def _collect_all_text(slide: SlideGraph) -> str:
    """Collect all text content from a slide."""
    texts: list[str] = []
    for obj in _collect_objects_recursive(slide.objects):
        for run in obj.text_runs:
            texts.append(run.text)
    return " ".join(texts)


def _check_font_policy(item: ChecklistItem, objects: list[SceneObject]) -> ChecklistItemResult:
    """Check that all fonts on a slide are in the bundled set."""
    bad_fonts: set[str] = set()
    for obj in objects:
        for run in obj.text_runs:
            if (
                run.font_family
                and run.font_family.lower() not in BUNDLED_FONTS
                and not run.font_family.startswith("+")
            ):
                bad_fonts.add(run.font_family)

    passed = len(bad_fonts) == 0
    return ChecklistItemResult(
        id=item.id,
        passed=passed,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details=f"Non-bundled fonts: {sorted(bad_fonts)}"
        if bad_fonts
        else "All fonts in bundled set",
    )


def _check_no_full_slide_raster(
    item: ChecklistItem, objects: list[SceneObject]
) -> ChecklistItemResult:
    """Check that no single raster covers >40% of slide area."""
    # Slide area in EMUs: 12192000 x 6858000
    slide_area = 12192000 * 6858000
    threshold = 0.4

    for obj in objects:
        if obj.is_picture:
            _, _, cx, cy = obj.bbox
            if cx > 0 and cy > 0:
                obj_area = cx * cy
                ratio = obj_area / slide_area
                if ratio > threshold:
                    return ChecklistItemResult(
                        id=item.id,
                        passed=False,
                        severity=Severity(item.severity),
                        source_of_truth=SourceOfTruth(item.source_of_truth),
                        details=(
                            f"Image '{obj.name}' covers {ratio:.1%} of slide "
                            f"(>{threshold:.0%} threshold)"
                        ),
                    )

    return ChecklistItemResult(
        id=item.id,
        passed=True,
        severity=Severity(item.severity),
        source_of_truth=SourceOfTruth(item.source_of_truth),
        details="No oversized raster images detected",
    )


def _slide_tier(slide_num: int) -> int:
    """Determine which tier a slide belongs to."""
    if slide_num <= 5:
        return 1
    if slide_num <= 12:
        return 2
    return 3
