"""Grading pipeline — orchestrates all stages without overstating verification."""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import rfc8785

from acidslide import __version__
from acidslide.checklist import load_checklist
from acidslide.compare import compare_slides
from acidslide.environment import environment_details
from acidslide.evaluate import compute_fidelity_score, compute_tier_scores, evaluate_checklist
from acidslide.export import export_slides
from acidslide.inspect_ooxml import extract_deck_graph
from acidslide.models import (
    AntiCheatFlag,
    ArtifactReportContext,
    ChecklistItemResult,
    DisqualificationState,
    GoldDuplicateCheck,
    GradeReport,
    GradingMode,
    RunKind,
    SchemaValidationResult,
    SlideResult,
    StableError,
    VisualComparisonResult,
)
from acidslide.package_hash import canonical_package_identity, sha256_file
from acidslide.provenance import ScoringCohortProvenance, load_signed_release_provenance
from acidslide.quarantine import quarantine_check
from acidslide.resources import resolve_benchmark_dir
from acidslide.schema_validate import validate_schema

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
    artifact_dir: Path | None = None,
    cohort_provenance: ScoringCohortProvenance | None = None,
    artifact_context: ArtifactReportContext | None = None,
) -> GradeReport:
    """Run local Stages 0–6; local reports are permanently non-official."""
    resolved_benchmark_dir, effective_cohort, context = _prepare_run(
        tier=tier,
        output_format=output_format,
        benchmark_dir=benchmark_dir,
        cohort_provenance=cohort_provenance,
        artifact_context=artifact_context,
    )
    if context.grading_mode is not GradingMode.LOCAL:
        raise ValueError("hosted runs must use run_resolved_pipeline")

    qresult = quarantine_check(submission)
    if not qresult.passed:
        return _failed_report(
            cohort=effective_cohort,
            context=context,
            reason=StableError("quarantine_failed", details=qresult.reason),
            submission_file_size_bytes=qresult.file_size_bytes,
        )

    _verify_artifact_context(submission, context, resolved=False)
    sresult = validate_schema(submission)
    return _run_scoring_stages(
        submission=submission,
        benchmark_dir=resolved_benchmark_dir,
        tier=tier,
        artifact_dir=artifact_dir,
        cohort=effective_cohort,
        context=context,
        schema_result=sresult,
    )


def run_resolved_pipeline(
    resolved_package: Path,
    tier: int,
    *,
    schema_result: SchemaValidationResult,
    artifact_context: ArtifactReportContext,
    benchmark_dir: Path | None = None,
    output_format: str = "json",
    artifact_dir: Path | None = None,
    cohort_provenance: ScoringCohortProvenance | None = None,
) -> GradeReport:
    """Run a hosted resolved-package result without repeating Stage 0.5.

    A performed but invalid Stage 0.5 result is itself a terminal diagnostic
    result. The artifact identities are still reverified before that report is
    emitted, but no renderer, parser, checklist, or scoring stage is entered.
    """
    resolved_benchmark_dir, effective_cohort, context = _prepare_run(
        tier=tier,
        output_format=output_format,
        benchmark_dir=benchmark_dir,
        cohort_provenance=cohort_provenance,
        artifact_context=artifact_context,
    )
    if context.grading_mode is not GradingMode.HOSTED:
        raise ValueError("resolved-package grading requires hosted grading_mode")
    _verify_artifact_context(resolved_package, context, resolved=True)
    if not schema_result.performed:
        raise ValueError("hosted grading requires a performed Stage 0.5 result")
    if not schema_result.valid:
        schema_errors = _schema_errors(schema_result.violations)
        details = (
            "Stage 0.5 rejected the resolved package"
            if schema_errors
            else "Stage 0.5 rejected the resolved package without a stable violation record"
        )
        return _failed_report(
            cohort=effective_cohort,
            context=context,
            reason=StableError("schema_validation_failed", details=details),
            submission_file_size_bytes=resolved_package.stat().st_size,
            schema_result=schema_result,
            schema_errors=schema_errors,
            ineligibility_reasons=["schema_validation_failed"],
        )
    return _run_scoring_stages(
        submission=resolved_package,
        benchmark_dir=resolved_benchmark_dir,
        tier=tier,
        artifact_dir=artifact_dir,
        cohort=effective_cohort,
        context=context,
        schema_result=schema_result,
    )


