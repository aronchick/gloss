"""Tests for the checklist evaluator and scoring logic."""

from __future__ import annotations

from typing import Any

from lxml import etree

from acidslide.checklist import ChecklistItem, FailureMode, Verification
from acidslide.evaluate import (
    compute_fidelity_score,
    compute_tier_scores,
    evaluate_checklist,
)
from acidslide.inspect_ooxml import DeckGraph, SceneObject, SlideGraph, TextRun, _parse_shape
from acidslide.models import VisualComparisonResult


def _make_item(
    id: str,
    scope: str = "slide",
    slide: int | None = 1,
    tier: int = 1,
    severity: str = "critical",
    method: str = "object_compare",
    selector: str = "table",
    expectation: dict[str, Any] | None = None,
    failure_mode: FailureMode | None = None,
) -> ChecklistItem:
    return ChecklistItem(
        schema_version="1.0",
        id=id,
        scope=scope,
        slide=slide,
        tier=tier,
        title=id,
        description="test",
        kind="structure",
        severity=severity,
        source_of_truth="ooxml",
        verification=Verification(
            method=method,
            selector=selector,
            expectation=expectation or {},
        ),
        failure_mode=failure_mode or FailureMode(),
    )


def _make_slide(
    slide_number: int = 1,
    objects: list[SceneObject] | None = None,
    layout_ref: str = "../slideLayouts/slideLayout1.xml",
) -> SlideGraph:
    sg = SlideGraph(slide_number=slide_number)
    sg.objects = objects or []
    sg.layout_ref = layout_ref
    return sg


def _make_deck(slides: list[SlideGraph] | None = None) -> DeckGraph:
    deck = DeckGraph()
    deck.slides = slides or []
    deck.master_names = ["Default"]
    deck.layout_names = ["Title", "Content"]
    return deck


class TestObjectCompare:
    def test_raster_filled_native_shape_is_picture_semantic_equivalent(self) -> None:
        shape = etree.fromstring(
            b"""<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <p:nvSpPr><p:cNvPr id="1" name="Masked image"/></p:nvSpPr>
              <p:spPr><a:blipFill><a:blip/></a:blipFill></p:spPr>
            </p:sp>"""
        )
        slide = _make_slide(objects=[_parse_shape(shape)])
        item = _make_item("s7.pictures", selector="picture", expectation={"min_count": 1})

        results, _, _ = evaluate_checklist(_make_deck([slide]), [item])

        assert results[0].items[0].passed is True

    def test_generic_shape_selector_counts_groups_and_descendants(self) -> None:
        group = SceneObject(
            obj_type="group",
            children=[SceneObject(obj_type="shape"), SceneObject(obj_type="shape")],
        )
        item = _make_item("s17.shapes", selector="shape", expectation={"min_count": 3})

        results, _, _ = evaluate_checklist(
            _make_deck([_make_slide(objects=[group])]),
            [item],
        )

        assert results[0].items[0].passed is True

    def test_table_found(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="table", is_table=True, table_rows=3, table_cols=4),
            ]
        )
        item = _make_item(
            "s3.table", selector="table", expectation={"exact_count": 1, "required": True}
        )
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert len(results) == 1
        assert results[0].items[0].passed is True

    def test_table_missing(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape"),
            ]
        )
        item = _make_item(
            "s3.table", selector="table", expectation={"exact_count": 1, "required": True}
        )
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is False
        assert (
            "not found" in results[0].items[0].details.lower()
            or "Expected" in results[0].items[0].details
        )

    def test_chart_found(self) -> None:
        slide = _make_slide(
            slide_number=4,
            objects=[
                SceneObject(obj_type="chart", is_chart=True),
            ],
        )
        item = _make_item(
            "s4.chart", slide=4, selector="chart", expectation={"exact_count": 1, "required": True}
        )
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is True

    def test_min_count(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape"),
                SceneObject(obj_type="shape"),
                SceneObject(obj_type="shape"),
            ]
        )
        item = _make_item("s1.shapes", selector="shape", expectation={"min_count": 2})
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is True


class TestTextMatch:
    def test_contains_found(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(
                    obj_type="shape",
                    text_runs=[TextRun(text="Hello World")],
                ),
            ]
        )
        item = _make_item("s1.text", method="text_match", expectation={"contains": "Hello"})
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is True

    def test_contains_not_found(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape", text_runs=[TextRun(text="Goodbye")]),
            ]
        )
        item = _make_item("s1.text", method="text_match", expectation={"contains": "Hello"})
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is False


class TestFieldCheck:
    def test_slidenum_field_found(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape", field_type="slidenum"),
            ]
        )
        item = _make_item("s12.field", method="field_check", expectation={"field_type": "slidenum"})
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is True

    def test_slidenum_field_missing(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape"),
            ]
        )
        item = _make_item("s12.field", method="field_check", expectation={"field_type": "slidenum"})
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is False


