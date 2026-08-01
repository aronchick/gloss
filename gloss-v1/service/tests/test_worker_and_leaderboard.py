from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from gloss_service import worker
from gloss_service.config import Settings
from gloss_service.models import Submission
from gloss_service.runner import (
    ArtifactFile,
    GradeOutcome,
    HostedArtifactBinding,
    ScoringCohortBinding,
)
from gloss_service.worker import worker_once

from .conftest import (
    ENVIRONMENT_HASH,
    GRADER_SOURCE_HASH,
    MANIFEST_HASH,
    create_campaign,
    create_model_revision,
    create_org,
    metadata,
    register_generation_profile,
    submit,
)


class FakeRunner:
    def __init__(self, score: float = 0.875, *, eligible: bool = True) -> None:
        self.score = score
        self.eligible = eligible
        self.seen_paths: list[Path] = []

    def grade(
        self,
        submission_path: Path,
        tier: int,
        submission_id: str,
        cohort: ScoringCohortBinding,
        artifact: HostedArtifactBinding,
    ) -> GradeOutcome:
        self.seen_paths.append(submission_path)
        return GradeOutcome(
            report={
                "benchmark_version": "gloss-v1.0.0",
                "grader_version": "grader-test-sha",
                "environment_hash": "overridden-by-service",
                "scoring_cohort_id": cohort.scoring_cohort_id,
                "scoring_manifest_sha256": cohort.scoring_manifest_sha256,
                "grader_source_tree_sha256": cohort.grader_source_tree_sha256,
                "environment_attestation_sha256": cohort.environment_attestation_sha256,
                "environment_attestation": {},
                "grader_package_sha256": f"sha256:{'a' * 64}",
                "oci_image_digest": "sha256:image",
                "prompt_bundle_sha256": f"sha256:{'b' * 64}",
                "scored_assertion_inventory_sha256": f"sha256:{'c' * 64}",
                "checklist_bundle_sha256": f"sha256:{'d' * 64}",
                "schema_bundle_sha256": artifact.schema_bundle_sha256,
                "schema_root_map_sha256": artifact.schema_root_map_sha256,
                "mce_profile_sha256": artifact.mce_profile_sha256,
                "asset_manifest_sha256": "sha256:assets",
                "font_manifest_sha256": "sha256:fonts",
                "grading_mode": "hosted",
                "run_kind": "submission",
                "canonical_package_hash_profile_sha256": (
                    artifact.canonical_package_hash_profile_sha256
                ),
                "canonical_package_hash_v1": artifact.canonical_package_hash_v1,
                "gold_duplicate_check": artifact.gold_duplicate_check,
                "generation_seed": artifact.generation_seed,
                "submission_id": artifact.submission_id,
                "campaign_id": artifact.campaign_id,
                "robustness_group_id": artifact.robustness_group_id,
                "campaign_slot": artifact.campaign_slot,
                "submitter_id": artifact.submitter_id,
                "model_key": artifact.model_key,
                "model_revision_key": artifact.model_revision_key,
                "targeted_tier": tier,
                "prompt_variant": artifact.prompt_variant,
                "assistance_class": artifact.assistance_class,
                "generation_profile_sha256": artifact.generation_profile_sha256,
                "submission_sha256": artifact.submission_sha256,
                "mce_resolved_package_sha256": artifact.mce_resolved_package_sha256,
                "gold_submission_sha256": f"sha256:{'8' * 64}",
                "gold_mce_resolved_package_sha256": f"sha256:{'e' * 64}",
                "gold_canonical_package_hash_v1": f"sha256:{'9' * 64}",
                "attested_metrics": artifact.attested_metrics,
                "attestation": artifact.attestation,
                "submission": submission_path.name,
                "schema_validation_performed": artifact.schema_validation_performed,
                "schema_valid": artifact.schema_valid,
                "verification_complete": True,
                "scoring_completed": True,
                "repair_triggered": False,
                "grading_duration_seconds": 1.25,
                "fidelity_score": self.score,
                "campaign_contribution": self.score if self.eligible else 0.0,
                "passed_items": 70,
                "total_items": 80,
                "deck_passed": False,
                "eligible": self.eligible,
                "tier_scores": {f"level_{tier}": {"fidelity_score": self.score}},
                "verified_metrics": {
                    "submission_file_size_bytes": submission_path.stat().st_size,
                    "grading_duration_seconds": 1.25,
                    "schema_valid": True,
                },
                "anti_cheat_flags": [],
                "slides": [],
                "deck_items": [],
            },
            provenance={
                "docker_image_hash": "sha256:image",
                "oci_image_digest": "sha256:image",
                "libreoffice_version": "24.2.7.2",
                "font_bundle_hash": "sha256:fonts",
                "font_manifest_sha256": "sha256:fonts",
                "asset_manifest_hash": "sha256:assets",
                "asset_manifest_sha256": "sha256:assets",
                "environment_hash": ENVIRONMENT_HASH,
                "environment_attestation_sha256": ENVIRONMENT_HASH,
                "scoring_manifest_sha256": MANIFEST_HASH,
                "grader_source_tree_sha256": GRADER_SOURCE_HASH,
                "grader_package_sha256": f"sha256:{'a' * 64}",
                "prompt_bundle_sha256": f"sha256:{'b' * 64}",
                "scored_assertion_inventory_sha256": f"sha256:{'c' * 64}",
                "checklist_bundle_sha256": f"sha256:{'d' * 64}",
                "schema_bundle_sha256": artifact.schema_bundle_sha256,
                "schema_root_map_sha256": artifact.schema_root_map_sha256,
                "mce_profile_sha256": artifact.mce_profile_sha256,
                "gold_submission_sha256": f"sha256:{'8' * 64}",
                "gold_mce_resolved_package_sha256": f"sha256:{'e' * 64}",
                "gold_canonical_package_hash_v1": f"sha256:{'9' * 64}",
            },
        )