def _prepare_run(
    *,
    tier: int,
    output_format: str,
    benchmark_dir: Path | None,
    cohort_provenance: ScoringCohortProvenance | None,
    artifact_context: ArtifactReportContext | None,
) -> tuple[Path, ScoringCohortProvenance, ArtifactReportContext]:
    if tier not in TIER_SLIDES:
        raise ValueError(f"Unsupported tier {tier}; expected 1, 2, or 3")
    if output_format not in {"json", "html", "text"}:
        raise ValueError(f"Unsupported output format: {output_format}")
    if artifact_context is None:
        raise ValueError("artifact_context is required; report provenance cannot be invented")
    artifact_context.validate()
    if artifact_context.targeted_tier != tier:
        raise ValueError("artifact_context targeted_tier does not match requested tier")

    resolved_benchmark_dir = resolve_benchmark_dir(benchmark_dir)
    effective_cohort = cohort_provenance or load_signed_release_provenance(resolved_benchmark_dir)
    effective_cohort.validate()
    attestation_bytes = rfc8785.dumps(artifact_context.environment_attestation)
    actual_attestation_hash = f"sha256:{hashlib.sha256(attestation_bytes).hexdigest()}"
    if actual_attestation_hash != effective_cohort.environment_attestation_sha256:
        raise ValueError("environment attestation payload does not match the scoring cohort")
    return resolved_benchmark_dir, effective_cohort, artifact_context


def _verify_artifact_context(
    package: Path,
    context: ArtifactReportContext,
    *,
    resolved: bool,
) -> None:
    actual_file_hash = f"sha256:{sha256_file(package)}"
    expected_file_hash = (
        context.mce_resolved_package_sha256 if resolved else context.submission_sha256
    )
    if expected_file_hash is None or actual_file_hash != expected_file_hash:
        raise ValueError("artifact bytes do not match the report context")

    identity = canonical_package_identity(package)
    actual_profiles = {
        "canonical_package_hash_profile_sha256": f"sha256:{identity.package_hash_profile_sha256}",
        "mce_profile_sha256": f"sha256:{identity.mce_profile_sha256}",
        "schema_root_map_sha256": f"sha256:{identity.schema_root_map_sha256}",
    }
    expected_profiles = {
        "canonical_package_hash_profile_sha256": (context.canonical_package_hash_profile_sha256),
        "mce_profile_sha256": context.mce_profile_sha256,
        "schema_root_map_sha256": context.schema_root_map_sha256,
    }
    if actual_profiles != expected_profiles:
        raise ValueError("artifact profile hashes do not match the report context")
    actual_canonical = f"sha256:{identity.canonical_package_sha256}"
    if actual_canonical != context.canonical_package_hash_v1:
        raise ValueError("canonical package hash does not match the report context")

    byte_match = context.submission_sha256 == context.gold_submission_sha256
    canonical_match = actual_canonical == context.gold_canonical_package_hash_v1
    expected_duplicate = (
        GoldDuplicateCheck.BYTE_MATCH
        if byte_match
        else GoldDuplicateCheck.CANONICAL_MATCH
        if canonical_match
        else GoldDuplicateCheck.CLEAR
    )
    if context.gold_duplicate_check is not expected_duplicate:
        raise ValueError("gold duplicate outcome does not match the report context")


