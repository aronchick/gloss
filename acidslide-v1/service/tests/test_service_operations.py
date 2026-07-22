from __future__ import annotations

import asyncio
import hashlib
import io
import json
import signal
import socket
import sys
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from acidslide_service import cli, webhooks, worker
from acidslide_service.config import Settings
from acidslide_service.models import (
    Campaign,
    GenerationProfile,
    ModelIdentity,
    ModelRevision,
    Organization,
    Submission,
    SubmissionStatus,
    WebhookDelivery,
)
from acidslide_service.runner import (
    GradeOutcome,
    GradingError,
    HostedArtifactBinding,
    InsecureTestRunner,
    ScoringCohortBinding,
)
from acidslide_service.security import encrypt_secret
from acidslide_service.service import (
    check_submission_limits,
    claim_next_submission,
    fail_submission,
    recover_stale_jobs,
    scoring_cohort_id,
    status_payload,
)
from acidslide_service.storage import UploadTooLargeError, new_object_version, store_upload
from acidslide_service.webhooks import (
    UnsafeWebhookURLError,
    deliver_webhook,
    validate_webhook_url,
)
from acidslide_service.worker import Runner, worker_once

from .conftest import (
    ENVIRONMENT_HASH,
    GRADER_SOURCE_HASH,
    MANIFEST_HASH,
    create_org,
    hosted_artifact_binding,
    submit,
)


def add_organization(session: Session, name: str, quota: int = 30) -> Organization:
    organization = Organization(
        name=name,
        key_prefix=f"prefix-{name}",
        api_key_hash="hash",
        monthly_quota=quota,
    )
    session.add(organization)
    session.flush()
    return organization


def add_submission(
    session: Session,
    organization: Organization,
    *,
    status: str = SubmissionStatus.QUEUED.value,
    attempt: int = 0,
    created_at: datetime | None = None,
    model_version: str = "v1",
) -> Submission:
    model = ModelIdentity(
        organization_id=organization.id,
        display_name="model",
        owner_attribution="submitter-attested",
    )
    session.add(model)
    session.flush()
    revision = ModelRevision(
        model_id=model.id,
        display_name=model_version,
        revision_note="test",
    )
    session.add(revision)
    session.flush()
    timestamp = created_at or datetime.now(UTC)
    profile_sha256 = f"sha256:{hashlib.sha256(revision.id.encode()).hexdigest()}"
    session.add(
        GenerationProfile(
            generation_profile_sha256=profile_sha256,
            organization_id=organization.id,
            model_revision_id=revision.id,
            canonical_profile_json={"permissions": {"human_intervention_permitted": False}},
        )
    )
    session.flush()
    campaign = Campaign(
        organization_id=organization.id,
        model_id=model.id,
        model_revision_id=revision.id,
        tier=1,
        benchmark_version="acidslide-v1.0.0",
        prompt_variant="canonical",
        scoring_cohort_id=scoring_cohort_id(MANIFEST_HASH, GRADER_SOURCE_HASH, ENVIRONMENT_HASH),
        scoring_manifest_sha256=MANIFEST_HASH,
        grader_source_tree_sha256=GRADER_SOURCE_HASH,
        environment_attestation_sha256=ENVIRONMENT_HASH,
        assistance_class="unassisted",
        generation_profile_sha256=profile_sha256,
        window_id=str(uuid.uuid4()),
        opens_at=timestamp - timedelta(minutes=1),
        closes_at=timestamp + timedelta(days=7),
    )
    session.add(campaign)
    session.flush()
    row = Submission(
        organization_id=organization.id,
        model_id=model.id,
        model_revision_id=revision.id,
        campaign_id=campaign.id,
        campaign_slot=1,
        tier=1,
        benchmark_version="acidslide-v1.0.0",
        prompt_variant="canonical",
        status=status,
        file_name="deck.pptx",
        file_path="/private/deck.pptx",
        file_sha256="0" * 64,
        file_size_bytes=100,
        original_object_version=new_object_version(),
        efficiency_metrics={"generation_strategy": "direct"},
        attestation={"human_intervention": False},
        attempt=attempt,
        created_at=timestamp,
        queued_at=timestamp,
    )
    session.add(row)
    session.flush()
    return row


