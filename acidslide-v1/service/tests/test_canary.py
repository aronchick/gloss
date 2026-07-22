from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from acidslide_service.canary import (
    ControlAuthorizationError,
    DriftCanaryError,
    drift_canary_health,
    load_frozen_canary_bindings,
    run_drift_canary,
)
from acidslide_service.config import Settings
from acidslide_service.models import DriftCanaryAuthorizationUse, DriftCanaryRun
from acidslide_service.quarantine_handoff import encode_public_key, utc_text
from acidslide_service.runner import (
    CanaryGradeOutcome,
    ReferenceControlBinding,
    ScoringCohortBinding,
)
from acidslide_service.service import scoring_cohort_id


def _hash(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _jcs_hash(value: Any) -> str:
    return f"sha256:{hashlib.sha256(rfc8785.dumps(value)).hexdigest()}"


class FakeCanaryRunner:
    def __init__(
        self,
        png_hashes: tuple[str, ...],
        scene_graph_sha256: str,
        score_hashes: dict[int, str],
        *,
        drift: str | None = None,
    ) -> None:
        self.png_hashes = png_hashes
        self.scene_graph_sha256 = scene_graph_sha256
        self.score_hashes = score_hashes
        self.drift = drift
        self.calls: list[int] = []

    def grade_reference_control(
        self,
        resolved_gold_path: Path,
        tier: int,
        cohort: ScoringCohortBinding,
        control: ReferenceControlBinding,
    ) -> CanaryGradeOutcome:
        assert resolved_gold_path.is_file()
        assert cohort.scoring_manifest_sha256.startswith("sha256:")
        assert control.control_authorization_sha256.startswith("sha256:")
        self.calls.append(tier)
        if self.drift == "error" and tier == 2:
            raise RuntimeError("controlled canary failure")
        png_hashes = self.png_hashes
        scene_hash = self.scene_graph_sha256
        score_hash = self.score_hashes[tier]
        if self.drift == "png" and tier == 2:
            png_hashes = (_hash("drifted-page"), *png_hashes[1:])
        if self.drift == "scene" and tier == 2:
            scene_hash = _hash("drifted-scene")
        if self.drift == "score" and tier == 2:
            score_hash = _hash("drifted-score")
        report = {
            "run_kind": "reference_control",
            "verification_label": ("grading-verified reference control; no generation attribution"),
            "targeted_tier": tier,
            "score_semantic_report_sha256": score_hash,
            "fidelity_score": 1.0,
            "deck_passed": True,
            "eligible": False,
        }
        return CanaryGradeOutcome(report, png_hashes, scene_hash)


def _canary_fixture(
    settings: Settings,
    tmp_path: Path,
) -> tuple[list[dict[str, object]], tuple[str, ...], str, dict[int, str], datetime]:
    now = datetime.now(UTC).replace(microsecond=0)
    resolved_bytes = b"resolved-gold-control"
    resolved_path = tmp_path / "gold-resolved.pptx"
    resolved_path.write_bytes(resolved_bytes)
    original_sha256 = _hash("original-gold")
    resolved_sha256 = f"sha256:{hashlib.sha256(resolved_bytes).hexdigest()}"
    canonical_sha256 = _hash("canonical-gold")
    canonical_profile_sha256 = settings.active_canonical_package_hash_profile_sha256
    png_hashes = tuple(_hash(f"page-{page}") for page in range(1, 21))
    scene_hash = _hash("scene-graph")
    score_hashes = {tier: _hash(f"score-tier-{tier}") for tier in (1, 2, 3)}
    manifest = {
        "benchmark_version": settings.active_benchmark_versions[0],
        "gold": {
            "original_byte_sha256": original_sha256,
            "mce_resolved_package_sha256": resolved_sha256,
            "mce_resolved_package_size_bytes": len(resolved_bytes),
            "canonical_package_hash_profile_sha256": canonical_profile_sha256,
            "canonical_package_hash_v1": canonical_sha256,
            "scene_graph_sha256": scene_hash,
            "canonical_png_sha256s": list(png_hashes),
        },
    }
    manifest_path = tmp_path / "scoring-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_sha256 = _jcs_hash(manifest)
    evidence = {
        "evidence_id": "acidslide-gold-evidence-v1",
        "benchmark_version": settings.active_benchmark_versions[0],
        "scoring_manifest_sha256": manifest_sha256,
        "scene_graph_sha256": scene_hash,
        "profile_hashes": {
            "canonical_package_hash_profile_sha256": canonical_profile_sha256,
        },
        "reference_controls": [
            {
                "targeted_tier": tier,
                "score_semantic_report_sha256": score_hashes[tier],
            }
            for tier in (1, 2, 3)
        ],
    }
    evidence_path = tmp_path / "gold-evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    evidence_sha256 = _jcs_hash(evidence)

    settings.scoring_manifest_path = manifest_path
    settings.gold_evidence_path = evidence_path
    settings.gold_resolved_path = resolved_path
    settings.active_scoring_manifest_sha256 = manifest_sha256
    settings.active_gold_byte_sha256 = original_sha256
    settings.active_gold_mce_resolved_package_sha256 = resolved_sha256
    settings.active_gold_canonical_package_sha256 = canonical_sha256

    signing_key = Ed25519PrivateKey.generate()
    key_id = "drift-maintainer-key"
    settings.control_verification_keys_json = json.dumps(
        {
            key_id: {
                "public_key": encode_public_key(signing_key.public_key()),
                "purposes": ["drift_canary"],
                "not_before": utc_text(now - timedelta(days=1)),
                "not_after": utc_text(now + timedelta(days=1)),
                "revoked_at": None,
            }
        }
    )
    cohort_id = scoring_cohort_id(
        settings.active_scoring_manifest_sha256,
        settings.active_grader_source_tree_sha256,
        settings.active_environment_attestation_sha256,
    )
    profile_hashes = {
        "grader_source_tree_sha256": settings.active_grader_source_tree_sha256,
        "environment_attestation_sha256": settings.active_environment_attestation_sha256,
        "mce_profile_sha256": settings.active_mce_profile_sha256,
        "xsd_bundle_sha256": settings.active_schema_bundle_sha256,
        "schema_root_map_sha256": settings.active_schema_root_map_sha256,
        "canonical_package_hash_profile_sha256": canonical_profile_sha256,
        "scored_assertion_inventory_sha256": (settings.active_scored_assertion_inventory_sha256),
        "checklist_bundle_sha256": settings.active_checklist_bundle_sha256,
    }
    authorizations: list[dict[str, object]] = []
    for tier in (1, 2, 3):
        unsigned: dict[str, Any] = {
            "schema_version": "1.0",
            "authorization_id": str(uuid.uuid4()),
            "canonicalization": "RFC8785-JCS",
            "run_kind": "reference_control",
            "purpose": "drift_canary",
            "artifact_identity": {
                "original_submission_sha256": original_sha256,
                "mce_resolved_package_sha256": resolved_sha256,
                "mce_resolved_package_size_bytes": len(resolved_bytes),
                "canonical_package_hash_profile_sha256": canonical_profile_sha256,
                "canonical_package_hash_v1": canonical_sha256,
            },
            "evidence_binding": {
                "evidence_id": evidence["evidence_id"],
                "evidence_sha256": evidence_sha256,
            },
            "scoring_manifest_sha256": manifest_sha256,
            "scoring_cohort_id": cohort_id,
            "profile_hashes": profile_hashes,
            "requested_tier": tier,
            "campaign_id": None,
            "campaign_slot": None,
            "submitter_id": None,
            "model_key": None,
            "model_revision_key": None,
            "no_campaign_no_slot": True,
            "duplicate_disposition": "allow_reference_only",
            "issuer_key_id": key_id,
            "issued_at": utc_text(now - timedelta(minutes=1)),
            "expires_at": utc_text(now + timedelta(hours=1)),
            "single_use_nonce": f"canary-tier-{tier}-{'n' * 32}",
        }
        signature = signing_key.sign(rfc8785.dumps(unsigned))
        authorizations.append(
            unsigned
            | {
                "signature": {
                    "algorithm": "Ed25519",
                    "signature_base64": base64.b64encode(signature).decode(),
                }
            }
        )
    return authorizations, png_hashes, scene_hash, score_hashes, now


def test_canary_pass_is_current_and_authorizations_are_single_use(
    settings: Settings,
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    documents, png_hashes, scene_hash, score_hashes, now = _canary_fixture(settings, tmp_path)
    runner = FakeCanaryRunner(png_hashes, scene_hash, score_hashes)
    with sessions() as session:
        result = run_drift_canary(session, settings, runner, documents, now=now)
        assert result.status == "pass"
        assert runner.calls == [1, 2, 3]
        assert drift_canary_health(session, settings).ready is True
        assert session.scalar(select(func.count(DriftCanaryAuthorizationUse.authorization_id))) == 3
        with pytest.raises(ControlAuthorizationError, match="already been consumed"):
            run_drift_canary(session, settings, runner, documents, now=now)


@pytest.mark.parametrize("drift", ["png", "scene", "score"])
def test_canary_detects_every_normative_drift_surface(
    settings: Settings,
    sessions: sessionmaker[Session],
    tmp_path: Path,
    drift: str,
) -> None:
    documents, png_hashes, scene_hash, score_hashes, now = _canary_fixture(settings, tmp_path)
    runner = FakeCanaryRunner(png_hashes, scene_hash, score_hashes, drift=drift)
    with sessions() as session:
        result = run_drift_canary(session, settings, runner, documents, now=now)
        assert result.status == "drift"
        health = drift_canary_health(session, settings)
        assert health.ready is False
        assert health.code == "drift_canary_drift"


def test_tampered_authorization_fails_before_nonce_consumption(
    settings: Settings,
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    documents, png_hashes, scene_hash, score_hashes, now = _canary_fixture(settings, tmp_path)
    documents[0]["requested_tier"] = 2
    runner = FakeCanaryRunner(png_hashes, scene_hash, score_hashes)
    with sessions() as session:
        with pytest.raises(ControlAuthorizationError, match="signature is invalid"):
            run_drift_canary(session, settings, runner, documents, now=now)
        assert session.scalar(select(func.count(DriftCanaryAuthorizationUse.authorization_id))) == 0


@pytest.mark.parametrize(
    ("key_case", "message"),
    [
        ("missing", "No maintainer"),
        ("shared", "must be distinct"),
        ("unknown", "issuer key is unknown"),
        ("purpose", "not scoped"),
        ("public", "public key is missing"),
        ("revoked", "key is revoked"),
    ],
)
def test_control_key_scope_and_rotation_fail_closed(
    settings: Settings,
    sessions: sessionmaker[Session],
    tmp_path: Path,
    key_case: str,
    message: str,
) -> None:
    documents, png_hashes, scene_hash, score_hashes, now = _canary_fixture(settings, tmp_path)
    key_document = json.loads(settings.control_verification_keys_json)
    key_id = next(iter(key_document))
    if key_case == "missing":
        settings.control_verification_keys_json = "{}"
    elif key_case == "shared":
        settings.quarantine_verification_keys_json = settings.control_verification_keys_json
    elif key_case == "unknown":
        documents[0]["issuer_key_id"] = "unknown-maintainer-key"
    elif key_case == "purpose":
        key_document[key_id]["purposes"] = ["release_reference"]
        settings.control_verification_keys_json = json.dumps(key_document)
    elif key_case == "public":
        key_document[key_id].pop("public_key")
        settings.control_verification_keys_json = json.dumps(key_document)
    else:
        key_document[key_id]["revoked_at"] = utc_text(now - timedelta(seconds=30))
        settings.control_verification_keys_json = json.dumps(key_document)
    runner = FakeCanaryRunner(png_hashes, scene_hash, score_hashes)
    with sessions() as session, pytest.raises(ControlAuthorizationError, match=message):
        run_drift_canary(session, settings, runner, documents, now=now)


@pytest.mark.parametrize(
    ("binding_case", "message"),
    [
        ("manifest_digest", "manifest bytes"),
        ("benchmark", "version is not active"),
        ("active_gold", "active service state"),
        ("gold_bytes", "Resolved gold bytes"),
        ("scene", "scene graph"),
        ("controls", "reference controls are missing"),
    ],
)
def test_frozen_release_binding_mismatches_fail_closed(
    settings: Settings,
    tmp_path: Path,
    binding_case: str,
    message: str,
) -> None:
    _canary_fixture(settings, tmp_path)
    if binding_case == "manifest_digest":
        settings.active_scoring_manifest_sha256 = _hash("wrong-manifest")
    elif binding_case == "benchmark":
        settings.active_benchmark_versions = ["acidslide-v2.0.0"]
    elif binding_case == "active_gold":
        settings.active_gold_byte_sha256 = _hash("wrong-gold")
    elif binding_case == "gold_bytes":
        settings.gold_resolved_path.write_bytes(b"tampered-gold")
    else:
        evidence = json.loads(settings.gold_evidence_path.read_text(encoding="utf-8"))
        if binding_case == "scene":
            evidence["scene_graph_sha256"] = _hash("wrong-scene")
        else:
            evidence.pop("reference_controls")
        settings.gold_evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(DriftCanaryError, match=message):
        load_frozen_canary_bindings(settings)


def test_canary_runner_error_is_persisted_and_blocks_as_error(
    settings: Settings,
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    documents, png_hashes, scene_hash, score_hashes, now = _canary_fixture(settings, tmp_path)
    runner = FakeCanaryRunner(png_hashes, scene_hash, score_hashes, drift="error")
    with sessions() as session:
        result = run_drift_canary(session, settings, runner, documents, now=now)
        assert result.status == "error"
        assert result.evidence_json["error"]["code"] == "canary_execution_failed"
        assert drift_canary_health(session, settings).code == "drift_canary_error"


def test_missing_stale_and_tampered_evidence_fail_closed(
    settings: Settings,
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    documents, png_hashes, scene_hash, score_hashes, now = _canary_fixture(settings, tmp_path)
    runner = FakeCanaryRunner(png_hashes, scene_hash, score_hashes)
    with sessions() as session:
        assert drift_canary_health(session, settings).code == "drift_canary_missing"
        record = run_drift_canary(session, settings, runner, documents, now=now)
        stale = drift_canary_health(
            session,
            settings,
            now=record.completed_at + timedelta(seconds=settings.drift_canary_max_age_seconds + 1),
        )
        assert stale.code == "drift_canary_stale"
        session.execute(
            update(DriftCanaryRun)
            .where(DriftCanaryRun.id == record.id)
            .values(evidence_json={"tampered": True})
        )
        session.commit()
        assert drift_canary_health(session, settings).code == "drift_canary_tampered"