class TestLayoutCheck:
    def test_placeholder_found(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape", placeholder_type="title"),
            ]
        )
        item = _make_item(
            "s1.ph",
            method="layout_check",
            selector="placeholder",
            expectation={"placeholder_type": "title", "min_count": 1},
        )
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is True

    def test_placeholder_missing(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape"),
            ]
        )
        item = _make_item(
            "s1.ph",
            method="layout_check",
            selector="placeholder",
            expectation={"placeholder_type": "body", "min_count": 1},
        )
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is False

    def test_master_ref_present(self) -> None:
        slide = _make_slide(layout_ref="../slideLayouts/slideLayout1.xml")
        item = _make_item("s5.master", method="layout_check", selector="master_ref")
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is True


class TestAntiCheat:
    def test_font_policy_pass(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(
                    obj_type="shape",
                    text_runs=[
                        TextRun(text="Hello", font_family="Carlito"),
                        TextRun(text="World", font_family="Noto Sans"),
                    ],
                ),
            ]
        )
        item = _make_item("s1.font", method="anti_cheat", selector="font_policy")
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is True

    def test_font_policy_fail(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(
                    obj_type="shape",
                    text_runs=[
                        TextRun(text="Bad", font_family="Arial"),
                    ],
                ),
            ]
        )
        item = _make_item(
            "s1.font",
            method="anti_cheat",
            selector="font_policy",
            failure_mode=FailureMode(
                automatic_fail_if=["non_bundled_font_used"],
                propagation="zero_slide",
            ),
        )
        deck = _make_deck([slide])

        results, _, flags = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is False
        assert "Arial" in results[0].items[0].details
        assert len(flags) > 0

    def test_no_full_slide_raster_pass(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="picture", bbox=(0, 0, 3000000, 2000000)),  # small image
            ]
        )
        item = _make_item("s1.raster", method="anti_cheat", selector="no_full_slide_raster")
        deck = _make_deck([slide])

        results, _, _ = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is True

    def test_no_full_slide_raster_fail(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="picture", bbox=(0, 0, 12000000, 6800000)),  # ~97% of slide
            ]
        )
        item = _make_item(
            "s1.raster",
            method="anti_cheat",
            selector="no_full_slide_raster",
            failure_mode=FailureMode(
                automatic_fail_if=["full_slide_raster_detected"],
                propagation="zero_slide",
            ),
        )
        deck = _make_deck([slide])

        results, _, flags = evaluate_checklist(deck, [item])
        assert results[0].items[0].passed is False
        assert len(flags) > 0


class TestZeroSlidePropagation:
    def test_auto_fail_zeroes_other_items(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape", text_runs=[TextRun(text="X", font_family="Arial")]),
                SceneObject(obj_type="table", is_table=True, table_rows=2, table_cols=2),
            ]
        )

        font_item = _make_item(
            "s1.font",
            method="anti_cheat",
            selector="font_policy",
            failure_mode=FailureMode(
                automatic_fail_if=["non_bundled_font_used"],
                propagation="zero_slide",
            ),
        )
        table_item = _make_item(
            "s1.table",
            selector="table",
            expectation={"exact_count": 1, "required": True},
        )
        deck = _make_deck([slide])

        results, _, flags = evaluate_checklist(deck, [font_item, table_item])
        # Table should normally pass, but font auto-fail zeroes the whole slide
        table_result = next(r for r in results[0].items if r.id == "s1.table")
        assert table_result.passed is False
        assert "Zeroed by anti-cheat" in table_result.details


class TestScoring:
    def test_perfect_score(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="table", is_table=True, table_rows=3, table_cols=4),
                SceneObject(obj_type="shape", placeholder_type="title"),
            ]
        )
        items = [
            _make_item(
                "s1.table",
                selector="table",
                severity="critical",
                expectation={"exact_count": 1, "required": True},
            ),
            _make_item(
                "s1.ph",
                method="layout_check",
                selector="placeholder",
                severity="major",
                expectation={"placeholder_type": "title", "min_count": 1},
            ),
        ]
        deck = _make_deck([slide])

        results, deck_items, _ = evaluate_checklist(deck, items)
        fidelity, passed, total = compute_fidelity_score(results, deck_items)
        assert fidelity == 1.0
        assert passed == 2
        assert total == 2

    def test_partial_score(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape"),  # no table, no placeholder
            ]
        )
        items = [
            _make_item(
                "s1.table",
                selector="table",
                severity="critical",
                expectation={"exact_count": 1, "required": True},
            ),
            _make_item(
                "s1.shapes", selector="shape", severity="minor", expectation={"min_count": 1}
            ),
        ]
        deck = _make_deck([slide])

        results, deck_items, _ = evaluate_checklist(deck, items)
        fidelity, passed, total = compute_fidelity_score(results, deck_items)
        # shape passes (weight 1), table fails (weight 3)
        # fidelity = 1 / (1+3) = 0.25
        assert fidelity == 0.25
        assert passed == 1
        assert total == 2

    def test_informational_excluded(self) -> None:
        slide = _make_slide(objects=[])
        items = [
            _make_item(
                "s1.info", selector="shape", severity="informational", expectation={"min_count": 1}
            ),
        ]
        deck = _make_deck([slide])

        results, deck_items, _ = evaluate_checklist(deck, items)
        fidelity, passed, total = compute_fidelity_score(results, deck_items)
        # Informational items have weight 0, excluded from scoring
        assert fidelity == 0.0
        assert total == 0

    def test_weighted_scoring(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(obj_type="shape"),
            ]
        )
        items = [
            _make_item(
                "s1.crit", selector="shape", severity="critical", expectation={"min_count": 1}
            ),
            _make_item(
                "s1.fail", selector="table", severity="major", expectation={"required": True}
            ),
        ]
        deck = _make_deck([slide])

        results, deck_items, _ = evaluate_checklist(deck, items)
        fidelity, passed, total = compute_fidelity_score(results, deck_items)
        # critical passes (weight 3), major fails (weight 2)
        # fidelity = 3 / (3+2) = 0.6
        assert fidelity == 0.6


