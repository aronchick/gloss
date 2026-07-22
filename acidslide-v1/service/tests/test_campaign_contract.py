from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from acidslide_service.config import Settings
from acidslide_service.models import RobustnessGroup, Submission
from acidslide_service.runner import (
    GradeOutcome,
    GradingError,
    HostedArtifactBinding,
    ScoringCohortBinding,
)
from acidslide_service.service import scoring_cohort_id
from acidslide_service.worker import worker_once

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
from .test_worker_and_leaderboard import FakeRunner


class FailedBeforeReportRunner:
    def grade(
        self,
        _path: Path,
        _tier: int,
        _submission_id: str,
        _cohort: ScoringCohortBinding,
        _artifact: HostedArtifactBinding,
    ) -> GradeOutcome:
        raise GradingError("no report exists")


def test_scoring_cohort_id_matches_frozen_jcs_vector() -> None:
    assert (
        scoring_cohort_id(MANIFEST_HASH, GRADER_SOURCE_HASH, ENVIRONMENT_HASH)
        == "sha256:959eb774fe23dfe05c4fcee347c079e1ede96d70a0dad6c97d05fff94b890bfa"
    )


def test_identity_and_campaign_keys_are_server_issued_and_tenant_scoped(
    client: TestClient,
) -> None:
    submitter_id, owner_key = create_org(client, "Identity owner")
    _, stranger_key = create_org(client, "Identity stranger")
    model_key, revision_key = create_model_revision(
        client,
        owner_key,
        display_name="Attested model label",
        display_version="provider-2026-07-18",
    )
    cohort = client.get("/v1/versions").json()["active_scoring_cohort_id"]
    profile_sha256 = register_generation_profile(client, owner_key, revision_key)
    campaign = client.post(
        "/v1/campaigns",
        headers={"X-API-Key": owner_key},
        json={
            "model_revision_key": revision_key,
            "scoring_cohort_id": cohort,
            "tier": 2,
            "prompt_variant": "paraphrase-a",
            "assistance_class": "unassisted",
            "generation_profile_sha256": profile_sha256,
        },
    )
    assert campaign.status_code == 201, campaign.text
    body = campaign.json()
    assert body["submitter_id"] == submitter_id
    assert body["model_key"] == model_key
    assert body["model_revision_key"] == revision_key
    assert body["benchmark_version"] == "acidslide-v1.0.0"
    assert body["scoring_cohort_id"] == cohort
    assert body["slot_count"] == 3
    assert body["occupied_slots"] == 0
    assert body["status"] == "open"
    assert len(body["window_id"]) == 36

    duplicate = client.post(
        "/v1/campaigns",
        headers={"X-API-Key": owner_key},
        json={
            "model_revision_key": revision_key,
            "scoring_cohort_id": cohort,
            "tier": 2,
            "prompt_variant": "paraphrase-a",
            "assistance_class": "unassisted",
            "generation_profile_sha256": profile_sha256,
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "campaign_window_exists"
    public_campaign = client.get(
        f"/v1/campaigns/{body['campaign_id']}",
        headers={"X-API-Key": stranger_key},
    )
    assert public_campaign.status_code == 200
    assert public_campaign.json()["slots"] == []
    assert (
        client.post(
            f"/v1/models/{model_key}/revisions",
            headers={"X-API-Key": stranger_key},
            json={"display_version": "alias", "revision_note": "not owned"},
        ).status_code
        == 404
    )


def test_submission_cannot_override_campaign_binding(client: TestClient) -> None:
    _, api_key = create_org(client)
    campaign_id = create_campaign(client, api_key, tier=2, prompt_variant="paraphrase-b")
    attempted_override = metadata(campaign_id)
    attempted_override.update(
        {
            "tier": 1,
            "benchmark_version": "acidslide-v0.1.0",
            "prompt_variant": "canonical",
            "model_key": "free-text-alias",
        }
    )
    rejected = submit(client, api_key, submission_metadata=attempted_override)
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "invalid_metadata"


def test_failed_job_releases_reserved_ordinal(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    campaign_id = create_campaign(client, api_key)
    first = submit(client, api_key, submission_metadata=metadata(campaign_id))
    assert first.json()["campaign_slot"] == 1
    assert worker_once(settings, sessions, FailedBeforeReportRunner(), "failed-worker")

    failed = client.get(
        f"/v1/submissions/{first.json()['submission_id']}",
        headers={"X-API-Key": api_key},
    ).json()
    assert failed["status"] == "failed"
    assert failed["campaign_slot"] is None
    retry = submit(client, api_key, submission_metadata=metadata(campaign_id))
    assert retry.status_code == 202
    assert retry.json()["campaign_slot"] == 1


def test_ineligible_report_occupies_slot_at_zero_and_public_ledger_is_append_only(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    campaign_id = create_campaign(client, api_key)
    outcomes = [FakeRunner(0.9, eligible=False), FakeRunner(0.9), FakeRunner(0.9)]
    submission_ids: list[str] = []
    for runner in outcomes:
        accepted = submit(client, api_key, submission_metadata=metadata(campaign_id))
        submission_ids.append(accepted.json()["submission_id"])
        assert worker_once(settings, sessions, runner, "worker")

    campaign = client.get(f"/v1/campaigns/{campaign_id}", headers={"X-API-Key": api_key}).json()
    assert campaign["status"] == "completed"
    assert campaign["occupied_slots"] == 3
    assert campaign["official_score"] == 0.6
    assert [slot["campaign_score"] for slot in campaign["slots"]] == [0.0, 0.9, 0.9]
    assert campaign["verification_scope"] == "artifact_conformance"
    assert campaign["verification_label"] == "grading-verified artifact score; generation-attested"

    ledger = client.get("/v1/leaderboard/runs").json()
    rows = {row["submission_id"]: row for row in ledger["runs"]}
    assert set(rows) == set(submission_ids)
    first = rows[submission_ids[0]]
    assert first["eligible"] is False
    assert first["campaign_score"] == 0.0
    assert first["scoring_cohort_id"] == campaign["scoring_cohort_id"]
    assert first["scoring_manifest_sha256"] == MANIFEST_HASH
    assert first["grader_source_tree_sha256"] == GRADER_SOURCE_HASH
    assert first["environment_attestation_sha256"] == ENVIRONMENT_HASH
    assert "report_json" not in first
    with sessions() as session:
        persisted = session.scalar(select(Submission).where(Submission.id == submission_ids[0]))
        assert persisted is not None
        assert persisted.campaign_slot == 1
        assert persisted.run is not None


def test_robustness_group_creation_is_atomic_when_a_child_conflicts(
    client: TestClient,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client)
    _, revision_key = create_model_revision(client, api_key)
    create_campaign(client, api_key, revision_key=revision_key, prompt_variant="canonical")
    cohort = client.get("/v1/versions").json()["active_scoring_cohort_id"]
    profile_sha256 = register_generation_profile(client, api_key, revision_key)
    response = client.post(
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
    assert response.status_code == 409
    with sessions() as session:
        assert session.scalar(select(func.count(RobustnessGroup.id))) == 0
