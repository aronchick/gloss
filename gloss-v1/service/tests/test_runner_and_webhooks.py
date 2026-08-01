from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import rfc8785
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from gloss_service import webhooks
from gloss_service.config import Settings
from gloss_service.models import Submission, WebhookDelivery
from gloss_service.runner import (
    DockerGradingRunner,
    GradingError,
    ReferenceControlBinding,
    RendererCrashError,
    ScoringCohortBinding,
)
from gloss_service.security import encrypt_secret
from gloss_service.service import scoring_cohort_id
from gloss_service.webhooks import (
    UnsafeWebhookURLError,
    deliver_webhook,
    validate_webhook_url,
    webhook_signature,
)

from .conftest import (
    ENVIRONMENT_HASH,
    GRADER_SOURCE_HASH,
    MANIFEST_HASH,
    create_org,
    hosted_artifact_binding,
    submit,
)


class RecordingRunner(DockerGradingRunner):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.commands: list[list[str]] = []

    def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        self.commands.append(args)
        if args[:3] == ["docker", "image", "inspect"]:
            identity = {
                "id": "sha256:config",
                "os": "linux",
                "architecture": "amd64",
                "repo_digests": ["gloss/grader@sha256:image"],
            }
            return subprocess.CompletedProcess(args, 0, json.dumps(identity), "")
        if "attest-environment" in args:
            attestation = self.settings.environment_attestation
            envelope = {
                "environment_attestation": attestation,
                "environment_attestation_sha256": (
                    f"sha256:{hashlib.sha256(rfc8785.dumps(attestation)).hexdigest()}"
                ),
            }
            return subprocess.CompletedProcess(args, 0, json.dumps(envelope), "")
        if args[:2] == ["docker", "run"]:
            report: dict[str, Any] = {
                "benchmark_version": "gloss-v1.0.0",
                "grader_version": "test",
                "fidelity_score": 0.5,
                "passed_items": 1,
                "total_items": 2,
                "deck_passed": False,
                "eligible": True,
                "tier_scores": {},
                "anti_cheat_flags": [],
            }
            return subprocess.CompletedProcess(args, 0, json.dumps(report), "")
        return subprocess.CompletedProcess(args, 0, "", "")


class ImageIdentityRunner(DockerGradingRunner):
    def __init__(self, settings: Settings, identity: object) -> None:
        super().__init__(settings)
        self.identity = identity

    def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, json.dumps(self.identity), "")


class CanaryRecordingRunner(RecordingRunner):
    def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["docker", "run"] and any(
            "GLOSS_CANARY_RESULT=" in argument for argument in args
        ):
            payload = {
                "report": {
                    "run_kind": "reference_control",
                    "score_semantic_report_sha256": f"sha256:{'a' * 64}",
                },
                "canonical_png_sha256s": [f"sha256:{page:064x}" for page in range(1, 21)],
                "scene_graph_sha256": f"sha256:{'b' * 64}",
            }
            self.commands.append(args)
            return subprocess.CompletedProcess(
                args,
                0,
                "renderer log\nGLOSS_CANARY_RESULT=" + json.dumps(payload, separators=(",", ":")),
                "",
            )
        return super()._run(args, timeout)


