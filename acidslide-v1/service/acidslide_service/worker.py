"""Asynchronous database-queue worker for controlled grading."""

from __future__ import annotations

import logging
import os
import signal
import socket
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from prometheus_client import Counter, Histogram, start_http_server
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session, sessionmaker

from acidslide_service.canary import drift_canary_health
from acidslide_service.config import Settings, get_settings
from acidslide_service.database import SessionLocal, initialize_database
from acidslide_service.leaderboard import write_snapshot
from acidslide_service.models import QuarantineVerdictUse, Submission, WorkerHeartbeat, utcnow
from acidslide_service.quarantine_handoff import (
    ObjectBinding,
    QuarantineHandoffError,
    load_verification_keys,
    require_binding,
    verify_envelope,
)
from acidslide_service.runner import (
    DockerGradingRunner,
    GradeOutcome,
    GradingError,
    HostedArtifactBinding,
    InsecureTestRunner,
    ScoringCohortBinding,
)
from acidslide_service.service import (
    claim_next_submission,
    complete_submission,
    fail_submission,
    recover_stale_jobs,
    status_payload,
)
from acidslide_service.storage import (
    ImmutableObjectError,
    purge_expired_artifacts,
    verify_immutable_object,
)
from acidslide_service.webhooks import deliver_webhook

logger = logging.getLogger("acidslide.worker")
GRADES = Counter("acidslide_grades_total", "Grading outcomes", ("outcome",))
GRADE_SECONDS = Histogram("acidslide_grading_duration_seconds", "Controlled grading duration")


class Runner(Protocol):
    def grade(
        self,
        submission_path: Path,
        tier: int,
        submission_id: str,
        cohort: ScoringCohortBinding,
        artifact: HostedArtifactBinding,
    ) -> GradeOutcome: ...