class ArtifactRunner(FakeRunner):
    def grade(
        self,
        submission_path: Path,
        tier: int,
        submission_id: str,
        cohort: ScoringCohortBinding,
        artifact: HostedArtifactBinding,
    ) -> GradeOutcome:
        outcome = super().grade(submission_path, tier, submission_id, cohort, artifact)
        artifact_dir = submission_path.parents[4] / "artifacts" / submission_id
        artifact_dir.mkdir(parents=True)
        artifact_path = artifact_dir / "diff-slide-01.png"
        artifact_path.write_bytes(b"\x89PNG\r\n\x1a\nprivate-diff")
        return GradeOutcome(
            outcome.report,
            outcome.provenance,
            (
                ArtifactFile(
                    name=artifact_path.name,
                    path=artifact_path,
                    size_bytes=artifact_path.stat().st_size,
                    sha256="7c7c2c71743e6442f8a1679af79950ed1ef94d9d7eff5aa7feaed28cf3f319d1",
                ),
            ),
        )


class SchemaDiagnosticRunner(FakeRunner):
    def grade(
        self,
        submission_path: Path,
        tier: int,
        submission_id: str,
        cohort: ScoringCohortBinding,
        artifact: HostedArtifactBinding,
    ) -> GradeOutcome:
        assert artifact.schema_validation_performed is True
        assert artifact.schema_valid is False
        assert artifact.schema_violations == ("schema-invalid-test",)
        outcome = super().grade(submission_path, tier, submission_id, cohort, artifact)
        report = {
            **outcome.report,
            "schema_valid": False,
            "schema_validation_performed": True,
            "visual_verification_performed": False,
            "verification_complete": False,
            "scoring_completed": False,
            "fidelity_score": None,
            "campaign_contribution": 0.0,
            "passed_items": 0,
            "total_items": 0,
            "deck_passed": False,
            "eligible": False,
            "tier_scores": {"level_1": None, "level_2": None, "level_3": None},
            "disqualification_state": "completed_ineligible",
            "ineligibility_reasons": ["schema_validation_failed"],
            "schema_violations": [{"code": "schema_invalid_test"}],
        }
        return GradeOutcome(report, outcome.provenance)


