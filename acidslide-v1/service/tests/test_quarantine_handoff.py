from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from acidslide_service.config import Settings
from acidslide_service.models import QuarantineVerdictUse, Submission
from acidslide_service.quarantine_handoff import (
    ObjectBinding,
    QuarantineHandoffError,
    QuarantineJobBinding,
    build_payload,
    jcs_bytes,
    load_private_key,
    load_public_key,
    load_verification_keys,
    parse_utc,
    require_binding,
    sign_payload,
    verify_envelope,
)
from acidslide_service.quarantine_runner import (
    DockerQuarantineRunner,
    InsecureInProcessQuarantineRunner,
    LocalSubprocessQuarantineRunner,
    QuarantineRunnerError,
    QuarantineRunResult,
)
from acidslide_service.quarantine_worker import claim_next_quarantine, quarantine_once
from acidslide_service.service import claim_next_submission, recover_stale_jobs
from acidslide_service.storage import InvalidUploadError, new_object_version, store_upload
from acidslide_service.worker import (
    consume_verdict,
    lease_verdict,
    verify_and_consume_handoff,
    worker_once,
)

from .conftest import create_campaign, create_org, make_pptx, metadata, submit
from .test_worker_and_leaderboard import FakeRunner


class FailingQuarantineRunner:
    def assert_ready(self) -> None:
        return None

    def inspect(self, **_kwargs: Any) -> QuarantineRunResult:
        raise QuarantineRunnerError("orchestrator unavailable")


class RecordingDockerQuarantineRunner(DockerQuarantineRunner):
    def __init__(self, settings: Settings, image_hash: str = "sha256:image") -> None:
        super().__init__(settings)
        self.image_hash = image_hash
        self.commands: list[list[str]] = []

    def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        self.commands.append(args)
        if args[:3] == ["docker", "image", "inspect"]:
            identity = {
                "id": "sha256:config",
                "os": "linux",
                "architecture": "amd64",
                "repo_digests": [f"acidslide/quarantine@{self.image_hash}"],
            }
            return subprocess.CompletedProcess(args, 0, json.dumps(identity), "")
        output_mount = next(
            value
            for value in args
            if value.startswith("type=bind,source=") and "target=/output" in value
        )
        output = Path(output_mount.split(",", 2)[1].removeprefix("source="))
        (output / "resolved.pptx").write_bytes(b"resolved")
        (output / "verdict.json").write_text('{"sandbox":"ok"}', encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "")


class QuarantineIdentityRunner(DockerQuarantineRunner):
    def __init__(self, settings: Settings, identity: object) -> None:
        super().__init__(settings)
        self.identity = identity

    def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, json.dumps(self.identity), "")


def _row(sessions: sessionmaker[Session], submission_id: str) -> Submission:
    with sessions() as session:
        submission = session.scalar(select(Submission).where(Submission.id == submission_id))
        assert submission is not None
        session.expunge(submission)
        return submission


def _resign(
    sessions: sessionmaker[Session],
    settings: Settings,
    submission_id: str,
    mutate: Any,
) -> None:
    with sessions() as session:
        submission = session.scalar(select(Submission).where(Submission.id == submission_id))
        assert submission is not None
        assert submission.quarantine_envelope_json is not None
        payload = dict(submission.quarantine_envelope_json["payload"])
        mutate(payload)
        submission.quarantine_envelope_json = sign_payload(
            payload,
            load_private_key(settings.quarantine_signing_private_key),
        )
        session.commit()