def _run_scoring_stages(
    *,
    submission: Path,
    benchmark_dir: Path,
    tier: int,
    artifact_dir: Path | None,
    cohort: ScoringCohortProvenance,
    context: ArtifactReportContext,
    schema_result: SchemaValidationResult,
) -> GradeReport:
    start_time = time.monotonic()
    effective_environment = environment_details()
    verification_errors: list[StableError] = []
    schema_errors = _schema_errors(schema_result.violations)
    if not schema_result.performed:
        verification_errors.append(
            StableError("schema_validation_not_performed", details="Stage 0.5 was not performed")
        )
    elif not schema_result.valid and not schema_errors:
        verification_errors.append(
            StableError(
                "schema_validation_failed",
                details="Stage 0.5 failed without a stable violation record",
            )
        )

    tier_slides, tier_errors = _load_tier_slides(benchmark_dir, tier)
    verification_errors.extend(tier_errors)
    visual_results, visual_verification_performed, visual_errors = _run_visual_stages(
        submission=submission,
        benchmark_dir=benchmark_dir,
        tier_slides=tier_slides,
        artifact_dir=artifact_dir,
    )
    visual_results = [result for result in visual_results if result.slide_number in tier_slides]
    verification_errors.extend(visual_errors)

    try:
        deck_graph = extract_deck_graph(submission)
    except Exception as exc:
        return _failed_report(
            cohort=cohort,
            context=context,
            reason=StableError("ooxml_extraction_failed", details=str(exc)),
            submission_file_size_bytes=submission.stat().st_size,
            schema_result=schema_result,
            schema_errors=schema_errors,
        )

    checklist_dir = benchmark_dir / "checklist"
    try:
        checklist_items = load_checklist(checklist_dir, tier)
    except (OSError, ValueError, TypeError) as exc:
        checklist_items = []
        verification_errors.append(StableError("checklist_loading_failed", details=str(exc)))
    if not checklist_items:
        verification_errors.append(StableError("checklist_empty", location=str(checklist_dir)))

    slide_results, deck_item_results, anti_cheat_flags = evaluate_checklist(
        deck_graph=deck_graph,
        items=checklist_items,
        visual_results=visual_results,
        tier_slides=tier_slides,
    )
    verification_errors = _deduplicate_errors(verification_errors)
    verification_complete = (
        schema_result.performed
        and schema_result.valid
        and visual_verification_performed
        and bool(checklist_items)
        and not verification_errors
    )
    scoring_completed = verification_complete
    if scoring_completed:
        raw_fidelity, passed, total = compute_fidelity_score(slide_results, deck_item_results)
        fidelity: float | None = round(raw_fidelity, 4)
        tier_scores = compute_tier_scores(slide_results, deck_item_results, tier)
    else:
        fidelity = None
        passed = 0
        total = 0
        tier_scores = {"level_1": None, "level_2": None, "level_3": None}

    repair_triggered = False
    disqualification_state, ineligibility_reasons = _disqualification(
        context=context,
        verification_complete=verification_complete,
        repair_triggered=repair_triggered,
    )
    eligible = (
        context.grading_mode is GradingMode.HOSTED
        and context.run_kind is RunKind.SUBMISSION
        and scoring_completed
        and verification_complete
        and context.gold_duplicate_check is GoldDuplicateCheck.CLEAR
        and disqualification_state is DisqualificationState.NONE
        and not repair_triggered
    )
    score_affecting_flags = any(
        flag.disposition in {"zero_slide", "zero_affected_slides", "reject"}
        for flag in anti_cheat_flags
    )
    deck_passed = bool(
        scoring_completed and fidelity == 1.0 and not score_affecting_flags and not repair_triggered
    )
    if context.grading_mode is GradingMode.HOSTED and context.run_kind is RunKind.SUBMISSION:
        deck_passed = deck_passed and eligible
    campaign_contribution = fidelity if eligible and fidelity is not None else 0.0
    elapsed = round(time.monotonic() - start_time, 2)

    return _report(
        cohort=cohort,
        context=context,
        schema_result=schema_result,
        visual_verification_performed=visual_verification_performed,
        verification_complete=verification_complete,
        scoring_completed=scoring_completed,
        disqualification_state=disqualification_state,
        ineligibility_reasons=ineligibility_reasons,
        repair_triggered=repair_triggered,
        grading_duration_seconds=elapsed,
        fidelity_score=fidelity,
        campaign_contribution=campaign_contribution,
        passed_items=passed,
        total_items=total,
        deck_passed=deck_passed,
        eligible=eligible,
        tier_scores=tier_scores,
        submission_file_size_bytes=submission.stat().st_size,
        renderer_version=str(effective_environment["libreoffice"]),
        slides=slide_results,
        deck_items=deck_item_results,
        anti_cheat_flags=anti_cheat_flags,
        schema_errors=schema_errors,
        verification_errors=verification_errors,
    )