class TamperedReportRunner(FakeRunner):
    def __init__(self, tamper: str) -> None:
        super().__init__()
        self.tamper = tamper

    def grade(
        self,
        submission_path: Path,
        tier: int,
        submission_id: str,
        cohort: ScoringCohortBinding,
        artifact: HostedArtifactBinding,
    ) -> GradeOutcome:
        outcome = super().grade(submission_path, tier, submission_id, cohort, artifact)
        if self.tamper == "binding":
            outcome.report["campaign_id"] = "00000000-0000-0000-0000-000000000000"
        elif self.tamper == "missing_release":
            outcome.report.pop("grader_package_sha256")
        elif self.tamper == "release_mismatch":
            outcome.report["grader_package_sha256"] = f"sha256:{'f' * 64}"
        else:
            outcome.report["environment_attestation"] = {"tampered": True}
        return outcome


def test_worker_grades_only_the_resolved_package(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    with sessions() as session:
        submission = session.scalar(select(Submission).where(Submission.id == submission_id))
        assert submission is not None
        original_path = Path(submission.file_path)
        assert submission.resolved_file_path is not None
        resolved_path = Path(submission.resolved_file_path)

    runner = FakeRunner()
    assert worker_once(settings, sessions, runner, "resolved-only-worker")
    assert runner.seen_paths == [resolved_path]
    assert original_path not in runner.seen_paths


def test_production_worker_does_not_claim_work_without_a_current_canary(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client, "Canary blocked worker")
    submission_id = submit(client, api_key).json()["submission_id"]
    runner = FakeRunner()
    production = settings.model_copy(update={"app_env": "production"})

    assert worker_once(production, sessions, runner, "canary-blocked-worker") is False
    assert runner.seen_paths == []
    with sessions() as session:
        submission = session.get(Submission, submission_id)
        assert submission is not None
        assert submission.status == "queued"
        assert submission.worker_id is None


def test_schema_invalid_diagnostic_report_occupies_zeroed_slot(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, api_key = create_org(client, "Schema diagnostic lab")
    submission_id = submit(client, api_key).json()["submission_id"]
    verify_handoff = worker.verify_and_consume_handoff

    def diagnostic_handoff(
        session: Session,
        submission: Submission,
        runtime_settings: Settings,
        worker_id: str,
    ) -> tuple[Path, dict[str, object]]:
        resolved_path, handoff = verify_handoff(session, submission, runtime_settings, worker_id)
        submission.schema_validation_json = {
            "performed": True,
            "valid": False,
            "violations": ["schema-invalid-test"],
        }
        return resolved_path, handoff

    monkeypatch.setattr(worker, "verify_and_consume_handoff", diagnostic_handoff)
    assert worker_once(settings, sessions, SchemaDiagnosticRunner(), "diagnostic-worker")

    status = client.get(f"/v1/submissions/{submission_id}", headers={"X-API-Key": api_key})
    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] == "completed"
    assert payload["campaign_slot"] == 1
    assert payload["result"]["fidelity_score"] is None
    assert payload["result"]["campaign_score"] == 0.0
    assert payload["result"]["eligible"] is False

    ledger = client.get("/v1/leaderboard/runs").json()
    row = next(run for run in ledger["runs"] if run["submission_id"] == submission_id)
    assert row["fidelity_score"] is None
    assert row["campaign_score"] == 0.0
    assert row["eligible"] is False


def test_unperformed_schema_result_fails_before_report_and_releases_slot(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, api_key = create_org(client, "Unperformed schema lab")
    submission_id = submit(client, api_key).json()["submission_id"]
    verify_handoff = worker.verify_and_consume_handoff

    def unperformed_handoff(
        session: Session,
        submission: Submission,
        runtime_settings: Settings,
        worker_id: str,
    ) -> tuple[Path, dict[str, object]]:
        resolved_path, handoff = verify_handoff(session, submission, runtime_settings, worker_id)
        submission.schema_validation_json = {
            "performed": False,
            "valid": False,
            "violations": [],
        }
        return resolved_path, handoff

    class RunnerMustNotStart(FakeRunner):
        def grade(
            self,
            submission_path: Path,
            tier: int,
            submission_id: str,
            cohort: ScoringCohortBinding,
            artifact: HostedArtifactBinding,
        ) -> GradeOutcome:
            raise AssertionError("grader must not start for an unperformed schema result")

    monkeypatch.setattr(worker, "verify_and_consume_handoff", unperformed_handoff)
    assert worker_once(settings, sessions, RunnerMustNotStart(), "unperformed-worker")

    status = client.get(f"/v1/submissions/{submission_id}", headers={"X-API-Key": api_key}).json()
    assert status["status"] == "failed"
    assert status["campaign_slot"] is None
    assert status["error"]["code"] == "quarantine_handoff_mismatch"


@pytest.mark.parametrize(
    "tamper",
    ["binding", "missing_release", "release_mismatch", "environment_attestation"],
)
def test_worker_rejects_report_context_tampering(
    tamper: str,
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client, f"Tampered report {tamper}")
    submission_id = submit(client, api_key).json()["submission_id"]
    assert worker_once(settings, sessions, TamperedReportRunner(tamper), "tamper-worker")

    status = client.get(f"/v1/submissions/{submission_id}", headers={"X-API-Key": api_key}).json()
    assert status["status"] == "failed"
    assert status["campaign_slot"] is None
    assert status["error"]["code"] == "grading_failed"


def test_worker_completes_private_report_then_publishes(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    accepted = submit(client, api_key)
    submission_id = accepted.json()["submission_id"]
    assert worker_once(settings, sessions, FakeRunner(), "test-worker")

    status = client.get(
        f"/v1/submissions/{submission_id}", headers={"Authorization": f"Bearer {api_key}"}
    )
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert status.json()["result"]["environment_hash"] == ENVIRONMENT_HASH
    assert status.json()["result"]["verification_scope"] == "artifact_conformance"
    assert (
        status.json()["result"]["verification_label"]
        == "grading-verified artifact score; generation-attested"
    )
    assert client.get(f"/v1/submissions/{submission_id}/report").status_code == 404
    private = client.get(
        f"/v1/submissions/{submission_id}/report",
        headers={"X-API-Key": api_key},
    )
    assert private.status_code == 200
    assert private.json()["environment_hash"] == ENVIRONMENT_HASH

    leaderboard = client.get("/v1/leaderboard?view=detail").json()
    assert leaderboard["entries"][0]["provisional"] is True
    assert leaderboard["entries"][0]["aggregate_score"] is None
    assert leaderboard["entries"][0]["environment_attestation_sha256"] == ENVIRONMENT_HASH
    assert leaderboard["entries"][0]["runs"][0]["submission_id"] == submission_id
    run_ledger = client.get("/v1/leaderboard/runs").json()
    public_run = run_ledger["runs"][0]
    assert public_run["campaign_slot"] == 1
    assert public_run["campaign_score"] == 0.875
    assert public_run["grading_mode"] == "hosted"
    assert public_run["run_kind"] == "submission"
    assert public_run["submission_sha256"].startswith("sha256:")
    assert public_run["gold_duplicate_check"] == "clear"
    assert public_run["grader_package_sha256"] == f"sha256:{'a' * 64}"
    assert public_run["environment_attestation"] == {}
    assert public_run["report_sha256"].startswith("sha256:")
    assert client.get("/v1/leaderboard/history").json()["snapshots"]

    published = client.post(
        f"/v1/submissions/{submission_id}/publish-report",
        headers={"X-API-Key": api_key},
    )
    assert published.status_code == 200
    assert client.get(f"/v1/submissions/{submission_id}/report").status_code == 200
    assert client.get(f"/v1/submissions/{submission_id}/report?format=html").status_code == 200


def test_robustness_requires_all_variants_and_human_assisted_is_separate(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    _, revision_key = create_model_revision(client, api_key)
    cohort = client.get("/v1/versions").json()["active_scoring_cohort_id"]
    profile_sha256 = register_generation_profile(client, api_key, revision_key)
    group = client.post(
        "/v1/robustness-groups",
        headers={"X-API-Key": api_key},
        json={
            "model_revision_key": revision_key,
            "scoring_cohort_id": cohort,
            "tier": 1,
            "assistance_class": "unassisted",
            "generation_profile_sha256": profile_sha256,
        },
    )
    assert group.status_code == 201, group.text
    campaigns = group.json()["campaigns"]
    scores = {"canonical": 0.9, "paraphrase-a": 0.82, "paraphrase-b": 0.86}
    for variant, score in scores.items():
        for _ in range(3):
            assert (
                submit(
                    client,
                    api_key,
                    submission_metadata=metadata(campaigns[variant]),
                ).status_code
                == 202
            )
            assert worker_once(settings, sessions, FakeRunner(score), "worker")
    payload = client.get("/v1/leaderboard").json()
    assert len(payload["entries"]) == 3
    assert {
        entry["tier_scores"]["level_1"]["robustness_score"] for entry in payload["entries"]
    } == {0.82}
    completed_group = client.get(
        f"/v1/robustness-groups/{group.json()['robustness_group_id']}",
        headers={"X-API-Key": api_key},
    ).json()
    assert completed_group["status"] == "completed"
    assert completed_group["robustness_score"] == 0.82

    assisted_campaign = create_campaign(client, api_key, assistance_class="human-assisted")
    for _ in range(3):
        assisted = metadata(assisted_campaign)
        assisted["attestation"]["human_intervention"] = True
        assert submit(client, api_key, submission_metadata=assisted).status_code == 202
        assert worker_once(settings, sessions, FakeRunner(0.99), "worker")
    separated = client.get("/v1/leaderboard").json()
    assert len(separated["entries"]) == 3
    assert separated["human_assisted_entries"][0]["aggregate_score"] == 0.99


def test_run_record_is_single_write(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    submission_id = submit(client, api_key).json()["submission_id"]
    assert worker_once(settings, sessions, FakeRunner(), "worker")
    with sessions() as session:
        submission = session.scalar(select(Submission).where(Submission.id == submission_id))
        assert submission is not None
        assert submission.run is not None
        assert len(submission.run.report_sha256) == 64
        assert submission.run.grading_started_at <= submission.run.grading_completed_at
        submission.run.report_sha256 = "0" * 64
        with pytest.raises(RuntimeError, match="immutable"):
            session.commit()
        session.rollback()


def test_diff_artifacts_are_private_and_tenant_scoped(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, owner_key = create_org(client, "Artifact owner")
    _, stranger_key = create_org(client, "Stranger")
    submission_id = submit(client, owner_key).json()["submission_id"]
    assert worker_once(settings, sessions, ArtifactRunner(), "worker")

    endpoint = f"/v1/submissions/{submission_id}/artifacts"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers={"X-API-Key": stranger_key}).json()["artifacts"] == []
    listing = client.get(endpoint, headers={"X-API-Key": owner_key})
    assert listing.status_code == 200
    assert listing.json()["retention_days"] == 90
    artifact = listing.json()["artifacts"][0]
    assert artifact["name"] == "diff-slide-01.png"
    download = client.get(artifact["url"], headers={"X-API-Key": owner_key})
    assert download.status_code == 200
    assert download.headers["cache-control"] == "private, no-store"
    assert download.content.startswith(b"\x89PNG")
    assert client.get(artifact["url"], headers={"X-API-Key": stranger_key}).status_code == 404