def test_grading_container_has_required_isolation(
    tmp_path: Path,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "deck.pptx"
    path.write_bytes(b"deck")
    cleanup: list[list[str]] = []

    def record_cleanup(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        cleanup.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", record_cleanup)
    runner = RecordingRunner(settings)
    outcome = runner.grade(
        path,
        1,
        "00000000-0000-0000-0000-000000000001",
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
        hosted_artifact_binding(),
    )
    command = next(
        args
        for args in runner.commands
        if args[:2] == ["docker", "run"]
        and "--read-only" in args
        and "attest-environment" not in args
    )
    attestation_command = next(args for args in runner.commands if "attest-environment" in args)
    for required in (
        "--network",
        "none",
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
    assert "readonly" in " ".join(command)
    assert "--network" in attestation_command
    assert "none" in attestation_command
    assert "--read-only" in attestation_command
    assert "/input/submission.pptx" not in attestation_command
    assert "from gloss.pipeline import run_resolved_pipeline" in command[-6]
    assert "from gloss.pipeline import run_pipeline" not in command[-6]
    context = json.loads(command[-2])
    assert context["grading_mode"] == "hosted"
    assert context["submission_id"] == "00000000-0000-0000-0000-000000000001"
    assert context["oci_image_digest"] == "sha256:image"
    assert json.loads(command[-1]) == {"performed": True, "valid": True, "violations": []}
    assert outcome.provenance["environment_hash"].startswith("sha256:")
    assert any(
        args[-2:] == [f"{settings.grader_uid}:{settings.grader_uid}", "/input/submission.pptx"]
        for args in runner.commands
    )
    assert any(args[:4] == ["docker", "volume", "rm", "-f"] for args in cleanup)


def test_reference_control_runner_emits_exact_canary_surfaces(
    tmp_path: Path,
    settings: Settings,
) -> None:
    path = tmp_path / "gold-resolved.pptx"
    path.write_bytes(b"resolved-gold")
    runner = CanaryRecordingRunner(settings)
    outcome = runner.grade_reference_control(
        path,
        2,
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
        ReferenceControlBinding(
            control_authorization_sha256=f"sha256:{'1' * 64}",
            original_submission_sha256=f"sha256:{'2' * 64}",
            mce_resolved_package_sha256=f"sha256:{'3' * 64}",
            canonical_package_hash_profile_sha256=f"sha256:{'4' * 64}",
            canonical_package_hash_v1=f"sha256:{'5' * 64}",
            schema_bundle_sha256=f"sha256:{'6' * 64}",
            schema_root_map_sha256=f"sha256:{'7' * 64}",
            mce_profile_sha256=f"sha256:{'8' * 64}",
        ),
    )
    assert outcome.report["run_kind"] == "reference_control"
    assert len(outcome.canonical_png_sha256s) == 20
    assert outcome.scene_graph_sha256 == f"sha256:{'b' * 64}"
    command = next(
        args
        for args in runner.commands
        if any("GLOSS_CANARY_RESULT=" in argument for argument in args)
    )
    assert command[command.index("--network") : command.index("--network") + 2] == [
        "--network",
        "none",
    ]
    assert "--read-only" in command
    assert "readonly" in " ".join(command)
    context = json.loads(command[-1])
    assert context["run_kind"] == "reference_control"
    assert context["targeted_tier"] == 2
    assert context["submission_id"] is None
    assert context["gold_duplicate_check"] == "byte_match"


def test_grading_runner_surfaces_sanitized_container_failure(
    tmp_path: Path,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingGradeRunner(RecordingRunner):
        def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
            if (
                args[:2] == ["docker", "run"]
                and "--read-only" in args
                and "attest-environment" not in args
            ):
                raise subprocess.CalledProcessError(
                    1,
                    args,
                    stderr="canonical grader canary failure",
                )
            return super()._run(args, timeout)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **_kwargs: subprocess.CompletedProcess(args, 0, "", ""),
    )
    path = tmp_path / "deck.pptx"
    path.write_bytes(b"deck")

    with pytest.raises(RendererCrashError, match="canonical grader canary failure"):
        FailingGradeRunner(settings).grade(
            path,
            1,
            "00000000-0000-0000-0000-000000000001",
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
            hosted_artifact_binding(),
        )


def test_grading_runner_rejects_runtime_attestation_tamper(
    tmp_path: Path,
    settings: Settings,
) -> None:
    class TamperedAttestationRunner(RecordingRunner):
        def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
            if "attest-environment" in args:
                envelope = {
                    "environment_attestation": {"tampered": True},
                    "environment_attestation_sha256": ENVIRONMENT_HASH,
                }
                return subprocess.CompletedProcess(args, 0, json.dumps(envelope), "")
            return super()._run(args, timeout)

    path = tmp_path / "deck.pptx"
    path.write_bytes(b"deck")
    runner = TamperedAttestationRunner(settings)
    with pytest.raises(GradingError, match="envelope hash is invalid"):
        runner.grade(
            path,
            1,
            "00000000-0000-0000-0000-000000000001",
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
            hosted_artifact_binding(),
        )


@pytest.mark.parametrize(
    ("stdout", "message"),
    [
        ("no envelope", "emitted no JSON"),
        ("{invalid", "emitted invalid JSON"),
        ("{}", "envelope is malformed"),
    ],
)
def test_runtime_attestation_rejects_malformed_container_output(
    stdout: str,
    message: str,
    settings: Settings,
) -> None:
    class EnvelopeRunner(DockerGradingRunner):
        def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args, 0, stdout, "")

    with pytest.raises(GradingError, match=message):
        EnvelopeRunner(settings)._attest_environment("sha256:image", ENVIRONMENT_HASH)


def test_runtime_attestation_binds_active_release_and_cohort(settings: Settings) -> None:
    class EnvelopeRunner(DockerGradingRunner):
        def __init__(self, runtime_settings: Settings, payload: dict[str, Any]) -> None:
            super().__init__(runtime_settings)
            self.payload = payload

        def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
            digest = f"sha256:{hashlib.sha256(rfc8785.dumps(self.payload)).hexdigest()}"
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps(
                    {
                        "environment_attestation": self.payload,
                        "environment_attestation_sha256": digest,
                    }
                ),
                "",
            )

    with pytest.raises(GradingError, match="active release"):
        EnvelopeRunner(settings, {"runtime": "different"})._attest_environment(
            "sha256:image", ENVIRONMENT_HASH
        )

    active_mismatch = settings.model_copy(
        update={"active_environment_attestation_sha256": f"sha256:{'f' * 64}"}
    )
    with pytest.raises(GradingError, match="service state"):
        EnvelopeRunner(active_mismatch, {})._attest_environment("sha256:image", ENVIRONMENT_HASH)

    with pytest.raises(GradingError, match="scoring cohort"):
        EnvelopeRunner(settings, {})._attest_environment("sha256:image", f"sha256:{'f' * 64}")


def test_runtime_attestation_surfaces_container_failure(settings: Settings) -> None:
    class FailedAttestationRunner(DockerGradingRunner):
        def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
            raise subprocess.CalledProcessError(2, args, stderr="binary hash mismatch")

    with pytest.raises(GradingError, match="binary hash mismatch"):
        FailedAttestationRunner(settings)._attest_environment("sha256:image", ENVIRONMENT_HASH)


def test_grading_runner_rejects_image_attestation_mismatch(
    tmp_path: Path,
    settings: Settings,
) -> None:
    path = tmp_path / "deck.pptx"
    path.write_bytes(b"deck")
    runner = RecordingRunner(
        settings.model_copy(
            update={
                "environment_attestation_json": json.dumps(
                    {"oci_image_digest": f"sha256:{'f' * 64}"}
                )
            }
        )
    )
    with pytest.raises(GradingError, match="environment attestation"):
        runner.grade(
            path,
            1,
            "00000000-0000-0000-0000-000000000001",
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
            hosted_artifact_binding(),
        )


def test_grading_runner_rejects_non_frozen_platform(
    tmp_path: Path,
    settings: Settings,
) -> None:
    class ArmRunner(RecordingRunner):
        def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
            if args[:3] == ["docker", "image", "inspect"]:
                identity = {
                    "id": "sha256:config",
                    "os": "linux",
                    "architecture": "arm64",
                    "repo_digests": ["gloss/grader@sha256:image"],
                }
                return subprocess.CompletedProcess(args, 0, json.dumps(identity), "")
            return super()._run(args, timeout)

    path = tmp_path / "deck.pptx"
    path.write_bytes(b"deck")
    with pytest.raises(GradingError, match="linux/amd64"):
        ArmRunner(settings).grade(
            path,
            1,
            "00000000-0000-0000-0000-000000000001",
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
            hosted_artifact_binding(),
        )


@pytest.mark.parametrize(
    "identity",
    [
        None,
        {},
        {
            "id": "sha256:config",
            "os": "linux",
            "architecture": "amd64",
            "repo_digests": ["not-a-digest"],
        },
    ],
)
def test_grading_runner_rejects_malformed_image_identity(
    identity: object,
    settings: Settings,
) -> None:
    with pytest.raises(RendererCrashError, match="identity is malformed"):
        ImageIdentityRunner(settings, identity)._image_hash()


def test_grading_runner_rejects_unavailable_and_invalid_image_inspection(
    settings: Settings,
) -> None:
    class UnavailableRunner(DockerGradingRunner):
        def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
            raise OSError("docker unavailable")

    class InvalidJSONRunner(DockerGradingRunner):
        def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args, 0, "{", "")

    with pytest.raises(RendererCrashError, match="image is unavailable"):
        UnavailableRunner(settings)._image_hash()
    with pytest.raises(RendererCrashError, match="identity is malformed"):
        InvalidJSONRunner(settings)._image_hash()


