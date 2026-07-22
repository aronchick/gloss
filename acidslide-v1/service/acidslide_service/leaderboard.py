"""Campaign leaderboard and append-only public grading-run ledger."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from acidslide_service.config import Settings
from acidslide_service.models import Campaign, LeaderboardSnapshot, Submission, SubmissionStatus
from acidslide_service.service import VERIFICATION_LABEL, VERIFICATION_SCOPE, scoring_cohort_id


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _completed_runs(campaign: Campaign) -> list[Submission]:
    return sorted(
        (
            submission
            for submission in campaign.submissions
            if submission.status == SubmissionStatus.COMPLETED.value
            and submission.run is not None
            and submission.campaign_slot is not None
        ),
        key=lambda submission: submission.campaign_slot or 0,
    )


def public_run_row(submission: Submission) -> dict[str, Any]:
    """Return the stable public projection; the full report and artifacts stay private."""

    assert submission.run is not None
    campaign = submission.campaign
    model = submission.model
    revision = submission.model_revision
    report = submission.run.report_json
    environment_attestation = report.get("environment_attestation")
    return {
        "verification_scope": submission.run.verification_scope,
        "verification_label": submission.run.verification_label,
        "grading_mode": report.get("grading_mode"),
        "run_kind": report.get("run_kind"),
        "submission_id": submission.id,
        "run_id": submission.run.id,
        "submitter_id": submission.organization_id,
        "submitter_display_name": submission.organization.name,
        "model_key": model.id,
        "model_revision_key": revision.id,
        "model_display_name": model.display_name,
        "model_revision_display": revision.display_name,
        "revision_note": revision.revision_note,
        "owner_attribution": model.owner_attribution,
        "campaign_id": campaign.id,
        "robustness_group_id": campaign.robustness_group_id,
        "campaign_slot": submission.campaign_slot,
        "tier": campaign.tier,
        "benchmark_version": campaign.benchmark_version,
        "prompt_variant": campaign.prompt_variant,
        "assistance_class": campaign.assistance_class,
        "generation_profile_sha256": campaign.generation_profile_sha256,
        "generation_seed": submission.generation_seed,
        "scoring_cohort_id": submission.run.scoring_cohort_id,
        "scoring_manifest_sha256": submission.run.scoring_manifest_sha256,
        "grader_source_tree_sha256": submission.run.grader_source_tree_sha256,
        "environment_attestation_sha256": submission.run.environment_attestation_sha256,
        "grader_package_sha256": report.get("grader_package_sha256"),
        "oci_image_digest": report.get("oci_image_digest"),
        "platform": (
            environment_attestation.get("platform")
            if isinstance(environment_attestation, dict)
            else None
        ),
        "libreoffice_version": submission.run.libreoffice_version,
        "prompt_bundle_sha256": report.get("prompt_bundle_sha256"),
        "scored_assertion_inventory_sha256": report.get("scored_assertion_inventory_sha256"),
        "checklist_bundle_sha256": report.get("checklist_bundle_sha256"),
        "schema_bundle_sha256": report.get("schema_bundle_sha256"),
        "schema_root_map_sha256": report.get("schema_root_map_sha256"),
        "mce_profile_sha256": report.get("mce_profile_sha256"),
        "asset_manifest_sha256": report.get("asset_manifest_sha256"),
        "font_manifest_sha256": report.get("font_manifest_sha256"),
        "fidelity_score": submission.fidelity_score,
        "campaign_score": submission.campaign_score,
        "campaign_contribution": report.get("campaign_contribution"),
        "eligible": bool(submission.eligible),
        "schema_validation_performed": report.get("schema_validation_performed"),
        "schema_valid": report.get("schema_valid"),
        "visual_verification_performed": report.get("visual_verification_performed"),
        "verification_complete": report.get("verification_complete"),
        "scoring_completed": report.get("scoring_completed"),
        "disqualification_state": report.get("disqualification_state"),
        "ineligibility_reasons": report.get("ineligibility_reasons", []),
        "submission_sha256": report.get("submission_sha256"),
        "mce_resolved_package_sha256": report.get("mce_resolved_package_sha256"),
        "canonical_package_hash_profile_sha256": (submission.canonical_package_hash_profile_sha256),
        "canonical_package_hash_v1": submission.canonical_package_hash_v1,
        "gold_submission_sha256": report.get("gold_submission_sha256"),
        "gold_mce_resolved_package_sha256": report.get("gold_mce_resolved_package_sha256"),
        "gold_canonical_package_hash_v1": report.get("gold_canonical_package_hash_v1"),
        "gold_duplicate_check": report.get("gold_duplicate_check"),
        "score_semantic_report_sha256": report.get("score_semantic_report_sha256"),
        "report_sha256": f"sha256:{submission.run.report_sha256}",
        "normalized_report_sha256": submission.run.report_sha256,
        "environment_attestation": environment_attestation,
        "generation_attestation": submission.attestation,
        "attested_efficiency": submission.efficiency_metrics,
        "provenance": submission.run.provenance_json,
        "submitted_at": _iso(submission.created_at),
        "grading_started_at": _iso(submission.run.grading_started_at),
        "grading_completed_at": _iso(submission.run.grading_completed_at),
    }


def _robustness_scores(campaigns: list[Campaign], settings: Settings) -> dict[str, float | None]:
    by_group: dict[str, list[Campaign]] = {}
    for campaign in campaigns:
        if campaign.robustness_group_id:
            by_group.setdefault(campaign.robustness_group_id, []).append(campaign)
    result: dict[str, float | None] = {}
    expected = set(settings.required_prompt_variants)
    for group_id, group_campaigns in by_group.items():
        means: dict[str, float] = {}
        for campaign in group_campaigns:
            runs = _completed_runs(campaign)
            if len(runs) == 3:
                means[campaign.prompt_variant] = statistics.fmean(
                    float(run.campaign_score or 0.0) for run in runs
                )
        result[group_id] = min(means.values()) if set(means) == expected else None
    return result


def _campaign_entry(
    campaign: Campaign,
    settings: Settings,
    robustness_score: float | None,
    *,
    include_runs: bool,
    now: datetime,
) -> dict[str, Any]:
    runs = _completed_runs(campaign)
    scores = [float(run.campaign_score or 0.0) for run in runs]
    completed = len(runs) == 3
    mean = statistics.fmean(scores) if scores else None
    current_cohort = (
        campaign.scoring_cohort_id
        == scoring_cohort_id(
            settings.active_scoring_manifest_sha256,
            settings.active_grader_source_tree_sha256,
            settings.active_environment_attestation_sha256,
        )
        and campaign.scoring_manifest_sha256 == settings.active_scoring_manifest_sha256
        and campaign.grader_source_tree_sha256 == settings.active_grader_source_tree_sha256
        and campaign.environment_attestation_sha256
        == settings.active_environment_attestation_sha256
    )
    closes_at = campaign.closes_at
    if closes_at.tzinfo is None:
        closes_at = closes_at.replace(tzinfo=UTC)
    stale = closes_at < now - timedelta(days=30)
    human_assisted = campaign.assistance_class == "human-assisted"
    tier_metric = {
        "official_score": round(mean, 6) if completed and mean is not None else None,
        "provisional_score": round(mean, 6) if not completed and mean is not None else None,
        "record_score": max(
            (float(run.fidelity_score or 0.0) for run in runs if run.eligible), default=None
        ),
        "mean_score": round(mean, 6) if mean is not None else None,
        "best_score": max(scores, default=None),
        "worst_score": min(scores, default=None),
        "standard_deviation": (
            round(statistics.pstdev(scores), 6) if len(scores) > 1 else 0.0 if scores else None
        ),
        "submission_count": len(runs),
        "robustness_score": robustness_score,
    }
    tier_scores: dict[str, Any] = {f"level_{tier}": None for tier in (1, 2, 3)}
    tier_scores[f"level_{campaign.tier}"] = tier_metric
    entry: dict[str, Any] = {
        "verification_scope": VERIFICATION_SCOPE,
        "verification_label": VERIFICATION_LABEL,
        "submitter_id": campaign.organization_id,
        "submitter_display_name": campaign.organization.name,
        "model_key": campaign.model.id,
        "model_revision_key": campaign.model_revision.id,
        "campaign_id": campaign.id,
        "robustness_group_id": campaign.robustness_group_id,
        "model_display_name": campaign.model.display_name,
        "model_revision_display": campaign.model_revision.display_name,
        "revision_note": campaign.model_revision.revision_note,
        "owner_attribution": campaign.model.owner_attribution,
        "tier": campaign.tier,
        "benchmark_version": campaign.benchmark_version,
        "prompt_variant": campaign.prompt_variant,
        "assistance_class": campaign.assistance_class,
        "generation_profile_sha256": campaign.generation_profile_sha256,
        "tier_scores": tier_scores,
        "aggregate_score": round(mean, 6) if completed and mean is not None else None,
        "provisional": not completed,
        "ranked": completed and current_cohort and not stale,
        "stale": stale,
        "human_assisted": human_assisted,
        "opens_at": _iso(campaign.opens_at),
        "closes_at": _iso(campaign.closes_at),
        "scoring_cohort_id": campaign.scoring_cohort_id,
        "scoring_manifest_sha256": campaign.scoring_manifest_sha256,
        "grader_source_tree_sha256": campaign.grader_source_tree_sha256,
        "environment_attestation_sha256": campaign.environment_attestation_sha256,
    }
    if include_runs:
        entry["runs"] = [public_run_row(run) for run in runs]
    return entry


def _campaign_query(benchmark_version: str) -> Any:
    return (
        select(Campaign)
        .options(
            joinedload(Campaign.organization),
            joinedload(Campaign.model),
            joinedload(Campaign.model_revision),
            joinedload(Campaign.submissions).joinedload(Submission.run),
            joinedload(Campaign.submissions).joinedload(Submission.organization),
            joinedload(Campaign.submissions).joinedload(Submission.model),
            joinedload(Campaign.submissions).joinedload(Submission.model_revision),
        )
        .where(Campaign.benchmark_version == benchmark_version)
        .order_by(Campaign.created_at.desc())
    )


def build_leaderboard(
    session: Session,
    settings: Settings,
    *,
    benchmark_version: str,
    view: str = "summary",
) -> dict[str, Any]:
    campaigns = list(session.scalars(_campaign_query(benchmark_version)).unique())
    robustness = _robustness_scores(campaigns, settings)
    now = datetime.now(UTC)
    entries = [
        _campaign_entry(
            campaign,
            settings,
            robustness.get(campaign.robustness_group_id or ""),
            include_runs=view == "detail",
            now=now,
        )
        for campaign in campaigns
        if _completed_runs(campaign)
    ]
    entries.sort(
        key=lambda entry: (
            bool(entry["ranked"]),
            entry["aggregate_score"] if entry["aggregate_score"] is not None else -1.0,
            entry["closes_at"],
        ),
        reverse=True,
    )
    standard = [entry for entry in entries if not entry["human_assisted"]]
    assisted = [entry for entry in entries if entry["human_assisted"]]
    completion_times = [
        run.grading_completed_at
        for campaign in campaigns
        for run in _completed_runs(campaign)
        if run.grading_completed_at is not None
    ]
    newest = max(completion_times, default=None)
    return {
        "benchmark_version": benchmark_version,
        "verification_scope": VERIFICATION_SCOPE,
        "verification_label": VERIFICATION_LABEL,
        "scoring_cohort_id": scoring_cohort_id(
            settings.active_scoring_manifest_sha256,
            settings.active_grader_source_tree_sha256,
            settings.active_environment_attestation_sha256,
        ),
        "scoring_manifest_sha256": settings.active_scoring_manifest_sha256,
        "grader_source_tree_sha256": settings.active_grader_source_tree_sha256,
        "environment_attestation_sha256": settings.active_environment_attestation_sha256,
        "updated_at": _iso(newest) or _iso(now),
        "view": view,
        "entries": standard,
        "human_assisted_entries": assisted,
        "comparability_notice": (
            "Official means use exactly three campaign slots. Scores are comparable only when "
            "scoring-manifest, grader-source, and environment-attestation hashes all match. "
            "Model and generation attribution are submitter-attested."
        ),
    }


def build_run_ledger(
    session: Session,
    *,
    benchmark_version: str,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    campaigns = list(session.scalars(_campaign_query(benchmark_version)).unique())
    runs = [public_run_row(run) for campaign in campaigns for run in _completed_runs(campaign)]
    runs.sort(key=lambda row: (row["grading_completed_at"], row["run_id"]), reverse=True)
    return {
        "benchmark_version": benchmark_version,
        "verification_scope": VERIFICATION_SCOPE,
        "verification_label": VERIFICATION_LABEL,
        "total": len(runs),
        "runs": runs[offset : offset + limit],
    }


def write_snapshot(session: Session, settings: Settings, benchmark_version: str) -> None:
    payload = build_leaderboard(
        session,
        settings,
        benchmark_version=benchmark_version,
        view="summary",
    )
    session.add(LeaderboardSnapshot(benchmark_version=benchmark_version, payload=payload))
    session.commit()
