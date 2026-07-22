from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import rfc8785
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from acidslide_service.config import Settings
from acidslide_service.main import create_app
from acidslide_service.models import DriftCanaryRun, Submission, WorkerHeartbeat
from acidslide_service.quarantine_handoff import utc_text
from acidslide_service.service import scoring_cohort_id

from .conftest import (
    create_campaign,
    create_model_revision,
    create_org,
    generation_profile,
    make_pptx,
    metadata,
    register_generation_profile,
    submit,
)


def add_passing_canary(
    session: Session,
    settings: Settings,
    *,
    completed_at: datetime | None = None,
) -> DriftCanaryRun:
    moment = (completed_at or datetime.now(UTC)).astimezone(UTC)
    run_id = "00000000-0000-0000-0000-000000000099"
    cohort_id = scoring_cohort_id(
        settings.active_scoring_manifest_sha256,
        settings.active_grader_source_tree_sha256,
        settings.active_environment_attestation_sha256,
    )
    evidence = {
        "schema_version": "1.0",
        "canary_run_id": run_id,
        "benchmark_version": settings.active_benchmark_versions[0],
        "scoring_cohort_id": cohort_id,
        "scoring_manifest_sha256": settings.active_scoring_manifest_sha256,
        "gold_evidence_sha256": f"sha256:{'f' * 64}",
        "status": "pass",
        "started_at": utc_text(moment - timedelta(minutes=1)),
        "completed_at": utc_text(moment),
        "controls": [{"targeted_tier": tier} for tier in (1, 2, 3)],
        "error": None,
    }
    record = DriftCanaryRun(
        id=run_id,
        benchmark_version=settings.active_benchmark_versions[0],
        scoring_cohort_id=cohort_id,
        scoring_manifest_sha256=settings.active_scoring_manifest_sha256,
        status="pass",
        evidence_json=evidence,
        evidence_sha256=(f"sha256:{hashlib.sha256(rfc8785.dumps(evidence)).hexdigest()}"),
        started_at=moment - timedelta(minutes=1),
        completed_at=moment,
    )
    session.add(record)
    session.commit()
    return record


def test_public_surface_and_security_headers(client: TestClient) -> None:
    homepage = client.get("/")
    assert homepage.status_code == 200
    assert "Can your model make" in homepage.text
    assert homepage.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in homepage.headers["content-security-policy"]
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    assert client.get("/v1/versions").json()["active"] == ["acidslide-v1.0.0"]
    assert client.get("/v1/leaderboard").status_code == 200


def test_admin_issues_key_once_and_auth_is_tenant_scoped(client: TestClient) -> None:
    assert client.post("/v1/admin/organizations", json={"name": "No auth"}).status_code == 401
    _, first_key = create_org(client, "First")
    _, second_key = create_org(client, "Second")
    assert first_key.startswith("asv1_")
    accepted = submit(client, first_key)
    assert accepted.status_code == 202, accepted.text
    submission_id = accepted.json()["submission_id"]
    assert accepted.json()["status_url"] == f"/v1/submissions/{submission_id}"

    own = client.get(
        f"/v1/submissions/{submission_id}",
        headers={"X-API-Key": first_key},
    )
    assert own.status_code == 200
    assert own.json()["status"] == "queued"
    assert (
        client.get(
            f"/v1/submissions/{submission_id}",
            headers={"X-API-Key": second_key},
        ).status_code
        == 404
    )
    assert client.get(f"/v1/submissions/{submission_id}").status_code == 401


def test_invalid_cohort_tier_and_quarantine_are_explicit(client: TestClient) -> None:
    _, api_key = create_org(client)
    _, revision_key = create_model_revision(client, api_key)
    profile_sha256 = register_generation_profile(client, api_key, revision_key)
    wrong_cohort = client.post(
        "/v1/campaigns",
        headers={"X-API-Key": api_key},
        json={
            "model_revision_key": revision_key,
            "scoring_cohort_id": f"sha256:{'0' * 64}",
            "tier": 1,
            "prompt_variant": "canonical",
            "assistance_class": "unassisted",
            "generation_profile_sha256": profile_sha256,
        },
    )
    assert wrong_cohort.status_code == 422
    assert wrong_cohort.json()["detail"]["code"] == "invalid_scoring_cohort"

    wrong_tier = submit(client, api_key, deck=make_pptx(slide_count=4))
    assert wrong_tier.status_code == 202
    wrong_tier_status = client.get(
        f"/v1/submissions/{wrong_tier.json()['submission_id']}",
        headers={"X-API-Key": api_key},
    ).json()
    assert wrong_tier_status["status"] == "rejected"
    assert wrong_tier_status["error"]["code"] == "invalid_tier"

    malicious = submit(client, api_key, deck=make_pptx(external_relationship=True))
    assert malicious.status_code == 202
    malicious_status = client.get(
        f"/v1/submissions/{malicious.json()['submission_id']}",
        headers={"X-API-Key": api_key},
    ).json()
    assert malicious_status["status"] == "rejected"
    assert malicious_status["error"]["code"] == "quarantine_rejected"
    assert "External OOXML" in malicious_status["error"]["message"]