def _disqualification(
    *,
    context: ArtifactReportContext,
    verification_complete: bool,
    repair_triggered: bool,
) -> tuple[DisqualificationState, list[str]]:
    if context.grading_mode is GradingMode.LOCAL:
        return DisqualificationState.NON_OFFICIAL_LOCAL, ["local_mode"]
    if context.run_kind is not RunKind.SUBMISSION:
        return DisqualificationState.NONE, []
    reasons: list[str] = []
    if context.gold_duplicate_check in {
        GoldDuplicateCheck.BYTE_MATCH,
        GoldDuplicateCheck.CANONICAL_MATCH,
    }:
        reasons.append("gold_artifact_copy")
    elif context.gold_duplicate_check is GoldDuplicateCheck.INCOMPLETE:
        reasons.append("duplicate_check_incomplete")
    if repair_triggered:
        reasons.append("repair_triggered")
    if not verification_complete:
        reasons.append("verification_incomplete")
    if reasons:
        return DisqualificationState.COMPLETED_INELIGIBLE, sorted(set(reasons))
    return DisqualificationState.NONE, []


def _run_visual_stages(
    *,
    submission: Path,
    benchmark_dir: Path,
    tier_slides: list[int],
    artifact_dir: Path | None,
) -> tuple[list[VisualComparisonResult], bool, list[StableError]]:
    errors: list[StableError] = []
    results: list[VisualComparisonResult] = []
    expected_slides = set(tier_slides)
    gold_exports_dir = benchmark_dir / "deck" / "exports"
    gold_slides = sorted(gold_exports_dir.glob("slide-*.png"))
    gold_slide_numbers = _slide_numbers(gold_slides)

    if not gold_slides:
        errors.append(StableError("gold_exports_missing", location=str(gold_exports_dir)))
    elif missing_gold := expected_slides - gold_slide_numbers:
        errors.append(StableError("gold_exports_incomplete", details=str(sorted(missing_gold))))

    with tempfile.TemporaryDirectory() as export_dir:
        export_path = Path(export_dir)
        try:
            exports = export_slides(
                submission,
                export_path,
                expected_page_count=len(tier_slides),
            )
        except RuntimeError as exc:
            exports = []
            errors.append(StableError("slide_export_failed", details=str(exc)))

        exported_slide_numbers = {export.slide_number for export in exports}
        if missing_exports := expected_slides - exported_slide_numbers:
            errors.append(
                StableError("submission_exports_missing", details=str(sorted(missing_exports)))
            )
        if unexpected_exports := exported_slide_numbers - expected_slides:
            errors.append(
                StableError(
                    "submission_exports_unexpected",
                    details=str(sorted(unexpected_exports)),
                )
            )

        if gold_slides:
            try:
                results = compare_slides(export_path, gold_exports_dir, artifact_dir)
            except (OSError, ValueError) as exc:
                errors.append(StableError("visual_comparison_failed", details=str(exc)))

    result_slide_numbers = {result.slide_number for result in results}
    missing_comparisons = expected_slides - result_slide_numbers
    if gold_slides and missing_comparisons:
        errors.append(
            StableError("visual_comparisons_missing", details=str(sorted(missing_comparisons)))
        )

    performed = not errors and expected_slides.issubset(result_slide_numbers)
    return results, performed, _deduplicate_errors(errors)