class TestDeckLevelItems:
    def test_slide_count(self) -> None:
        slides = [_make_slide(slide_number=i) for i in range(1, 21)]
        deck = _make_deck(slides)
        item = _make_item(
            "deck.count",
            scope="deck",
            slide=None,
            method="object_compare",
            selector="slide_count",
            expectation={"exact_count": 20},
        )

        _, deck_items, _ = evaluate_checklist(deck, [item])
        assert len(deck_items) == 1
        assert deck_items[0].passed is True

    def test_slide_count_wrong(self) -> None:
        slides = [_make_slide(slide_number=i) for i in range(1, 11)]
        deck = _make_deck(slides)
        item = _make_item(
            "deck.count",
            scope="deck",
            slide=None,
            method="object_compare",
            selector="slide_count",
            expectation={"exact_count": 20},
        )

        _, deck_items, _ = evaluate_checklist(deck, [item])
        assert deck_items[0].passed is False

    def test_deck_font_policy_pass(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(
                    obj_type="shape", text_runs=[TextRun(text="OK", font_family="Carlito")]
                ),
            ]
        )
        deck = _make_deck([slide])
        item = _make_item(
            "deck.font",
            scope="deck",
            slide=None,
            method="anti_cheat",
            selector="font_policy",
        )

        _, deck_items, _ = evaluate_checklist(deck, [item])
        assert deck_items[0].passed is True

    def test_deck_font_policy_fail(self) -> None:
        slide = _make_slide(
            objects=[
                SceneObject(
                    obj_type="shape", text_runs=[TextRun(text="Bad", font_family="Courier New")]
                ),
            ]
        )
        deck = _make_deck([slide])
        item = _make_item(
            "deck.font",
            scope="deck",
            slide=None,
            method="anti_cheat",
            selector="font_policy",
        )

        _, deck_items, _ = evaluate_checklist(deck, [item])
        assert deck_items[0].passed is False
        assert "Courier New" in deck_items[0].details


class TestTierScores:
    def test_tier_scoring(self) -> None:
        slides = []
        items = []
        for i in range(1, 21):
            slides.append(
                _make_slide(
                    slide_number=i,
                    objects=[
                        SceneObject(obj_type="shape"),
                    ],
                )
            )
            items.append(
                _make_item(
                    f"s{i}.shape",
                    slide=i,
                    tier=1 if i <= 5 else (2 if i <= 12 else 3),
                    selector="shape",
                    severity="major",
                    expectation={"min_count": 1},
                )
            )

        deck = _make_deck(slides)
        results, deck_items, _ = evaluate_checklist(deck, items, tier_slides=list(range(1, 21)))
        tier_scores = compute_tier_scores(results, deck_items, tier=3)

        assert "level_1" in tier_scores
        assert "level_2" in tier_scores
        assert "level_3" in tier_scores
        level_1 = tier_scores["level_1"]
        level_2 = tier_scores["level_2"]
        level_3 = tier_scores["level_3"]
        assert level_1 is None
        assert level_2 is None
        assert level_3 is not None and level_3["fidelity_score"] == 1.0


class TestDeckVisualScoring:
    def test_all_targeted_slides_must_meet_threshold(self) -> None:
        item = _make_item(
            "deck.visual",
            scope="deck",
            slide=None,
            method="visual_ssim",
            expectation={"min_ssim": 0.99},
        )
        visual = [
            VisualComparisonResult(1, 1.0, True),
            VisualComparisonResult(2, 0.98, False),
        ]

        _, deck_items, _ = evaluate_checklist(_make_deck(), [item], visual)

        assert deck_items[0].passed is False
        assert "1/2 slides" in deck_items[0].details

    def test_missing_visual_results_fail_deck_visual_item(self) -> None:
        item = _make_item(
            "deck.visual",
            scope="deck",
            slide=None,
            method="visual_ssim",
        )

        _, deck_items, _ = evaluate_checklist(_make_deck(), [item])

        assert deck_items[0].passed is False
        assert "No visual" in deck_items[0].details
