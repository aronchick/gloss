"""Long-lived dispatcher for disposable Stage 0/0.5 quarantine jobs."""

from __future__ import annotations

import logging
import os
import signal
import socket
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from acidslide_service.config import Settings, get_settings
from acidslide_service.database import SessionLocal, initialize_database
from acidslide_service.models import (
    Organization,
    QuarantineVerdictUse,
    SecurityEvent,
    Submission,
    SubmissionStatus,
    WorkerHeartbeat,
    utcnow,
)
from acidslide_service.quarantine_handoff import (
    ObjectBinding,
    QuarantineHandoffError,
    QuarantineJobBinding,
    load_private_key,
    load_verification_keys,
    verify_envelope,
)
from acidslide_service.quarantine_runner import (
    DockerQuarantineRunner,
    InsecureInProcessQuarantineRunner,
    QuarantineRunner,
    QuarantineRunnerError,
)
from acidslide_service.storage import (
    ImmutableObjectError,
    new_object_version,
    publish_resolved_object,
)

logger = logging.getLogger("acidslide.quarantine-worker")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def expected_profiles(settings: Settings) -> dict[str, str]:
    return {
        "canonical_package_hash_profile_sha256": (
            settings.active_canonical_package_hash_profile_sha256
        ),
        "mce_profile_sha256": settings.active_mce_profile_sha256,
        "quarantine_profile_sha256": settings.active_quarantine_profile_sha256,
        "schema_bundle_sha256": settings.active_schema_bundle_sha256,
        "schema_root_map_sha256": settings.active_schema_root_map_sha256,
    }


def original_binding(submission: Submission) -> ObjectBinding:
    return ObjectBinding(
        object_version=submission.original_object_version,
        sha256=f"sha256:{submission.file_sha256}",
        size_bytes=submission.file_size_bytes,
    )


