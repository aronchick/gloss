"""Transactional submission lifecycle operations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import rfc8785
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from gloss_service.config import Settings
from gloss_service.models import (
    Artifact,
    Campaign,
    Organization,
    QuarantineVerdictUse,
    RunRecord,
    SecurityEvent,
    Submission,
    SubmissionStatus,
)
from gloss_service.runner import ArtifactFile


@dataclass(frozen=True)
class LimitViolation:
    message: str
    retry_after: int


VERIFICATION_LABEL = "grading-verified artifact score; generation-attested"
VERIFICATION_SCOPE = "artifact_conformance"


def scoring_cohort_id(
    scoring_manifest_sha256: str,
    grader_source_tree_sha256: str,
    environment_attestation_sha256: str,
) -> str:
    """Hash the exact RFC 8785 descriptor (string-only JCS is canonical sorted JSON)."""

    descriptor = {
        "environment_attestation_sha256": environment_attestation_sha256,
        "grader_source_tree_sha256": grader_source_tree_sha256,
        "schema_version": "1.0",
        "scoring_manifest_sha256": scoring_manifest_sha256,
    }
    encoded = json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _count(session: Session, query: Any) -> int:
    return int(session.scalar(query) or 0)


def check_submission_limits(
    session: Session,
    organization: Organization,
    *,
    campaign: Campaign,
    settings: Settings,
    now: datetime | None = None,
) -> LimitViolation | None:
    now = now or _utcnow()
    if session.bind and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:organization_id))"),
            {"organization_id": organization.id},
        )

    hour_start = now - timedelta(hours=1)
    hourly = _count(
        session,
        select(func.count(Submission.id)).where(
            Submission.organization_id == organization.id,
            Submission.created_at >= hour_start,
        ),
    )
    hourly += _count(
        session,
        select(func.count(SecurityEvent.id)).where(
            SecurityEvent.organization_id == organization.id,
            SecurityEvent.created_at >= hour_start,
            SecurityEvent.event_type.in_({"quarantine_rejected", "invalid_tier"}),
        ),
    )
    if hourly >= settings.submissions_per_hour:
        oldest = session.scalar(
            select(Submission.created_at)
            .where(
                Submission.organization_id == organization.id,
                Submission.created_at >= hour_start,
            )
            .order_by(Submission.created_at.asc())
            .limit(1)
        )
        retry = (
            max(1, int(((_as_utc(oldest) + timedelta(hours=1)) - now).total_seconds()))
            if oldest
            else 3600
        )
        return LimitViolation("Hourly submission limit reached", retry)

    if _as_utc(campaign.opens_at) > now:
        return LimitViolation("Campaign window has not opened", 1)
    if _as_utc(campaign.closes_at) <= now:
        return LimitViolation("Campaign window has closed", 0)

    active_slots = _count(
        session,
        select(func.count(Submission.id)).where(
            Submission.campaign_id == campaign.id,
            Submission.status.in_(
                {
                    SubmissionStatus.QUEUED.value,
                    SubmissionStatus.GRADING.value,
                    SubmissionStatus.COMPLETED.value,
                }
            ),
        ),
    )
    if active_slots >= 3:
        return LimitViolation(
            "Campaign already has three completed or in-flight slots",
            max(0, int((_as_utc(campaign.closes_at) - now).total_seconds())),
        )

    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    monthly = _count(
        session,
        select(func.count(Submission.id)).where(
            Submission.organization_id == organization.id,
            Submission.created_at >= month_start,
        ),
    )
    if monthly >= organization.monthly_quota:
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1, tzinfo=UTC)
        else:
            next_month = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
        return LimitViolation(
            "Monthly organization quota reached", int((next_month - now).total_seconds())
        )
    return None


def estimated_wait_seconds(session: Session, settings: Settings) -> int:
    ahead = _count(
        session,
        select(func.count(Submission.id)).where(Submission.status == SubmissionStatus.QUEUED.value),
    )
    grading = _count(
        session,
        select(func.count(Submission.id)).where(
            Submission.status == SubmissionStatus.GRADING.value
        ),
    )
    capacity = max(1, grading or 1)
    return min(settings.grader_timeout_seconds, int((ahead / capacity) * 60))


def claim_next_submission(
    session: Session,
    settings: Settings,
    worker_id: str,
) -> Submission | None:
    candidates = list(
        session.scalars(
            select(Submission)
            .join(Organization)
            .where(
                Submission.status == SubmissionStatus.QUEUED.value,
                Organization.is_suspended.is_(False),
            )
            .order_by(Submission.queued_at.asc())
            .with_for_update(skip_locked=True)
            .limit(100)
        )
    )
    for candidate in candidates:
        active = _count(
            session,
            select(func.count(Submission.id)).where(
                Submission.organization_id == candidate.organization_id,
                Submission.status == SubmissionStatus.GRADING.value,
            ),
        )
        if active >= settings.concurrent_jobs_per_key:
            continue
        candidate.status = SubmissionStatus.GRADING.value
        candidate.grading_started_at = _utcnow()
        candidate.worker_id = worker_id
        candidate.attempt += 1
        session.commit()
        session.refresh(candidate)
        return candidate
    session.rollback()
    return None


def recover_stale_jobs(session: Session, settings: Settings) -> int:
    stale_before = _utcnow() - timedelta(seconds=settings.stale_job_seconds)
    jobs = list(
        session.scalars(
            select(Submission).where(
                Submission.status == SubmissionStatus.GRADING.value,
                Submission.grading_started_at < stale_before,
            )
        )
    )
    recovered = 0
    for job in jobs:
        if job.attempt >= 3:
            job.status = SubmissionStatus.FAILED.value
            job.error_code = "grading_timeout"
            job.error_message = "The grading worker stopped responding after three attempts."
            job.error_retryable = True
            job.grading_completed_at = _utcnow()
            job.campaign_slot = None
            recovered += 1
        else:
            envelope = job.quarantine_envelope_json or {}
            payload = envelope.get("payload") if isinstance(envelope, dict) else None
            verdict_id = payload.get("verdict_id") if isinstance(payload, dict) else None
            verdict = (
                session.get(QuarantineVerdictUse, verdict_id)
                if isinstance(verdict_id, str)
                else None
            )
            if verdict is not None and verdict.state == "leased":
                deadline = verdict.lease_deadline
                if deadline is not None and _as_utc(deadline) > _utcnow():
                    continue
            if verdict is not None and verdict.state == "consumed":
                job.status = SubmissionStatus.QUARANTINING.value
                job.quarantine_envelope_json = None
                job.quarantine_started_at = None
                job.quarantine_completed_at = None
                job.quarantine_worker_id = None
                job.resolved_file_path = None
                job.resolved_file_sha256 = None
                job.resolved_file_size_bytes = None
                job.resolved_object_version = None
                job.canonical_package_hash_profile_sha256 = None
                job.canonical_package_hash_v1 = None
                job.gold_duplicate_check_json = None
                job.schema_validation_json = None
            else:
                job.status = SubmissionStatus.QUEUED.value
            job.worker_id = None
            job.grading_started_at = None
            recovered += 1
    session.commit()
    return recovered


def complete_submission(
    session: Session,
    submission: Submission,
    report: dict[str, Any],
    provenance: dict[str, str],
    artifacts: tuple[ArtifactFile, ...] = (),
    artifact_retention_days: int = 90,
) -> RunRecord:
    if submission.status != SubmissionStatus.GRADING.value:
        raise RuntimeError("Only grading submissions can be completed")
    if submission.run is not None:
        raise RuntimeError("A grading run already exists for this submission")
    required = {
        "benchmark_version",
        "environment_attestation_sha256",
        "grader_version",
        "grader_source_tree_sha256",
        "scoring_cohort_id",
        "scoring_manifest_sha256",
        "fidelity_score",
        "passed_items",
        "total_items",
        "deck_passed",
        "eligible",
        "tier_scores",
        "anti_cheat_flags",
        "grading_mode",
        "run_kind",
        "submission_id",
        "campaign_id",
        "robustness_group_id",
        "campaign_slot",
        "submitter_id",
        "model_key",
        "model_revision_key",
        "targeted_tier",
        "prompt_variant",
        "assistance_class",
        "generation_profile_sha256",
        "generation_seed",
        "attested_metrics",
        "attestation",
        "environment_attestation",
        "canonical_package_hash_profile_sha256",
        "canonical_package_hash_v1",
        "gold_duplicate_check",
        "submission_sha256",
        "mce_resolved_package_sha256",
        "schema_validation_performed",
        "schema_valid",
        "verification_complete",
        "scoring_completed",
        "campaign_contribution",
    }
    missing = required - report.keys()
    if missing:
        raise ValueError(f"Grader report missing fields: {sorted(missing)}")
    if report["benchmark_version"] != submission.benchmark_version:
        raise ValueError("Grader report benchmark version does not match the submission")
    reported_score = report["fidelity_score"]
    score = None if reported_score is None else float(reported_score)
    if score is not None and not 0 <= score <= 1:
        raise ValueError("Grader report fidelity_score must be null or between 0 and 1")
    if score is None and bool(report["eligible"]):
        raise ValueError("An eligible grader report must contain a fidelity_score")

    campaign = session.scalar(
        select(Campaign).where(Campaign.id == submission.campaign_id).with_for_update()
    )
    if campaign is None:
        raise RuntimeError("Submission campaign no longer exists")
    if submission.campaign_slot is None:
        raise RuntimeError("Submission lost its reserved campaign slot")

    if (
        submission.canonical_package_hash_profile_sha256 is None
        or submission.canonical_package_hash_v1 is None
        or submission.resolved_file_sha256 is None
        or submission.gold_duplicate_check_json is None
        or submission.schema_validation_json is None
    ):
        raise RuntimeError("Submission lost its signed report context")
    gold = submission.gold_duplicate_check_json
    expected_gold_decision = (
        "byte_match"
        if gold.get("byte_match") is True
        else "canonical_match"
        if gold.get("canonical_package_match") is True
        else "clear"
    )
    schema = submission.schema_validation_json
    expected_report_fields: dict[str, Any] = {
        "grading_mode": "hosted",
        "run_kind": "submission",
        "submission_id": submission.id,
        "campaign_id": campaign.id,
        "robustness_group_id": campaign.robustness_group_id,
        "campaign_slot": submission.campaign_slot,
        "submitter_id": submission.organization_id,
        "model_key": submission.model_id,
        "model_revision_key": submission.model_revision_id,
        "targeted_tier": submission.tier,
        "prompt_variant": campaign.prompt_variant,
        "assistance_class": campaign.assistance_class,
        "generation_profile_sha256": campaign.generation_profile_sha256,
        "generation_seed": submission.generation_seed,
        "attested_metrics": submission.efficiency_metrics,
        "attestation": submission.attestation,
        "canonical_package_hash_profile_sha256": (submission.canonical_package_hash_profile_sha256),
        "canonical_package_hash_v1": submission.canonical_package_hash_v1,
        "gold_duplicate_check": expected_gold_decision,
        "submission_sha256": f"sha256:{submission.file_sha256}",
        "mce_resolved_package_sha256": f"sha256:{submission.resolved_file_sha256}",
        "schema_validation_performed": schema.get("performed"),
        "schema_valid": schema.get("valid"),
    }
    for field, expected in expected_report_fields.items():
        if report[field] != expected:
            raise ValueError(f"Grader report {field} does not match the signed submission binding")

    provenance_report_fields = {
        "grader_package_sha256",
        "oci_image_digest",
        "prompt_bundle_sha256",
        "scored_assertion_inventory_sha256",
        "checklist_bundle_sha256",
        "schema_bundle_sha256",
        "schema_root_map_sha256",
        "mce_profile_sha256",
        "asset_manifest_sha256",
        "font_manifest_sha256",
        "gold_submission_sha256",
        "gold_mce_resolved_package_sha256",
        "gold_canonical_package_hash_v1",
    }
    missing_provenance = (provenance_report_fields - report.keys()) | (
        provenance_report_fields - provenance.keys()
    )
    if missing_provenance:
        raise ValueError(f"Grader release provenance missing fields: {sorted(missing_provenance)}")
    for field in provenance_report_fields:
        if report[field] != provenance[field]:
            raise ValueError(f"Grader report {field} does not match worker provenance")

    environment_attestation = report["environment_attestation"]
    if not isinstance(environment_attestation, dict):
        raise ValueError("Grader report environment_attestation must be an object")
    attestation_sha256 = (
        "sha256:" + hashlib.sha256(rfc8785.dumps(environment_attestation)).hexdigest()
    )
    if attestation_sha256 != provenance["environment_attestation_sha256"]:
        raise ValueError("Grader environment attestation does not match worker provenance")

    if score is None and (
        report["scoring_completed"] is not False
        or report["verification_complete"] is not False
        or report["campaign_contribution"] != 0.0
    ):
        raise ValueError("An unscored report must be incomplete with zero campaign contribution")

    actual_manifest = provenance["scoring_manifest_sha256"]
    actual_grader_source = provenance["grader_source_tree_sha256"]
    actual_environment = provenance["environment_attestation_sha256"]
    actual_cohort = scoring_cohort_id(actual_manifest, actual_grader_source, actual_environment)
    report_cohort_matches = (
        report["scoring_cohort_id"] == actual_cohort
        and report["scoring_manifest_sha256"] == actual_manifest
        and report["grader_source_tree_sha256"] == actual_grader_source
        and report["environment_attestation_sha256"] == actual_environment
    )
    cohort_matches = (
        report_cohort_matches
        and actual_cohort == campaign.scoring_cohort_id
        and actual_manifest == campaign.scoring_manifest_sha256
        and actual_grader_source == campaign.grader_source_tree_sha256
        and actual_environment == campaign.environment_attestation_sha256
    )
    eligible = bool(report["eligible"]) and cohort_matches

    completed_at = _utcnow()
    stable_report = dict(report)
    stable_report["environment_hash"] = provenance["environment_hash"]
    stable_report["scoring_manifest_sha256"] = actual_manifest
    stable_report["grader_source_tree_sha256"] = actual_grader_source
    stable_report["environment_attestation_sha256"] = actual_environment
    stable_report["scoring_cohort_id"] = actual_cohort
    stable_report["verification_scope"] = VERIFICATION_SCOPE
    stable_report["verification_label"] = VERIFICATION_LABEL
    for field in (
        "mce_profile_sha256",
        "original_object_version",
        "original_sha256",
        "quarantine_key_id",
        "quarantine_profile_sha256",
        "quarantine_verdict_id",
        "resolved_object_version",
        "resolved_sha256",
        "schema_bundle_sha256",
        "schema_root_map_sha256",
    ):
        if field in provenance:
            stable_report[field] = provenance[field]
    stable_report["eligible"] = eligible
    if not eligible:
        stable_report["campaign_contribution"] = 0.0
    if not cohort_matches:
        flags = list(stable_report.get("anti_cheat_flags", []))
        flags.append("scoring_cohort_mismatch")
        stable_report["anti_cheat_flags"] = flags
    encoded = json.dumps(stable_report, sort_keys=True, separators=(",", ":")).encode()
    run = RunRecord(
        submission_id=submission.id,
        benchmark_version=submission.benchmark_version,
        grader_version=str(report["grader_version"]),
        libreoffice_version=provenance["libreoffice_version"],
        docker_image_hash=provenance["docker_image_hash"],
        font_bundle_hash=provenance["font_bundle_hash"],
        asset_manifest_hash=provenance["asset_manifest_hash"],
        environment_hash=provenance["environment_hash"],
        scoring_cohort_id=actual_cohort,
        scoring_manifest_sha256=actual_manifest,
        grader_source_tree_sha256=actual_grader_source,
        environment_attestation_sha256=actual_environment,
        verification_scope=VERIFICATION_SCOPE,
        verification_label=VERIFICATION_LABEL,
        provenance_json=dict(provenance),
        report_json=stable_report,
        report_sha256=hashlib.sha256(encoded).hexdigest(),
        grading_started_at=submission.grading_started_at or completed_at,
        grading_completed_at=completed_at,
    )
    submission.status = SubmissionStatus.COMPLETED.value
    submission.fidelity_score = score
    submission.eligible = eligible
    submission.campaign_score = score if eligible and score is not None else 0.0
    submission.grading_completed_at = completed_at
    if submission.model_revision.first_submitted_at is None:
        submission.model_revision.first_submitted_at = submission.created_at
    session.add(run)
    session.flush()
    expires_at = completed_at + timedelta(days=artifact_retention_days)
    for artifact in artifacts:
        session.add(
            Artifact(
                run_id=run.id,
                name=artifact.name,
                storage_path=str(artifact.path),
                sha256=artifact.sha256,
                size_bytes=artifact.size_bytes,
                content_type=artifact.content_type,
                expires_at=expires_at,
            )
        )
    session.commit()
    session.refresh(run)
    return run


def fail_submission(
    session: Session,
    submission: Submission,
    *,
    code: str,
    message: str,
    retryable: bool,
) -> None:
    submission.status = SubmissionStatus.FAILED.value
    submission.error_code = code
    submission.error_message = message[:4000]
    submission.error_retryable = retryable
    submission.eligible = False
    submission.campaign_slot = None
    submission.grading_completed_at = _utcnow()
    session.commit()


def status_payload(submission: Submission) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "submission_id": submission.id,
        "campaign_id": submission.campaign_id,
        "campaign_slot": submission.campaign_slot,
        "status": submission.status,
        "result": None,
        "error": None,
        "created_at": submission.created_at,
        "grading_started_at": submission.grading_started_at,
        "grading_completed_at": submission.grading_completed_at,
    }
    if submission.status == SubmissionStatus.COMPLETED.value and submission.run:
        report = submission.run.report_json
        payload["result"] = {
            "fidelity_score": report["fidelity_score"],
            "passed_items": report["passed_items"],
            "total_items": report["total_items"],
            "deck_passed": report["deck_passed"],
            "eligible": report["eligible"],
            "anti_cheat_flags": report.get("anti_cheat_flags", []),
            "repair_triggered": report.get("repair_triggered", False),
            "tier_scores": report["tier_scores"],
            "report_url": f"/v1/submissions/{submission.id}/report",
            "environment_hash": submission.run.environment_hash,
            "campaign_id": submission.campaign_id,
            "campaign_slot": submission.campaign_slot,
            "campaign_score": submission.campaign_score,
            "verification_scope": submission.run.verification_scope,
            "verification_label": submission.run.verification_label,
            "scoring_cohort_id": submission.run.scoring_cohort_id,
            "scoring_manifest_sha256": submission.run.scoring_manifest_sha256,
            "grader_source_tree_sha256": submission.run.grader_source_tree_sha256,
            "environment_attestation_sha256": (submission.run.environment_attestation_sha256),
        }
    elif submission.status in {SubmissionStatus.FAILED.value, SubmissionStatus.REJECTED.value}:
        payload["error"] = {
            "code": submission.error_code or "grading_failed",
            "message": submission.error_message or "Grading failed.",
            "retryable": bool(submission.error_retryable),
        }
    return payload