def test_hourly_and_monthly_limits(settings: Settings, sessions: sessionmaker[Session]) -> None:
    now = datetime.now(UTC)
    with sessions() as session:
        organization = add_organization(session, "limited", quota=1)
        add_submission(session, organization, created_at=now - timedelta(minutes=2))
        session.commit()
        hourly_settings = settings.model_copy(update={"submissions_per_hour": 1})
        hourly = check_submission_limits(
            session,
            organization,
            campaign=add_submission(
                session, organization, model_version="hourly-campaign"
            ).campaign,
            settings=hourly_settings,
            now=now,
        )
        assert hourly is not None
        assert hourly.message == "Hourly submission limit reached"

        monthly_settings = settings.model_copy(
            update={"submissions_per_hour": 100, "submissions_per_tuple_window": 100}
        )
        monthly = check_submission_limits(
            session,
            organization,
            campaign=add_submission(
                session, organization, model_version="monthly-campaign"
            ).campaign,
            settings=monthly_settings,
            now=now,
        )
        assert monthly is not None
        assert monthly.message == "Monthly organization quota reached"


def test_claim_fairness_skips_tenant_at_concurrency_cap(
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with sessions() as session:
        busy = add_organization(session, "busy")
        available = add_organization(session, "available")
        for index in range(5):
            add_submission(
                session,
                busy,
                status=SubmissionStatus.GRADING.value,
                model_version=f"active-{index}",
            )
        add_submission(session, busy, created_at=now - timedelta(minutes=2), model_version="queued")
        expected = add_submission(
            session,
            available,
            created_at=now - timedelta(minutes=1),
            model_version="available",
        )
        session.commit()
        claimed = claim_next_submission(session, settings, "worker-1")
        assert claimed is not None
        assert claimed.id == expected.id
        assert claimed.status == SubmissionStatus.GRADING.value


def test_stale_recovery_and_failure_payload(
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    stale = datetime.now(UTC) - timedelta(hours=1)
    with sessions() as session:
        organization = add_organization(session, "recovery")
        retry = add_submission(
            session,
            organization,
            status=SubmissionStatus.GRADING.value,
            attempt=1,
            model_version="retry",
        )
        retry.grading_started_at = stale
        exhausted = add_submission(
            session,
            organization,
            status=SubmissionStatus.GRADING.value,
            attempt=3,
            model_version="exhausted",
        )
        exhausted.grading_started_at = stale
        session.commit()
        assert recover_stale_jobs(session, settings) == 2
        assert retry.status == SubmissionStatus.QUEUED.value
        assert exhausted.status == SubmissionStatus.FAILED.value
        assert status_payload(exhausted)["error"]["code"] == "grading_timeout"

        retry.status = SubmissionStatus.GRADING.value
        fail_submission(
            session,
            retry,
            code="renderer_crash",
            message="Renderer stopped",
            retryable=True,
        )
        assert status_payload(retry)["error"] == {
            "code": "renderer_crash",
            "message": "Renderer stopped",
            "retryable": True,
        }


class ExpectedGradingErrorRunner:
    def grade(
        self,
        _path: Path,
        _tier: int,
        _submission_id: str,
        _cohort: ScoringCohortBinding,
        _artifact: HostedArtifactBinding,
    ) -> GradeOutcome:
        raise GradingError("bad report")


class UnexpectedErrorRunner:
    def grade(
        self,
        _path: Path,
        _tier: int,
        _submission_id: str,
        _cohort: ScoringCohortBinding,
        _artifact: HostedArtifactBinding,
    ) -> GradeOutcome:
        raise TypeError("unexpected")


@pytest.mark.parametrize(
    ("runner", "error_code"),
    [
        (ExpectedGradingErrorRunner(), "grading_failed"),
        (UnexpectedErrorRunner(), "grading_failed"),
    ],
)
def test_worker_failure_paths_do_not_publish(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
    runner: Runner,
    error_code: str,
) -> None:
    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    assert worker_once(settings, sessions, runner, "worker")
    response = client.get(
        f"/v1/submissions/{submission_id}",
        headers={"X-API-Key": api_key},
    ).json()
    assert response["status"] == "failed"
    assert response["error"]["code"] == error_code


def test_admin_cli_init_and_create_org(
    settings: Settings,
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    initialized: list[bool] = []
    monkeypatch.setattr(cli, "initialize_database", lambda: initialized.append(True))
    monkeypatch.setattr(sys, "argv", ["acidslide-admin", "init-db"])
    cli.main()
    assert initialized == [True]
    assert "initialized" in capsys.readouterr().out

    monkeypatch.setattr(cli, "SessionLocal", sessions)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        sys,
        "argv",
        ["acidslide-admin", "create-org", "CLI Lab", "--monthly-quota", "42"],
    )
    cli.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["api_key"].startswith("asv1_")
    with sessions() as session:
        organization = session.scalar(select(Organization).where(Organization.name == "CLI Lab"))
        assert organization is not None
        assert organization.monthly_quota == 42


def test_worker_run_initializes_and_exits_cleanly(
    settings: Settings,
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_settings = settings.model_copy(update={"allow_insecure_test_runner": True})
    callbacks: dict[int, Callable[[int, object], None]] = {}
    initialized: list[bool] = []
    monkeypatch.setattr(worker, "get_settings", lambda: runtime_settings)
    monkeypatch.setattr(worker, "initialize_database", lambda: initialized.append(True))
    monkeypatch.setattr(worker, "start_http_server", lambda _port: None)
    monkeypatch.setattr(worker, "SessionLocal", sessions)

    def capture_signal(signum: int, callback: Callable[[int, object], None]) -> None:
        callbacks[signum] = callback

    monkeypatch.setattr(signal, "signal", capture_signal)

    def stop_on_first_poll(*_args: object) -> bool:
        callback = callbacks[signal.SIGTERM]
        callback(signal.SIGTERM, None)
        return False

    monkeypatch.setattr(worker, "worker_once", stop_on_first_poll)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    worker.run()
    assert initialized == [True]


def test_insecure_runner_requires_opt_in_and_returns_deterministic_grade(
    settings: Settings,
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="disabled"):
        InsecureTestRunner(settings)

    submission = tmp_path / "submission.pptx"
    submission.write_bytes(b"small-deck")
    runner = InsecureTestRunner(settings.model_copy(update={"allow_insecure_test_runner": True}))
    outcome = runner.grade(
        submission,
        2,
        "submission-id",
        ScoringCohortBinding(
            scoring_cohort_id=scoring_cohort_id(
                MANIFEST_HASH,
                GRADER_SOURCE_HASH,
                ENVIRONMENT_HASH,
            ),
            scoring_manifest_sha256=MANIFEST_HASH,
            grader_source_tree_sha256=GRADER_SOURCE_HASH,
            environment_attestation_sha256=ENVIRONMENT_HASH,
        ),
        hosted_artifact_binding("submission-id"),
    )

    assert outcome.report["fidelity_score"] == 0.8
    assert outcome.report["tier_scores"] == {"level_2": {"fidelity_score": 0.8}}
    assert outcome.report["verified_metrics"] == {"submission_file_size_bytes": 10}
    assert outcome.provenance["environment_hash"] == "test-only"


def test_webhook_validation_accepts_public_dns_and_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolve_public(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 8443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 8443)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolve_public)
    validate_webhook_url("https://hooks.example.com:8443/callback?event=grade")


def test_webhook_retries_transport_error_then_stops_on_unsafe_dns(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, api_key = create_org(client, "Webhook retry lab")
    submission_id = submit(client, api_key).json()["submission_id"]
    failures = iter([OSError("connection reset"), UnsafeWebhookURLError("DNS rebound")])
    pauses: list[float] = []

    def fail_delivery(_url: str, _body: bytes, _headers: dict[str, str]) -> int:
        raise next(failures)

    monkeypatch.setattr(webhooks, "_post_pinned", fail_delivery)
    monkeypatch.setattr(time, "sleep", pauses.append)
    with sessions() as session:
        submission = session.scalar(select(Submission).where(Submission.id == submission_id))
        assert submission is not None
        assert deliver_webhook(session, submission, {}, settings)
        submission.webhook_url = "https://hooks.example.com/acidslide"
        submission.webhook_secret_encrypted = encrypt_secret("a-secret-at-least-16", settings)
        session.commit()

        assert not deliver_webhook(session, submission, {"status": "failed"}, settings)
        deliveries = list(
            session.scalars(
                select(WebhookDelivery)
                .where(WebhookDelivery.submission_id == submission_id)
                .order_by(WebhookDelivery.attempt)
            )
        )

    assert [(row.attempt, row.outcome) for row in deliveries] == [
        (1, "OSError"),
        (2, "UnsafeWebhookURLError"),
    ]
    assert pauses == [1]


def test_oversize_upload_is_removed_and_closed(settings: Settings) -> None:
    upload = UploadFile(filename="oversize.pptx", file=io.BytesIO(b"too-large"))
    limited = settings.model_copy(update={"max_upload_bytes": 4, "upload_chunk_bytes": 3})

    with pytest.raises(UploadTooLargeError, match="4-byte upload limit"):
        asyncio.run(store_upload(upload, "oversize-submission", limited))

    assert upload.file.closed
    assert not (limited.storage_path / "staging" / "oversize-submission.upload").exists()
    assert not (limited.storage_path / "submissions" / "oversize-submission.pptx").exists()