def test_grading_runner_binds_attested_platform_and_single_manifest_digest(
    settings: Settings,
) -> None:
    identity = {
        "id": "sha256:config",
        "os": "linux",
        "architecture": "amd64",
        "repo_digests": [f"gloss/grader@sha256:{'a' * 64}"],
    }
    wrong_attestation = settings.model_copy(
        update={"environment_attestation_json": json.dumps({"platform": "linux/arm64"})}
    )
    with pytest.raises(GradingError, match="platform does not match"):
        ImageIdentityRunner(wrong_attestation, identity)._image_hash()
    unpinned = settings.model_copy(update={"grader_image_digest": ""})
    assert ImageIdentityRunner(unpinned, identity)._image_hash() == f"sha256:{'a' * 64}"


def test_grading_runner_collects_only_bounded_diff_artifacts(
    tmp_path: Path,
    settings: Settings,
) -> None:
    runner = DockerGradingRunner(settings)
    valid_dir = tmp_path / "valid"
    valid_dir.mkdir()
    (valid_dir / "diff-slide-02.png").write_bytes(b"two")
    (valid_dir / "diff-slide-01.png").write_bytes(b"one")
    artifacts = runner._collect_artifacts(valid_dir)
    assert [artifact.name for artifact in artifacts] == [
        "diff-slide-01.png",
        "diff-slide-02.png",
    ]

    unsafe_dir = tmp_path / "unsafe"
    unsafe_dir.mkdir()
    (unsafe_dir / "directory").mkdir()
    with pytest.raises(GradingError, match="unsafe filesystem entry"):
        runner._collect_artifacts(unsafe_dir)

    unexpected_dir = tmp_path / "unexpected"
    unexpected_dir.mkdir()
    (unexpected_dir / "report.json").write_text("{}", encoding="utf-8")
    with pytest.raises(GradingError, match="unexpected name"):
        runner._collect_artifacts(unexpected_dir)

    large_dir = tmp_path / "large"
    large_dir.mkdir()
    with (large_dir / "diff-slide-01.png").open("wb") as stream:
        stream.truncate(50 * 1024 * 1024 + 1)
    with pytest.raises(GradingError, match="exceeds 50 MB"):
        runner._collect_artifacts(large_dir)