def _load_tier_slides(benchmark_dir: Path, tier: int) -> tuple[list[int], list[StableError]]:
    default = TIER_SLIDES[tier]
    tier_file = benchmark_dir / "tiers" / f"level-{tier}" / "slides.json"
    if not tier_file.is_file():
        return default, [StableError("tier_definition_missing", location=str(tier_file))]

    try:
        raw: Any = json.loads(tier_file.read_text(encoding="utf-8"))
        slides = raw["slides"]
        if not isinstance(slides, list) or not slides:
            raise ValueError("slides must be a non-empty list")
        if any(not isinstance(slide, int) or isinstance(slide, bool) for slide in slides):
            raise ValueError("slides must contain only integers")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return default, [
            StableError("tier_definition_invalid", location=str(tier_file), details=str(exc))
        ]
    return slides, []


def _slide_numbers(paths: list[Path]) -> set[int]:
    numbers: set[int] = set()
    for path in paths:
        try:
            numbers.add(int(path.stem.rsplit("-", maxsplit=1)[1]))
        except (IndexError, ValueError):
            continue
    return numbers


def _deduplicate_errors(errors: list[StableError]) -> list[StableError]:
    unique: dict[tuple[str, str | None, str | None, str], StableError] = {}
    for error in errors:
        unique[(error.code, error.part, error.location, error.details)] = error
    return list(unique.values())


def _schema_errors(violations: list[str]) -> list[StableError]:
    errors: list[StableError] = []
    for violation in violations:
        prefix, separator, detail = violation.partition(":")
        part = prefix if separator and ("/" in prefix or prefix.endswith(".xml")) else None
        errors.append(
            StableError(
                "schema_violation",
                part=part,
                details=detail.strip() if part is not None else violation,
            )
        )
    return _deduplicate_errors(errors)