def _required_string(mapping: dict[str, object], name: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise QuarantineHandoffError(f"Signed handoff {name} is missing")
    return value


def _hosted_artifact_binding(
    submission: Submission,
    handoff: dict[str, object],
) -> HostedArtifactBinding:
    """Build the exact hosted report context from signed Stage-0.5 state."""
    campaign = submission.campaign
    if (
        submission.campaign_slot is None
        or submission.resolved_file_sha256 is None
        or submission.canonical_package_hash_v1 is None
        or submission.canonical_package_hash_profile_sha256 is None
        or submission.schema_validation_json is None
        or submission.gold_duplicate_check_json is None
    ):
        raise QuarantineHandoffError("Submission lacks signed hosted report context")

    schema = submission.schema_validation_json
    performed = schema.get("performed")
    valid = schema.get("valid")
    violations = schema.get("violations")
    if not isinstance(performed, bool) or not isinstance(valid, bool):
        raise QuarantineHandoffError("Signed schema validation flags are malformed")
    if not isinstance(violations, list) or not all(
        isinstance(violation, str) for violation in violations
    ):
        raise QuarantineHandoffError("Signed schema validation violations are malformed")
    if not performed:
        raise QuarantineHandoffError("Signed Stage 0.5 schema validation was not performed")

    gold = submission.gold_duplicate_check_json
    byte_match = gold.get("byte_match")
    canonical_match = gold.get("canonical_package_match")
    if not isinstance(byte_match, bool) or not isinstance(canonical_match, bool):
        raise QuarantineHandoffError("Signed gold duplicate flags are malformed")
    gold_duplicate_check = (
        "byte_match" if byte_match else "canonical_match" if canonical_match else "clear"
    )
    if gold.get("decision") != gold_duplicate_check:
        raise QuarantineHandoffError("Signed gold duplicate decision is inconsistent")

    profiles_value = handoff.get("profiles")
    if not isinstance(profiles_value, dict):
        raise QuarantineHandoffError("Signed handoff profiles are missing")
    profiles = {str(key): value for key, value in profiles_value.items()}
    return HostedArtifactBinding(
        prompt_variant=submission.prompt_variant,
        generation_seed=submission.generation_seed,
        schema_validation_performed=performed,
        schema_valid=valid,
        schema_violations=tuple(violations),
        schema_bundle_sha256=_required_string(profiles, "schema_bundle_sha256"),
        schema_root_map_sha256=_required_string(profiles, "schema_root_map_sha256"),
        mce_profile_sha256=_required_string(profiles, "mce_profile_sha256"),
        canonical_package_hash_profile_sha256=(submission.canonical_package_hash_profile_sha256),
        canonical_package_hash_v1=submission.canonical_package_hash_v1,
        gold_duplicate_check=gold_duplicate_check,
        submission_sha256=f"sha256:{submission.file_sha256}",
        mce_resolved_package_sha256=f"sha256:{submission.resolved_file_sha256}",
        assistance_class=campaign.assistance_class,
        generation_profile_sha256=campaign.generation_profile_sha256,
        attested_metrics=submission.efficiency_metrics,
        attestation=submission.attestation,
        submission_id=submission.id,
        campaign_id=submission.campaign_id,
        robustness_group_id=campaign.robustness_group_id,
        campaign_slot=submission.campaign_slot,
        submitter_id=submission.organization_id,
        model_key=submission.model_id,
        model_revision_key=submission.model_revision_id,
    )


def _resolved_binding(submission: Submission) -> ObjectBinding:
    if (
        submission.resolved_object_version is None
        or submission.resolved_file_sha256 is None
        or submission.resolved_file_size_bytes is None
    ):
        raise QuarantineHandoffError("Submission has no immutable resolved-package binding")
    return ObjectBinding(
        object_version=submission.resolved_object_version,
        sha256=f"sha256:{submission.resolved_file_sha256}",
        size_bytes=submission.resolved_file_size_bytes,
    )


def _original_binding(submission: Submission) -> ObjectBinding:
    return ObjectBinding(
        object_version=submission.original_object_version,
        sha256=f"sha256:{submission.file_sha256}",
        size_bytes=submission.file_size_bytes,
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def lease_verdict(
    session: Session,
    *,
    verdict_id: str,
    submission_id: str,
    worker_id: str,
    lease_seconds: int,
    now: datetime | None = None,
) -> int:
    """Atomically lease an issued or expired signed verdict and return its generation."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    verdict = session.scalar(
        select(QuarantineVerdictUse)
        .where(
            QuarantineVerdictUse.verdict_id == verdict_id,
            QuarantineVerdictUse.submission_id == submission_id,
        )
        .with_for_update()
    )
    if verdict is None:
        session.rollback()
        raise QuarantineHandoffError("Quarantine verdict was not issued by the dispatcher")
    if verdict.state == "consumed":
        session.rollback()
        raise QuarantineHandoffError("Quarantine verdict has already been consumed")
    if verdict.state == "leased" and (
        verdict.lease_deadline is None or _as_utc(verdict.lease_deadline) > moment
    ):
        session.rollback()
        raise QuarantineHandoffError("Quarantine verdict already has an active lease")
    if verdict.state not in {"issued", "leased"}:
        session.rollback()
        raise QuarantineHandoffError("Quarantine verdict has an invalid lifecycle state")

    previous_state = verdict.state
    previous_generation = verdict.generation
    conditions = [
        QuarantineVerdictUse.verdict_id == verdict_id,
        QuarantineVerdictUse.submission_id == submission_id,
        QuarantineVerdictUse.state == previous_state,
        QuarantineVerdictUse.generation == previous_generation,
    ]
    if previous_state == "leased":
        conditions.append(QuarantineVerdictUse.lease_deadline <= moment)
    result = session.execute(
        update(QuarantineVerdictUse)
        .where(*conditions)
        .values(
            state="leased",
            generation=previous_generation + 1,
            worker_id=worker_id,
            lease_deadline=moment + timedelta(seconds=lease_seconds),
            consumed_at=None,
        )
        .execution_options(synchronize_session=False)
    )
    if getattr(result, "rowcount", 0) != 1:
        session.rollback()
        raise QuarantineHandoffError("Quarantine verdict lease was concurrently changed")
    session.commit()
    session.expire_all()
    return previous_generation + 1


def consume_verdict(
    session: Session,
    *,
    verdict_id: str,
    submission_id: str,
    worker_id: str,
    generation: int,
    now: datetime | None = None,
) -> None:
    """Atomically consume the exact lease generation immediately before parsing."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    result = session.execute(
        update(QuarantineVerdictUse)
        .where(
            QuarantineVerdictUse.verdict_id == verdict_id,
            QuarantineVerdictUse.submission_id == submission_id,
            QuarantineVerdictUse.state == "leased",
            QuarantineVerdictUse.generation == generation,
            QuarantineVerdictUse.worker_id == worker_id,
            QuarantineVerdictUse.lease_deadline > moment,
        )
        .values(
            state="consumed",
            lease_deadline=None,
            consumed_at=moment,
        )
        .execution_options(synchronize_session=False)
    )
    if getattr(result, "rowcount", 0) != 1:
        session.rollback()
        raise QuarantineHandoffError(
            "Quarantine verdict lease is expired, stale, or owned by another worker"
        )
    session.commit()
    session.expire_all()


def verify_and_consume_handoff(
    session: Session,
    submission: Submission,
    settings: Settings,
    worker_id: str,
) -> tuple[Path, dict[str, object]]:
    """Verify the signed handoff and atomically consume its single-use ID."""
    if submission.campaign_slot is None or submission.resolved_file_path is None:
        raise QuarantineHandoffError("Submission lost its resolved package or campaign slot")
    payload = verify_envelope(
        submission.quarantine_envelope_json,
        load_verification_keys(settings.quarantine_verification_keys_json),
    )
    resolved = _resolved_binding(submission)
    if (
        submission.canonical_package_hash_v1 is None
        or submission.gold_duplicate_check_json is None
        or submission.schema_validation_json is None
    ):
        raise QuarantineHandoffError("Submission lacks signed Stage 0.5 report context")
    require_binding(
        payload,
        original=_original_binding(submission),
        resolved=resolved,
        submission_id=submission.id,
        campaign_id=submission.campaign_id,
        campaign_slot=submission.campaign_slot,
        expected_profiles={
            "canonical_package_hash_profile_sha256": (
                settings.active_canonical_package_hash_profile_sha256
            ),
            "mce_profile_sha256": settings.active_mce_profile_sha256,
            "quarantine_profile_sha256": settings.active_quarantine_profile_sha256,
            "schema_bundle_sha256": settings.active_schema_bundle_sha256,
            "schema_root_map_sha256": settings.active_schema_root_map_sha256,
        },
        expected_context={
            "canonical_package_hash_v1": submission.canonical_package_hash_v1,
            "control_authorization_object_version": None,
            "control_authorization_sha256": None,
            "gold_duplicate_check": submission.gold_duplicate_check_json,
            "run_kind": "submission",
            "schema_validation": submission.schema_validation_json,
        },
    )
    resolved_path = verify_immutable_object(
        Path(submission.resolved_file_path),
        settings,
        kind="resolved",
        binding=resolved,
    )
    verdict_id = str(payload["verdict_id"])
    generation = lease_verdict(
        session,
        verdict_id=verdict_id,
        submission_id=submission.id,
        worker_id=worker_id,
        lease_seconds=settings.stale_job_seconds,
    )
    consume_verdict(
        session,
        verdict_id=verdict_id,
        submission_id=submission.id,
        worker_id=worker_id,
        generation=generation,
    )
    session.refresh(submission)
    return resolved_path, payload


def worker_once(
    settings: Settings,
    sessions: sessionmaker[Session],
    runner: Runner,
    worker_id: str,
) -> bool:
    with sessions() as session:
        if settings.app_env == "production":
            canary = drift_canary_health(session, settings)
            if not canary.ready:
                logger.error(
                    "Grading blocked by drift canary code=%s run_id=%s",
                    canary.code,
                    canary.run_id,
                )
                return False
        submission = claim_next_submission(session, settings, worker_id)
        if submission is None:
            return False
        started = time.monotonic()
        try:
            resolved_path, handoff = verify_and_consume_handoff(
                session, submission, settings, worker_id
            )
            campaign = submission.campaign
            outcome = runner.grade(
                resolved_path,
                submission.tier,
                submission.id,
                ScoringCohortBinding(
                    scoring_cohort_id=campaign.scoring_cohort_id,
                    scoring_manifest_sha256=campaign.scoring_manifest_sha256,
                    grader_source_tree_sha256=campaign.grader_source_tree_sha256,
                    environment_attestation_sha256=campaign.environment_attestation_sha256,
                ),
                _hosted_artifact_binding(submission, handoff),
            )
            profiles = handoff["profiles"]
            assert isinstance(profiles, dict)
            provenance = {
                **outcome.provenance,
                "original_object_version": submission.original_object_version,
                "original_sha256": f"sha256:{submission.file_sha256}",
                "quarantine_key_id": str(handoff["key_id"]),
                "quarantine_verdict_id": str(handoff["verdict_id"]),
                "resolved_object_version": str(submission.resolved_object_version),
                "resolved_sha256": f"sha256:{submission.resolved_file_sha256}",
                **{str(name): str(value) for name, value in profiles.items()},
            }
            complete_submission(
                session,
                submission,
                outcome.report,
                provenance,
                outcome.artifacts,
                settings.artifact_retention_days,
            )
            GRADES.labels("completed").inc()
        except (QuarantineHandoffError, ImmutableObjectError) as exc:
            fail_submission(
                session,
                submission,
                code="quarantine_handoff_mismatch",
                message=str(exc),
                retryable=False,
            )
            GRADES.labels("quarantine_handoff_mismatch").inc()
        except GradingError as exc:
            fail_submission(
                session,
                submission,
                code=exc.code,
                message=str(exc),
                retryable=exc.retryable,
            )
            GRADES.labels(exc.code).inc()
        except Exception as exc:
            logger.exception("Unexpected grading failure submission_id=%s", submission.id)
            fail_submission(
                session,
                submission,
                code="grading_failed",
                message=f"Controlled grader failed: {type(exc).__name__}",
                retryable=False,
            )
            GRADES.labels("grading_failed").inc()
        finally:
            GRADE_SECONDS.observe(time.monotonic() - started)
        session.refresh(submission)
        if submission.status == "completed":
            try:
                write_snapshot(session, settings, submission.benchmark_version)
            except Exception:
                session.rollback()
                logger.exception("Leaderboard snapshot failed submission_id=%s", submission.id)
        if submission.webhook_url:
            try:
                deliver_webhook(session, submission, status_payload(submission), settings)
            except Exception:
                session.rollback()
                logger.exception("Webhook delivery failed submission_id=%s", submission.id)
        return True


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if settings.app_env == "production":
        with SessionLocal() as session:
            session.execute(text("SELECT version_num FROM alembic_version"))
    else:
        initialize_database()
    start_http_server(settings.worker_metrics_port)
    worker_id = f"grading:{socket.gethostname()}:{os.getpid()}"
    runner: Runner
    if settings.allow_insecure_test_runner:
        runner = InsecureTestRunner(settings)
    else:
        runner = DockerGradingRunner(settings)
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with SessionLocal() as session:
        recovered = recover_stale_jobs(session, settings)
        if recovered:
            logger.warning("Recovered %s stale grading jobs", recovered)
    logger.info("Worker started worker_id=%s", worker_id)
    last_heartbeat = 0.0
    last_retention_sweep = 0.0
    while not stopping:
        now = time.monotonic()
        if now - last_heartbeat >= settings.worker_heartbeat_seconds:
            with SessionLocal() as session:
                heartbeat = session.get(WorkerHeartbeat, worker_id)
                if heartbeat is None:
                    heartbeat = WorkerHeartbeat(
                        worker_id=worker_id,
                        hostname=socket.gethostname(),
                        process_id=os.getpid(),
                    )
                    session.add(heartbeat)
                heartbeat.last_seen_at = utcnow()
                session.commit()
            last_heartbeat = now
        if now - last_retention_sweep >= 3600:
            with SessionLocal() as session:
                removed = purge_expired_artifacts(session, settings)
                if removed:
                    logger.info("Purged %s expired private artifacts", removed)
            last_retention_sweep = now
        if not worker_once(settings, SessionLocal, runner, worker_id):
            time.sleep(settings.worker_poll_seconds)
    logger.info("Worker stopped worker_id=%s", worker_id)


if __name__ == "__main__":
    run()