def test_grading_runner_requires_configured_manifest_repodigest(settings: Settings) -> None:
    identity = {
        "id": "sha256:config",
        "os": "linux",
        "architecture": "amd64",
        "repo_digests": [f"gloss/grader@sha256:{'a' * 64}"],
    }
    pinned = settings.model_copy(update={"grader_image_digest": f"sha256:{'b' * 64}"})
    with pytest.raises(GradingError, match="RepoDigest"):
        ImageIdentityRunner(pinned, identity)._image_hash()


def test_grading_runner_rejects_ambiguous_unpinned_repodigests(settings: Settings) -> None:
    identity = {
        "id": "sha256:config",
        "os": "linux",
        "architecture": "amd64",
        "repo_digests": [
            f"one/grader@sha256:{'a' * 64}",
            f"two/grader@sha256:{'b' * 64}",
        ],
    }
    with pytest.raises(GradingError, match="ambiguous"):
        ImageIdentityRunner(settings, identity)._image_hash()


def test_development_grading_runner_can_fall_back_to_config_digest(settings: Settings) -> None:
    identity = {
        "id": f"sha256:{'a' * 64}",
        "os": "linux",
        "architecture": "amd64",
        "repo_digests": None,
    }
    assert ImageIdentityRunner(settings, identity)._image_hash() == f"sha256:{'a' * 64}"


def test_webhook_signature_is_raw_body_hmac() -> None:
    assert webhook_signature(b'{"status":"completed"}', "secret") == (
        "f221b3e5be7a7967fb814487442ac97c879375c1cd8fec3fec9c4476bed3589a"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/callback",
        "https://127.0.0.1/callback",
        "https://[::1]/callback",
        "https://user:password@example.com/callback",
    ],
)
def test_webhook_rejects_unsafe_destinations(url: str) -> None:
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url(url)


def test_delivery_signs_exact_body_and_records_attempt(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    captured: dict[str, Any] = {}

    def fake_post(url: str, body: bytes, headers: dict[str, str]) -> int:
        captured.update(url=url, body=body, headers=headers)
        return 204

    monkeypatch.setattr(webhooks, "_post_pinned", fake_post)
    with sessions() as session:
        submission = session.scalar(select(Submission).where(Submission.id == submission_id))
        assert submission is not None
        submission.webhook_url = "https://hooks.example.com/gloss"
        submission.webhook_secret_encrypted = encrypt_secret("a-secret-at-least-16", settings)
        session.commit()
        payload = {"submission_id": submission.id, "status": "completed"}
        assert deliver_webhook(session, submission, payload, settings)
        delivery = session.scalar(
            select(WebhookDelivery).where(WebhookDelivery.submission_id == submission.id)
        )
        assert delivery is not None
        assert delivery.attempt == 1
        assert delivery.response_status == 204
    assert captured["headers"]["X-Gloss-Signature"] == webhook_signature(
        captured["body"], "a-secret-at-least-16"
    )
