"""Grading pipeline — orchestrates all stages."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from acidslide import __version__
from acidslide.checklist import load_checklist
from acidslide.compare import compare_slides
from acidslide.evaluate import compute_fidelity_score, compute_tier_scores, evaluate_checklist
from acidslide.export import export_slides
from acidslide.inspect_ooxml import extract_deck_graph
from acidslide.models import GradeReport
from acidslide.quarantine import quarantine_check
from acidslide.schema_validate import validate_schema

DEFAULT_BENCHMARK_DIR = Path("/opt/acidslide/benchmark")

TIER_SLIDES: dict[int, list[int]] = {
    1: list(range(1, 6)),
    2: list(range(1, 13)),
    3: list(range(1, 21)),
}


def run_pipeline(
    submission: Path,
    tier: int,
    benchmark_dir: Path | None = None,
    output_format: str = "json",
) -> GradeReport:
    """Run the full grading pipeline on a submission."""
    if benchmark_dir is None:
        benchmark_dir = DEFAULT_BENCHMARK_DIR

    start_time = time.monotonic()

    # Stage 0: Quarantine
    qresult = quarantine_check(submission)
    if not qresult.passed:
        return _failed_report(
            submission=submission.name,
            reason=f"Quarantine failed: {qresult.reason}",
        )

    # Stage 0.5: Schema validation (non-blocking)
    sresult = validate_schema(submission)

    # Stage 1: Export via LibreOffice
    visual_results = []
    with tempfile.TemporaryDirectory() as export_dir:
        export_path = Path(export_dir)
        try:
            export_slides(submission, export_path)
        except RuntimeError:
            pass  # Export failure is non-fatal; structural grading continues

        # Stage 2: Visual comparison
        gold_exports_dir = benchmark_dir / "deck" / "exports"
        if gold_exports_dir.exists() and any(gold_exports_dir.glob("slide-*.png")):
            visual_results = compare_slides(export_path, gold_exports_dir)

    # Stage 3: OOXML structural extraction
    deck_graph = extract_deck_graph(submission)

    # Stage 4: Load checklist and evaluate
    checklist_dir = benchmark_dir / "checklist"
    tier_slides = TIER_SLIDES.get(tier, TIER_SLIDES[3])

    # Also load tier definition from benchmark tiers if available
    tier_file = benchmark_dir / "tiers" / f"level-{tier}" / "slides.json"
    if tier_file.exists():
        tier_data = json.loads(tier_file.read_text(encoding="utf-8"))
        tier_slides = tier_data.get("slides", tier_slides)

    checklist_items = []
    if checklist_dir.exists():
        checklist_items = load_checklist(checklist_dir, tier)

    slide_results, deck_item_results, anti_cheat_flags = evaluate_checklist(
        deck_graph=deck_graph,
        items=checklist_items,
        visual_results=visual_results if visual_results else None,
        tier_slides=tier_slides,
    )

    # Stage 5: Scoring
    fidelity, passed, total = compute_fidelity_score(slide_results, deck_item_results)
    tier_scores = compute_tier_scores(slide_results, deck_item_results, tier)

    deck_passed = (
        fidelity == 1.0
        and len(anti_cheat_flags) == 0
        and not False  # repair_triggered placeholder
    )

    elapsed = time.monotonic() - start_time

    return GradeReport(
        benchmark_version="acidslide-v1.0.0",
        grader_version=__version__,
        environment_hash="TODO",
        submission=submission.name,
        schema_valid=sresult.valid,
        repair_triggered=False,
        fidelity_score=round(fidelity, 4),
        passed_items=passed,
        total_items=total,
        deck_passed=deck_passed,
        eligible=True,
        tier_scores=tier_scores,
        slides=slide_results,
        deck_items=deck_item_results,
        anti_cheat_flags=anti_cheat_flags,
        verified_metrics={
            "submission_file_size_bytes": submission.stat().st_size,
            "grading_duration_seconds": round(elapsed, 2),
            "schema_valid": sresult.valid,
        },
    )


def _failed_report(submission: str, reason: str) -> GradeReport:
    return GradeReport(
        benchmark_version="acidslide-v1.0.0",
        grader_version=__version__,
        environment_hash="TODO",
        submission=submission,
        schema_valid=False,
        repair_triggered=False,
        fidelity_score=0.0,
        passed_items=0,
        total_items=0,
        deck_passed=False,
        eligible=False,
        tier_scores={},
    )