def _report(
    *,
    cohort: ScoringCohortProvenance,
    context: ArtifactReportContext,
    schema_result: SchemaValidationResult,
    visual_verification_performed: bool,
    verification_complete: bool,
    scoring_completed: bool,
    disqualification_state: DisqualificationState,
    ineligibility_reasons: list[str],
    repair_triggered: bool,
    grading_duration_seconds: float,
    fidelity_score: float | None,
    campaign_contribution: float,
    passed_items: int,
    total_items: int,
    deck_passed: bool,
    eligible: bool,
    tier_scores: dict[str, dict[str, int | float] | None],
    submission_file_size_bytes: int,
    renderer_version: str,
    slides: list[SlideResult],
    deck_items: list[ChecklistItemResult],
    anti_cheat_flags: list[AntiCheatFlag],
    schema_errors: list[StableError],
    verification_errors: list[StableError],
) -> GradeReport:
    return GradeReport(
        benchmark_version="acidslide-v1.0.0",
        grader_version=__version__,
        scoring_cohort_id=cohort.scoring_cohort_id,
        scoring_manifest_sha256=cohort.scoring_manifest_sha256,
        grader_source_tree_sha256=cohort.grader_source_tree_sha256,
        environment_attestation_sha256=cohort.environment_attestation_sha256,
        grader_package_sha256=context.grader_package_sha256,
        oci_image_digest=context.oci_image_digest,
        prompt_bundle_sha256=context.prompt_bundle_sha256,
        scored_assertion_inventory_sha256=context.scored_assertion_inventory_sha256,
        checklist_bundle_sha256=context.checklist_bundle_sha256,
        schema_bundle_sha256=context.schema_bundle_sha256,
        schema_root_map_sha256=context.schema_root_map_sha256,
        mce_profile_sha256=context.mce_profile_sha256,
        asset_manifest_sha256=context.asset_manifest_sha256,
        font_manifest_sha256=context.font_manifest_sha256,
        grading_mode=context.grading_mode,
        run_kind=context.run_kind,
        canonical_package_hash_profile_sha256=(context.canonical_package_hash_profile_sha256),
        canonical_package_hash_v1=context.canonical_package_hash_v1,
        gold_duplicate_check=context.gold_duplicate_check,
        generation_seed=context.generation_seed,
        submission_id=context.submission_id,
        campaign_id=context.campaign_id,
        campaign_slot=context.campaign_slot,
        robustness_group_id=context.robustness_group_id,
        submitter_id=context.submitter_id,
        model_key=context.model_key,
        model_revision_key=context.model_revision_key,
        targeted_tier=context.targeted_tier,
        prompt_variant=context.prompt_variant,
        assistance_class=context.assistance_class,
        generation_profile_sha256=context.generation_profile_sha256,
        submission_sha256=context.submission_sha256,
        mce_resolved_package_sha256=context.mce_resolved_package_sha256,
        gold_submission_sha256=context.gold_submission_sha256,
        gold_mce_resolved_package_sha256=context.gold_mce_resolved_package_sha256,
        gold_canonical_package_hash_v1=context.gold_canonical_package_hash_v1,
        schema_valid=schema_result.valid,
        schema_validation_performed=schema_result.performed,
        visual_verification_performed=visual_verification_performed,
        verification_complete=verification_complete,
        scoring_completed=scoring_completed,
        disqualification_state=disqualification_state,
        ineligibility_reasons=ineligibility_reasons,
        repair_triggered=repair_triggered,
        grading_duration_seconds=grading_duration_seconds,
        fidelity_score=fidelity_score,
        campaign_contribution=campaign_contribution,
        passed_items=passed_items,
        total_items=total_items,
        deck_passed=deck_passed,
        eligible=eligible,
        tier_scores=tier_scores,
        slides=slides,
        deck_items=deck_items,
        anti_cheat_flags=anti_cheat_flags,
        schema_violations=schema_errors,
        verification_errors=verification_errors,
        environment_attestation=context.environment_attestation,
        verified_metrics={
            "submission_file_size_bytes": submission_file_size_bytes,
            "grading_duration_seconds": grading_duration_seconds,
            "schema_valid": schema_result.valid,
            "schema_validation_performed": schema_result.performed,
            "visual_verification_performed": visual_verification_performed,
            "verification_complete": verification_complete,
            "renderer_version": renderer_version,
        },
        attested_metrics=context.attested_metrics,
        attestation=context.attestation,
    )


def _failed_report(
    cohort: ScoringCohortProvenance,
    context: ArtifactReportContext,
    reason: StableError,
    submission_file_size_bytes: int,
    *,
    schema_result: SchemaValidationResult | None = None,
    schema_errors: list[StableError] | None = None,
    ineligibility_reasons: list[str] | None = None,
) -> GradeReport:
    effective_schema_result = schema_result or SchemaValidationResult(valid=False, performed=False)
    state, reasons = _disqualification(
        context=context,
        verification_complete=False,
        repair_triggered=False,
    )
    if ineligibility_reasons is not None:
        reasons = sorted(set(reasons + ineligibility_reasons))
        if context.grading_mode is GradingMode.HOSTED and context.run_kind is RunKind.SUBMISSION:
            state = DisqualificationState.COMPLETED_INELIGIBLE
    return _report(
        cohort=cohort,
        context=context,
        schema_result=effective_schema_result,
        visual_verification_performed=False,
        verification_complete=False,
        scoring_completed=False,
        disqualification_state=state,
        ineligibility_reasons=reasons,
        repair_triggered=False,
        grading_duration_seconds=0.0,
        fidelity_score=None,
        campaign_contribution=0.0,
        passed_items=0,
        total_items=0,
        deck_passed=False,
        eligible=False,
        tier_scores={"level_1": None, "level_2": None, "level_3": None},
        submission_file_size_bytes=submission_file_size_bytes,
        renderer_version="unavailable",
        slides=[],
        deck_items=[],
        anti_cheat_flags=[],
        schema_errors=schema_errors or [],
        verification_errors=[reason],
    )