def _payload_binding(value: object, field: str) -> ObjectBinding:
    if not isinstance(value, dict):
        raise QuarantineHandoffError(f"Verdict {field} object binding is missing")
    try:
        return ObjectBinding(
            object_version=str(value["object_version"]),
            sha256=str(value["sha256"]),
            size_bytes=int(value["size_bytes"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise QuarantineHandoffError(f"Verdict {field} object binding is invalid") from exc


def _require_common_binding(
    payload: dict[str, Any],
    submission: Submission,
    settings: Settings,
) -> None:
    if submission.campaign_slot is None:
        raise QuarantineHandoffError("Submission has no reserved campaign slot")
    expected: dict[str, object] = {
        "campaign_id": submission.campaign_id,
        "campaign_slot": submission.campaign_slot,
        "original": original_binding(submission).as_dict(),
        "profiles": expected_profiles(settings),
        "run_kind": "submission",
        "control_authorization_sha256": None,
        "control_authorization_object_version": None,
        "submission_id": submission.id,
    }
    mismatches = [name for name, value in expected.items() if payload.get(name) != value]
    if mismatches:
        raise QuarantineHandoffError(
            "Quarantine verdict binding mismatch: " + ", ".join(sorted(mismatches))
        )


def claim_next_quarantine(
    session: Session,
    settings: Settings,
    worker_id: str,
) -> Submission | None:
    stale_before = datetime.now(UTC) - timedelta(seconds=settings.stale_job_seconds)
    submission = session.scalar(
        select(Submission)
        .where(
            Submission.status == SubmissionStatus.QUARANTINING.value,
            (
                Submission.quarantine_started_at.is_(None)
                | (Submission.quarantine_started_at < stale_before)
            ),
        )
        .order_by(Submission.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if submission is None:
        session.rollback()
        return None
    if submission.quarantine_attempt >= 3:
        submission.status = SubmissionStatus.FAILED.value
        submission.error_code = "quarantine_unavailable"
        submission.error_message = "Quarantine failed after three isolated attempts."
        submission.error_retryable = True
        submission.campaign_slot = None
        submission.quarantine_completed_at = datetime.now(UTC)
        session.commit()
        return None
    submission.quarantine_started_at = datetime.now(UTC)
    submission.quarantine_worker_id = worker_id
    submission.quarantine_attempt += 1
    session.commit()
    session.refresh(submission)
    return submission


def _reject_submission(
    session: Session,
    submission: Submission,
    *,
    code: str,
    reason: str,
) -> None:
    submission.status = SubmissionStatus.REJECTED.value
    submission.error_code = code
    submission.error_message = reason[:4000]
    submission.error_retryable = False
    submission.eligible = False
    submission.campaign_slot = None
    submission.quarantine_completed_at = datetime.now(UTC)
    organization = session.get(Organization, submission.organization_id)
    malicious_markers = (
        "Executable content",
        "Nested archive",
        "OLE content",
        "Active content",
        "Unsafe path",
        "Encrypted ZIP",
        "External OOXML",
    )
    if (
        organization is not None
        and code == "quarantine_rejected"
        and any(marker in reason for marker in malicious_markers)
    ):
        organization.malicious_rejections += 1
        if organization.malicious_rejections >= 5:
            organization.is_suspended = True
    session.add(
        SecurityEvent(
            organization_id=submission.organization_id,
            event_type=code,
            detail=reason[:4000],
        )
    )
    session.commit()


def quarantine_once(
    settings: Settings,
    sessions: sessionmaker[Session],
    runner: QuarantineRunner,
    worker_id: str,
) -> bool:
    with sessions() as session:
        submission = claim_next_quarantine(session, settings, worker_id)
        if submission is None:
            return False
        if submission.campaign_slot is None:
            _reject_submission(
                session,
                submission,
                code="quarantine_handoff_mismatch",
                reason="Submission lost its reserved campaign slot before quarantine",
            )
            return True
        binding = QuarantineJobBinding(
            submission_id=submission.id,
            campaign_id=submission.campaign_id,
            campaign_slot=submission.campaign_slot,
            tier=submission.tier,
            original=original_binding(submission),
            resolved_object_version=new_object_version(),
        )
        result = None
        try:
            result = runner.inspect(original_path=Path(submission.file_path), binding=binding)
            payload = verify_envelope(
                result.envelope,
                load_verification_keys(settings.quarantine_verification_keys_json),
            )
            _require_common_binding(payload, submission, settings)
            submission.quarantine_envelope_json = result.envelope
            if payload.get("outcome") != "accepted":
                reason = str(payload.get("reason") or "Quarantine rejected the package")
                code = "invalid_tier" if reason.startswith("Tier ") else "quarantine_rejected"
                _reject_submission(session, submission, code=code, reason=reason)
                return True

            signed_resolved = _payload_binding(payload.get("resolved"), "resolved")
            if signed_resolved.object_version != binding.resolved_object_version:
                raise QuarantineHandoffError("Resolved object version was substituted")
            if result.resolved_path is None:
                raise QuarantineHandoffError("Accepted verdict has no resolved package")
            resolved_path = publish_resolved_object(result.resolved_path, settings, signed_resolved)
            canonical_hash = payload.get("canonical_package_hash_v1")
            gold_check = payload.get("gold_duplicate_check")
            schema_validation = payload.get("schema_validation")
            if (
                not isinstance(canonical_hash, str)
                or not isinstance(gold_check, dict)
                or not isinstance(schema_validation, dict)
            ):
                raise QuarantineHandoffError(
                    "Accepted verdict lacks canonical hash, gold check, or schema result"
                )
            submission.resolved_file_path = str(resolved_path)
            submission.resolved_file_sha256 = signed_resolved.sha256.removeprefix("sha256:")
            submission.resolved_file_size_bytes = signed_resolved.size_bytes
            submission.resolved_object_version = signed_resolved.object_version
            submission.run_kind = "submission"
            submission.control_authorization_sha256 = None
            submission.control_authorization_object_version = None
            submission.canonical_package_hash_profile_sha256 = (
                settings.active_canonical_package_hash_profile_sha256
            )
            submission.canonical_package_hash_v1 = canonical_hash
            submission.gold_duplicate_check_json = gold_check
            submission.schema_validation_json = schema_validation
            verdict_id = payload.get("verdict_id")
            if not isinstance(verdict_id, str) or not verdict_id:
                raise QuarantineHandoffError("Accepted verdict has no single-use ID")
            session.add(
                QuarantineVerdictUse(
                    verdict_id=verdict_id,
                    submission_id=submission.id,
                    state="issued",
                    generation=0,
                )
            )
            submission.status = SubmissionStatus.QUEUED.value
            submission.queued_at = datetime.now(UTC)
            submission.quarantine_completed_at = datetime.now(UTC)
            session.commit()
            return True
        except (QuarantineHandoffError, ImmutableObjectError) as exc:
            _reject_submission(
                session,
                submission,
                code="quarantine_handoff_mismatch",
                reason=str(exc),
            )
            return True
        except QuarantineRunnerError as exc:
            submission.status = SubmissionStatus.FAILED.value
            submission.error_code = "quarantine_unavailable"
            submission.error_message = str(exc)[:4000]
            submission.error_retryable = True
            submission.campaign_slot = None
            submission.quarantine_completed_at = datetime.now(UTC)
            session.commit()
            return True
        finally:
            if result is not None:
                result.cleanup()


def _validate_signing_configuration(settings: Settings) -> None:
    if not settings.quarantine_signing_key_id or not settings.quarantine_signing_private_key:
        raise RuntimeError("Quarantine signing key configuration is incomplete")
    private_key = load_private_key(settings.quarantine_signing_private_key)
    keys = load_verification_keys(settings.quarantine_verification_keys_json)
    configured = keys.get(settings.quarantine_signing_key_id)
    if configured is None:
        raise RuntimeError("Quarantine signing key ID is not in the verification key set")
    if private_key.public_key().public_bytes_raw() != configured.public_key.public_bytes_raw():
        raise RuntimeError("Quarantine signing private/public keys do not match")


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    _validate_signing_configuration(settings)
    if settings.app_env == "production":
        with SessionLocal() as session:
            session.execute(text("SELECT version_num FROM alembic_version"))
    else:
        initialize_database()
    runner: QuarantineRunner
    if settings.allow_insecure_quarantine_runner:
        runner = InsecureInProcessQuarantineRunner(settings)
    else:
        runner = DockerQuarantineRunner(settings)
    runner.assert_ready()
    worker_id = f"quarantine:{socket.gethostname()}:{os.getpid()}"
    stopping = False
    last_heartbeat = 0.0

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
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
        if not quarantine_once(settings, SessionLocal, runner, worker_id):
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    run()