def test_api_control_plane_never_opens_zip_or_xml(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, api_key = create_org(client)
    campaign_id = create_campaign(client, api_key)
    deck = make_pptx()

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("API process attempted ZIP/XML parsing")

    monkeypatch.setattr(zipfile, "ZipFile", forbidden)
    monkeypatch.setattr(etree, "fromstring", forbidden)
    response = client.post(
        "/v1/submissions",
        headers={"Authorization": f"Bearer {api_key}"},
        files={
            "metadata": (None, json.dumps(metadata(campaign_id)), "application/json"),
            "file": (
                "submission.pptx",
                deck,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "quarantining"

    assert quarantine_once(
        settings,
        sessions,
        LocalSubprocessQuarantineRunner(settings),
        "subprocess-quarantine",
    )
    assert _row(sessions, response.json()["submission_id"]).status == "queued"


def test_original_object_tamper_is_rejected_before_parse(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    campaign_id = create_campaign(client, api_key)
    response = client.post(
        "/v1/submissions",
        headers={"X-API-Key": api_key},
        files={
            "metadata": (None, json.dumps(metadata(campaign_id)), "application/json"),
            "file": ("submission.pptx", make_pptx(), "application/octet-stream"),
        },
    )
    submission = _row(sessions, response.json()["submission_id"])
    original = Path(submission.file_path)
    os.chmod(original, 0o600)
    original.write_bytes(original.read_bytes() + b"tamper")
    os.chmod(original, 0o400)

    assert quarantine_once(
        settings,
        sessions,
        InsecureInProcessQuarantineRunner(settings),
        "quarantine",
    )
    rejected = _row(sessions, submission.id)
    assert rejected.status == "rejected"
    assert rejected.campaign_slot is None
    assert "digest or size changed" in (rejected.error_message or "")


def test_quarantine_orchestrator_failure_and_attempt_exhaustion_release_slots(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    first_campaign = create_campaign(client, api_key)
    first = client.post(
        "/v1/submissions",
        headers={"X-API-Key": api_key},
        files={
            "metadata": (None, json.dumps(metadata(first_campaign)), "application/json"),
            "file": ("submission.pptx", make_pptx(), "application/octet-stream"),
        },
    )
    assert quarantine_once(settings, sessions, FailingQuarantineRunner(), "quarantine")
    failed = _row(sessions, first.json()["submission_id"])
    assert failed.status == "failed"
    assert failed.error_code == "quarantine_unavailable"
    assert failed.campaign_slot is None

    second_campaign = create_campaign(client, api_key)
    second = client.post(
        "/v1/submissions",
        headers={"X-API-Key": api_key},
        files={
            "metadata": (None, json.dumps(metadata(second_campaign)), "application/json"),
            "file": ("submission.pptx", make_pptx(), "application/octet-stream"),
        },
    )
    with sessions() as session:
        exhausted = session.scalar(
            select(Submission).where(Submission.id == second.json()["submission_id"])
        )
        assert exhausted is not None
        exhausted.quarantine_attempt = 3
        session.commit()
        assert claim_next_quarantine(session, settings, "quarantine") is None
    exhausted_row = _row(sessions, second.json()["submission_id"])
    assert exhausted_row.status == "failed"
    assert exhausted_row.campaign_slot is None


def test_opaque_upload_rejects_extension_and_magic_only(
    settings: Settings,
) -> None:
    wrong_extension = UploadFile(filename="deck.zip", file=io.BytesIO(make_pptx()))
    with pytest.raises(InvalidUploadError, match="extension"):
        asyncio.run(store_upload(wrong_extension, "wrong-extension", settings))

    wrong_magic = UploadFile(filename="deck.pptx", file=io.BytesIO(b"not-a-package"))
    with pytest.raises(InvalidUploadError, match="not an OOXML"):
        asyncio.run(store_upload(wrong_magic, "wrong-magic", settings))


def test_resolved_tamper_fails_closed_before_grader(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    submission = _row(sessions, submission_id)
    assert submission.resolved_file_path is not None, (
        submission.status,
        submission.error_code,
        submission.error_message,
    )
    resolved = Path(submission.resolved_file_path)
    os.chmod(resolved, 0o600)
    resolved.write_bytes(resolved.read_bytes() + b"tamper")
    os.chmod(resolved, 0o400)

    assert worker_once(settings, sessions, FakeRunner(), "worker")
    failed = _row(sessions, submission_id)
    assert failed.status == "failed"
    assert failed.error_code == "quarantine_handoff_mismatch"


def test_signature_expiry_object_version_and_binding_tamper_fail_closed(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)

    expired_id = submit(client, api_key).json()["submission_id"]

    def expire(payload: dict[str, Any]) -> None:
        payload["issued_at"] = "2020-01-01T00:00:00Z"
        payload["expires_at"] = "2020-01-01T00:01:00Z"

    _resign(sessions, settings, expired_id, expire)
    assert worker_once(settings, sessions, FakeRunner(), "worker")
    assert _row(sessions, expired_id).error_code == "quarantine_handoff_mismatch"

    version_id = submit(client, api_key).json()["submission_id"]
    with sessions() as session:
        versioned = session.scalar(select(Submission).where(Submission.id == version_id))
        assert versioned is not None
        versioned.resolved_object_version = new_object_version()
        session.commit()
    assert worker_once(settings, sessions, FakeRunner(), "worker")
    assert _row(sessions, version_id).error_code == "quarantine_handoff_mismatch"

    binding_id = submit(client, api_key).json()["submission_id"]

    def substitute_slot(payload: dict[str, Any]) -> None:
        payload["campaign_slot"] = 3 if payload["campaign_slot"] != 3 else 2

    _resign(sessions, settings, binding_id, substitute_slot)
    assert worker_once(settings, sessions, FakeRunner(), "worker")
    assert _row(sessions, binding_id).error_code == "quarantine_handoff_mismatch"


def test_verdict_replay_is_database_rejected(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    with sessions() as session:
        submission = session.scalar(select(Submission).where(Submission.id == submission_id))
        assert submission is not None
        verify_and_consume_handoff(session, submission, settings, "worker-one")
        with pytest.raises(QuarantineHandoffError, match="already been consumed"):
            verify_and_consume_handoff(session, submission, settings, "worker-two")


def test_verdict_cas_rejects_active_lease_stale_generation_and_consumed_replay(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    now = datetime.now(UTC)
    with sessions() as session:
        verdict = session.scalar(
            select(QuarantineVerdictUse).where(QuarantineVerdictUse.submission_id == submission_id)
        )
        assert verdict is not None
        generation = lease_verdict(
            session,
            verdict_id=verdict.verdict_id,
            submission_id=submission_id,
            worker_id="worker-one",
            lease_seconds=10,
            now=now,
        )
        assert generation == 1
        with pytest.raises(QuarantineHandoffError, match="active lease"):
            lease_verdict(
                session,
                verdict_id=verdict.verdict_id,
                submission_id=submission_id,
                worker_id="worker-two",
                lease_seconds=10,
                now=now + timedelta(seconds=1),
            )
        with pytest.raises(QuarantineHandoffError, match="expired, stale"):
            consume_verdict(
                session,
                verdict_id=verdict.verdict_id,
                submission_id=submission_id,
                worker_id="worker-one",
                generation=0,
                now=now + timedelta(seconds=1),
            )
        consume_verdict(
            session,
            verdict_id=verdict.verdict_id,
            submission_id=submission_id,
            worker_id="worker-one",
            generation=generation,
            now=now + timedelta(seconds=1),
        )
        with pytest.raises(QuarantineHandoffError, match="already been consumed"):
            lease_verdict(
                session,
                verdict_id=verdict.verdict_id,
                submission_id=submission_id,
                worker_id="worker-two",
                lease_seconds=10,
                now=now + timedelta(seconds=2),
            )


def test_expired_verdict_lease_reclaims_with_incremented_generation(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    now = datetime.now(UTC)
    with sessions() as session:
        verdict = session.scalar(
            select(QuarantineVerdictUse).where(QuarantineVerdictUse.submission_id == submission_id)
        )
        assert verdict is not None
        first_generation = lease_verdict(
            session,
            verdict_id=verdict.verdict_id,
            submission_id=submission_id,
            worker_id="worker-one",
            lease_seconds=10,
            now=now,
        )
        second_generation = lease_verdict(
            session,
            verdict_id=verdict.verdict_id,
            submission_id=submission_id,
            worker_id="worker-two",
            lease_seconds=10,
            now=now + timedelta(seconds=11),
        )
        assert first_generation == 1
        assert second_generation == 2
        with pytest.raises(QuarantineHandoffError, match="expired, stale"):
            consume_verdict(
                session,
                verdict_id=verdict.verdict_id,
                submission_id=submission_id,
                worker_id="worker-one",
                generation=first_generation,
                now=now + timedelta(seconds=12),
            )
        consume_verdict(
            session,
            verdict_id=verdict.verdict_id,
            submission_id=submission_id,
            worker_id="worker-two",
            generation=second_generation,
            now=now + timedelta(seconds=12),
        )


def test_verdict_lease_rejects_unissued_and_invalid_lifecycle_states(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session, pytest.raises(QuarantineHandoffError, match="not issued"):
        lease_verdict(
            session,
            verdict_id="missing",
            submission_id="missing",
            worker_id="worker",
            lease_seconds=10,
        )

    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    with sessions() as session:
        verdict = session.scalar(
            select(QuarantineVerdictUse).where(QuarantineVerdictUse.submission_id == submission_id)
        )
        assert verdict is not None
        verdict.state = "corrupt"
        session.commit()
        with pytest.raises(QuarantineHandoffError, match="invalid lifecycle state"):
            lease_verdict(
                session,
                verdict_id=verdict.verdict_id,
                submission_id=submission_id,
                worker_id="worker",
                lease_seconds=10,
            )


def test_retry_after_consumption_requires_fresh_quarantine_verdict(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    with sessions() as session:
        submission = claim_next_submission(session, settings, "crashed-worker")
        assert submission is not None
        assert submission.id == submission_id
        verify_and_consume_handoff(session, submission, settings, "crashed-worker")
        submission.grading_started_at = datetime.now(UTC) - timedelta(
            seconds=settings.stale_job_seconds + 1
        )
        session.commit()
        assert recover_stale_jobs(session, settings) == 1
        session.refresh(submission)
        assert submission.status == "quarantining"
        assert submission.quarantine_envelope_json is None
        assert submission.resolved_object_version is None

    assert quarantine_once(
        settings,
        sessions,
        InsecureInProcessQuarantineRunner(settings),
        "replacement-quarantine",
    )
    with sessions() as session:
        verdicts = list(
            session.scalars(
                select(QuarantineVerdictUse).where(
                    QuarantineVerdictUse.submission_id == submission_id
                )
            )
        )
        assert sorted(verdict.state for verdict in verdicts) == ["consumed", "issued"]
        submission = session.get(Submission, submission_id)
        assert submission is not None
        assert submission.status == "queued"


def test_unknown_revoked_key_signature_and_exact_binding_are_rejected(settings: Settings) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    private_key = load_private_key(settings.quarantine_signing_private_key)
    binding = ObjectBinding(new_object_version(), f"sha256:{'a' * 64}", 12)
    resolved = ObjectBinding(new_object_version(), f"sha256:{'b' * 64}", 13)
    profiles = {
        "canonical_package_hash_profile_sha256": (
            settings.active_canonical_package_hash_profile_sha256
        ),
        "mce_profile_sha256": settings.active_mce_profile_sha256,
        "quarantine_profile_sha256": settings.active_quarantine_profile_sha256,
        "schema_bundle_sha256": settings.active_schema_bundle_sha256,
        "schema_root_map_sha256": settings.active_schema_root_map_sha256,
    }
    payload = build_payload(
        verdict_id="one-use",
        key_id=settings.quarantine_signing_key_id,
        outcome="accepted",
        reason="",
        original=binding,
        resolved=resolved,
        submission_id="submission",
        campaign_id="campaign",
        campaign_slot=1,
        quarantine_profile_sha256=profiles["quarantine_profile_sha256"],
        mce_profile_sha256=profiles["mce_profile_sha256"],
        schema_bundle_sha256=profiles["schema_bundle_sha256"],
        schema_root_map_sha256=profiles["schema_root_map_sha256"],
        canonical_package_hash_profile_sha256=profiles["canonical_package_hash_profile_sha256"],
        canonical_package_hash_v1=f"sha256:{'c' * 64}",
        gold_duplicate_check={
            "byte_match": False,
            "canonical_package_match": False,
            "decision": "clear",
        },
        schema_validation={"performed": True, "valid": True, "violations": []},
        run_kind="submission",
        control_authorization_sha256=None,
        control_authorization_object_version=None,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    envelope = sign_payload(payload, private_key)
    keys = load_verification_keys(settings.quarantine_verification_keys_json)
    assert verify_envelope(envelope, keys, now=now) == payload

    tampered = dict(envelope)
    tampered["signature"] = "A" + str(tampered["signature"])[1:]
    with pytest.raises(QuarantineHandoffError, match="signature is invalid"):
        verify_envelope(tampered, keys, now=now)

    unknown_payload = dict(payload)
    unknown_payload["key_id"] = "unknown"
    with pytest.raises(QuarantineHandoffError, match="key is unknown"):
        verify_envelope(sign_payload(unknown_payload, private_key), keys, now=now)

    key_document = json.loads(settings.quarantine_verification_keys_json)
    key_document[settings.quarantine_signing_key_id]["revoked_at"] = (
        (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    )
    revoked = load_verification_keys(json.dumps(key_document))
    with pytest.raises(QuarantineHandoffError, match="inactive or revoked"):
        verify_envelope(envelope, revoked, now=now)

    with pytest.raises(QuarantineHandoffError, match="campaign_slot"):
        require_binding(
            payload,
            original=binding,
            resolved=resolved,
            submission_id="submission",
            campaign_id="campaign",
            campaign_slot=2,
            expected_profiles=profiles,
        )


def test_malformed_handoff_primitives_fail_closed(settings: Settings) -> None:
    with pytest.raises(QuarantineHandoffError, match="Original object binding is missing"):
        QuarantineJobBinding.from_dict({})
    with pytest.raises(QuarantineHandoffError, match="binding is malformed"):
        QuarantineJobBinding.from_dict({"original": {}})
    with pytest.raises(QuarantineHandoffError, match="not JCS canonicalizable"):
        jcs_bytes({"non_finite": float("nan")})
    with pytest.raises(QuarantineHandoffError, match="private key"):
        load_private_key("not-base64")
    with pytest.raises(QuarantineHandoffError, match="public key"):
        load_public_key("not-base64")
    with pytest.raises(QuarantineHandoffError, match="UTC timestamp"):
        parse_utc("not-utc", "issued_at")
    with pytest.raises(QuarantineHandoffError, match="is invalid"):
        parse_utc("not-a-dateZ", "issued_at")
    with pytest.raises(QuarantineHandoffError, match="JSON is invalid"):
        load_verification_keys("{")
    with pytest.raises(QuarantineHandoffError, match="No quarantine verification keys"):
        load_verification_keys("{}")
    with pytest.raises(QuarantineHandoffError, match="record is malformed"):
        load_verification_keys('{"": {}}')
    with pytest.raises(QuarantineHandoffError, match="Public key is missing"):
        load_verification_keys('{"missing-public": {}}')

    now = datetime.now(UTC).replace(microsecond=0)
    original = ObjectBinding(new_object_version(), f"sha256:{'a' * 64}", 12)
    resolved = ObjectBinding(new_object_version(), f"sha256:{'b' * 64}", 13)
    common = {
        "verdict_id": "malformed-test",
        "key_id": settings.quarantine_signing_key_id,
        "outcome": "accepted",
        "reason": "",
        "original": original,
        "resolved": resolved,
        "submission_id": "submission",
        "campaign_id": "campaign",
        "campaign_slot": 1,
        "quarantine_profile_sha256": settings.active_quarantine_profile_sha256,
        "mce_profile_sha256": settings.active_mce_profile_sha256,
        "schema_bundle_sha256": settings.active_schema_bundle_sha256,
        "schema_root_map_sha256": settings.active_schema_root_map_sha256,
        "canonical_package_hash_profile_sha256": (
            settings.active_canonical_package_hash_profile_sha256
        ),
        "canonical_package_hash_v1": f"sha256:{'c' * 64}",
        "gold_duplicate_check": {"decision": "clear"},
        "schema_validation": {"performed": True, "valid": True},
        "run_kind": "submission",
        "control_authorization_sha256": None,
        "control_authorization_object_version": None,
    }
    with pytest.raises(QuarantineHandoffError, match="expiry must follow"):
        build_payload(**common, issued_at=now, expires_at=now)  # type: ignore[arg-type]

    payload = build_payload(
        **common,  # type: ignore[arg-type]
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    private_key = load_private_key(settings.quarantine_signing_private_key)
    keys = load_verification_keys(settings.quarantine_verification_keys_json)
    with pytest.raises(QuarantineHandoffError, match="envelope is missing"):
        verify_envelope(None, keys, now=now)
    with pytest.raises(QuarantineHandoffError, match="algorithm is invalid"):
        verify_envelope({"signature_algorithm": "RSA"}, keys, now=now)
    with pytest.raises(QuarantineHandoffError, match="payload is missing"):
        verify_envelope({"signature_algorithm": "Ed25519"}, keys, now=now)
    unsupported = dict(payload)
    unsupported["schema_version"] = "2.0"
    with pytest.raises(QuarantineHandoffError, match="schema version is unsupported"):
        verify_envelope(sign_payload(unsupported, private_key), keys, now=now)
    backwards = dict(payload)
    backwards["issued_at"] = (now + timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    backwards["expires_at"] = (now + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    with pytest.raises(QuarantineHandoffError, match="expiry is invalid"):
        verify_envelope(sign_payload(backwards, private_key), keys, now=now)
    unsigned = sign_payload(payload, private_key)
    unsigned.pop("signature")
    with pytest.raises(QuarantineHandoffError, match="signature is missing"):
        verify_envelope(unsigned, keys, now=now)
    missing_id = dict(payload)
    missing_id["verdict_id"] = ""
    with pytest.raises(QuarantineHandoffError, match="verdict_id"):
        require_binding(
            missing_id,
            original=original,
            resolved=resolved,
            submission_id="submission",
            campaign_id="campaign",
            campaign_slot=1,
            expected_profiles=payload["profiles"],
        )


def test_production_docker_quarantine_command_is_constrained(
    settings: Settings,
    tmp_path: Path,
) -> None:
    pinned = settings.model_copy(
        update={
            "quarantine_image_digest": "sha256:image",
            "storage_path": tmp_path / "data",
        }
    )
    original = tmp_path / "original.pptx"
    original.write_bytes(make_pptx())
    runner = RecordingDockerQuarantineRunner(pinned)
    runner.assert_ready()
    result = runner.inspect(
        original_path=original,
        binding=QuarantineJobBinding(
            submission_id="00000000-0000-0000-0000-000000000001",
            campaign_id="00000000-0000-0000-0000-000000000002",
            campaign_slot=1,
            tier=1,
            original=ObjectBinding(new_object_version(), f"sha256:{'a' * 64}", 1),
            resolved_object_version=new_object_version(),
        ),
    )
    assert result.envelope == {"sandbox": "ok"}
    command = next(args for args in runner.commands if args[:2] == ["docker", "run"])
    for required in (
        "--network",
        "none",
        "--platform",
        "linux/amd64",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "--memory",
        "--cpus",
        "--user",
    ):
        assert required in command
    assert "target=/input/original.pptx,readonly" in " ".join(command)
    for real_time_override in (
        "LD_PRELOAD=",
        "FAKETIME=",
        "FAKETIME_DONT_FAKE_MONOTONIC=",
        "FAKETIME_NO_CACHE=",
    ):
        assert real_time_override in command
    result.cleanup()

    mismatch = RecordingDockerQuarantineRunner(pinned, "sha256:other")
    with pytest.raises(QuarantineRunnerError, match="RepoDigest does not match"):
        mismatch.assert_ready()


def test_quarantine_runner_rejects_malformed_image_identity(settings: Settings) -> None:
    with pytest.raises(QuarantineRunnerError, match="identity is malformed"):
        QuarantineIdentityRunner(settings, {}).assert_ready()


def test_quarantine_runner_rejects_ambiguous_unpinned_repodigests(
    settings: Settings,
) -> None:
    identity = {
        "id": "sha256:config",
        "os": "linux",
        "architecture": "amd64",
        "repo_digests": [
            f"one/quarantine@sha256:{'a' * 64}",
            f"two/quarantine@sha256:{'b' * 64}",
        ],
    }
    with pytest.raises(QuarantineRunnerError, match="ambiguous"):
        QuarantineIdentityRunner(settings, identity).assert_ready()


def test_development_quarantine_runner_can_fall_back_to_config_digest(
    settings: Settings,
) -> None:
    identity = {
        "id": f"sha256:{'a' * 64}",
        "os": "linux",
        "architecture": "amd64",
        "repo_digests": None,
    }
    assert QuarantineIdentityRunner(settings, identity)._image_hash() == f"sha256:{'a' * 64}"