def test_generation_profiles_are_server_hashed_immutable_and_scope_bound(
    client: TestClient,
) -> None:
    _, owner_key = create_org(client, "Profile owner")
    _, stranger_key = create_org(client, "Profile stranger")
    _, revision_key = create_model_revision(client, owner_key)
    payload = generation_profile(revision_key)
    request = {"model_revision_key": revision_key, "profile": payload}
    first = client.post(
        "/v1/generation-profiles",
        headers={"X-API-Key": owner_key},
        json=request,
    )
    replay = client.post(
        "/v1/generation-profiles",
        headers={"X-API-Key": owner_key},
        json=request,
    )
    assert first.status_code == replay.status_code == 201
    expected = f"sha256:{hashlib.sha256(rfc8785.dumps(payload)).hexdigest()}"
    assert first.json()["generation_profile_sha256"] == expected
    assert replay.json() == first.json()

    invalid_payload = dict(payload)
    invalid_payload["unpublished_extension"] = True
    invalid = client.post(
        "/v1/generation-profiles",
        headers={"X-API-Key": owner_key},
        json={"model_revision_key": revision_key, "profile": invalid_payload},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_generation_profile"

    _, other_revision = create_model_revision(client, owner_key, display_name="Other revision")
    cohort = client.get("/v1/versions").json()["active_scoring_cohort_id"]
    wrong_revision = client.post(
        "/v1/campaigns",
        headers={"X-API-Key": owner_key},
        json={
            "model_revision_key": other_revision,
            "scoring_cohort_id": cohort,
            "tier": 1,
            "prompt_variant": "canonical",
            "assistance_class": "unassisted",
            "generation_profile_sha256": expected,
        },
    )
    assert wrong_revision.status_code == 422
    assert wrong_revision.json()["detail"]["code"] == "invalid_generation_profile"

    _, stranger_revision = create_model_revision(client, stranger_key)
    conflicting_registration = client.post(
        "/v1/generation-profiles",
        headers={"X-API-Key": stranger_key},
        json={"model_revision_key": stranger_revision, "profile": payload},
    )
    assert conflicting_registration.status_code == 409
    assert conflicting_registration.json()["detail"]["code"] == (
        "generation_profile_scope_conflict"
    )
    cross_tenant = client.post(
        "/v1/campaigns",
        headers={"X-API-Key": stranger_key},
        json={
            "model_revision_key": stranger_revision,
            "scoring_cohort_id": cohort,
            "tier": 1,
            "prompt_variant": "canonical",
            "assistance_class": "unassisted",
            "generation_profile_sha256": expected,
        },
    )
    assert cross_tenant.status_code == 422
    assert cross_tenant.json()["detail"]["code"] == "invalid_generation_profile"


def test_unassisted_campaign_rejects_intervention_permitted_profile(
    client: TestClient,
) -> None:
    _, api_key = create_org(client)
    _, revision_key = create_model_revision(client, api_key)
    profile_sha256 = register_generation_profile(
        client,
        api_key,
        revision_key,
        human_intervention_permitted=True,
    )
    response = client.post(
        "/v1/campaigns",
        headers={"X-API-Key": api_key},
        json={
            "model_revision_key": revision_key,
            "scoring_cohort_id": client.get("/v1/versions").json()["active_scoring_cohort_id"],
            "tier": 1,
            "prompt_variant": "canonical",
            "assistance_class": "unassisted",
            "generation_profile_sha256": profile_sha256,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_assistance_class"


def test_tuple_rate_limit_has_retry_after(client: TestClient) -> None:
    _, api_key = create_org(client)
    campaign_id = create_campaign(client, api_key)
    slots = []
    for _ in range(3):
        accepted = submit(client, api_key, submission_metadata=metadata(campaign_id))
        assert accepted.status_code == 202
        slots.append(accepted.json()["campaign_slot"])
    assert slots == [1, 2, 3]
    limited = submit(client, api_key, submission_metadata=metadata(campaign_id))
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    assert limited.json()["detail"]["code"] == "rate_limited"


def test_metadata_conditional_fields_are_enforced(client: TestClient) -> None:
    _, api_key = create_org(client)
    invalid = metadata()
    invalid["attestation"]["external_resources_used"] = True
    response = submit(client, api_key, submission_metadata=invalid)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_metadata"


def test_repeated_malicious_uploads_suspend_account(client: TestClient) -> None:
    _, api_key = create_org(client)
    campaign_id = create_campaign(client, api_key)
    for attempt in range(5):
        response = submit(client, api_key, deck=make_pptx(nested_archive=True))
        assert response.status_code == 202
        if attempt == 0:
            rejected = client.get(
                f"/v1/submissions/{response.json()['submission_id']}",
                headers={"X-API-Key": api_key},
            ).json()
            assert rejected["error"]["code"] == "quarantine_rejected"
    suspended = submit(
        client,
        api_key,
        submission_metadata=metadata(campaign_id),
    )
    assert suspended.status_code == 403
    assert suspended.json()["detail"]["code"] == "account_suspended"


def test_reviewed_openapi_covers_runtime_contract(client: TestClient) -> None:
    reviewed_path = Path(__file__).parents[1] / "api-spec.yaml"
    reviewed = yaml.safe_load(reviewed_path.read_text())
    runtime = client.get("/v1/openapi.json").json()
    reviewed_paths = {f"/v1{path}" for path in reviewed["paths"]}
    runtime_contract_paths = {path for path in runtime["paths"] if path.startswith("/v1/")}
    assert runtime_contract_paths <= reviewed_paths
    assert reviewed["openapi"] == "3.1.0"


def test_metrics_can_be_bearer_protected(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "acidslide_http_requests_total" in response.text


def test_production_readiness_requires_both_worker_roles_and_metrics_token(
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    production = settings.model_copy(
        update={
            "app_env": "production",
            "metrics_bearer_token": "metrics-secret",
        }
    )
    with TestClient(create_app(production, sessions)) as production_client:
        missing = production_client.get("/health/ready")
        assert missing.status_code == 503
        assert missing.json()["detail"]["code"] == "worker_unavailable"
        assert "grading, quarantine" in missing.json()["detail"]["message"]
        assert production_client.get("/metrics").status_code == 401
        assert (
            production_client.get(
                "/metrics", headers={"Authorization": "Bearer metrics-secret"}
            ).status_code
            == 200
        )

        with sessions() as session:
            for role in ("grading", "quarantine"):
                session.add(
                    WorkerHeartbeat(
                        worker_id=f"{role}:test",
                        hostname="test",
                        process_id=1,
                        last_seen_at=datetime.now(UTC),
                    )
                )
            session.commit()
        missing_canary = production_client.get("/health/ready")
        assert missing_canary.status_code == 503
        assert missing_canary.json()["detail"]["code"] == "drift_canary_missing"
        with sessions() as session:
            add_passing_canary(session, production)
        assert production_client.get("/health/ready").json() == {"status": "ready"}
        metrics = production_client.get(
            "/metrics", headers={"Authorization": "Bearer metrics-secret"}
        )
        assert "acidslide_drift_canary_blocked 0.0" in metrics.text


def test_production_submission_is_blocked_without_a_current_canary(
    client: TestClient,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    _, api_key = create_org(client, "Canary blocked submitter")
    campaign_id = create_campaign(client, api_key)
    production = settings.model_copy(update={"app_env": "production"})
    with TestClient(create_app(production, sessions)) as production_client:
        blocked = submit(
            production_client,
            api_key,
            submission_metadata=metadata(campaign_id),
        )
    assert blocked.status_code == 503
    assert blocked.json()["detail"]["code"] == "drift_canary_missing"
    with sessions() as session:
        assert session.scalar(select(func.count(Submission.id))) == 0
