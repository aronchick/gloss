"""Signed, immutable production drift-canary execution and health gates."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast

import rfc8785
from cryptography.exceptions import InvalidSignature
from jsonschema import Draft202012Validator, FormatChecker
from prometheus_client import Counter, Gauge
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gloss_service.config import Settings
from gloss_service.models import (
    DriftCanaryAuthorizationUse,
    DriftCanaryRun,
)
from gloss_service.quarantine_handoff import load_public_key, parse_utc, utc_text
from gloss_service.runner import (
    CanaryGradeOutcome,
    ReferenceControlBinding,
    ScoringCohortBinding,
)
from gloss_service.service import scoring_cohort_id

CANARY_RUNS = Counter(
    "gloss_drift_canary_runs_total",
    "Completed drift-canary batches",
    ("outcome",),
)
CANARY_BLOCKED = Gauge(
    "gloss_drift_canary_blocked",
    "Whether production grading is blocked by drift-canary state",
)
CANARY_LAST_COMPLETED = Gauge(
    "gloss_drift_canary_last_completed_timestamp_seconds",
    "Completion time of the latest drift-canary batch",
)


class DriftCanaryError(ValueError):
    """A drift-canary input or execution failed closed."""


class ControlAuthorizationError(DriftCanaryError):
    """A maintainer control authorization is invalid or replayed."""


class CanaryRunner(Protocol):
    def grade_reference_control(
        self,
        resolved_gold_path: Path,
        tier: int,
        cohort: ScoringCohortBinding,
        control: ReferenceControlBinding,
    ) -> CanaryGradeOutcome: ...


@dataclass(frozen=True)
class VerifiedControl:
    document: dict[str, Any]
    authorization_id: str
    authorization_sha256: str
    nonce_sha256: str
    issuer_key_id: str
    targeted_tier: int


@dataclass(frozen=True)
class FrozenCanaryBindings:
    benchmark_version: str
    scoring_manifest_sha256: str
    scoring_cohort_id: str
    gold_evidence_sha256: str
    original_gold_sha256: str
    resolved_gold_sha256: str
    resolved_gold_size_bytes: int
    canonical_package_hash_profile_sha256: str
    canonical_package_hash_v1: str
    expected_png_sha256s: tuple[str, ...]
    expected_scene_graph_sha256: str
    expected_score_sha256_by_tier: dict[int, str]
    manifest: dict[str, Any]
    gold_evidence: dict[str, Any]


@dataclass(frozen=True)
class DriftCanaryHealth:
    ready: bool
    code: str
    message: str
    run_id: str | None = None

    def detail(self) -> dict[str, str]:
        detail = {"code": self.code, "message": self.message}
        if self.run_id is not None:
            detail["canary_run_id"] = self.run_id
        return detail


def _jcs_sha256(value: Any) -> str:
    try:
        encoded = rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, rfc8785.FloatDomainError) as exc:
        raise DriftCanaryError("Canary evidence is not RFC 8785 canonicalizable") from exc
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise DriftCanaryError(f"Canary artifact is unreadable: {path}") from exc
    return f"sha256:{digest.hexdigest()}"


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DriftCanaryError(f"{label} is unreadable or invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise DriftCanaryError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _required_hash(mapping: Mapping[str, Any], field: str, label: str) -> str:
    value = mapping.get(field)
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise DriftCanaryError(f"{label} {field} is not a canonical SHA-256")
    return value


def _required_mapping(mapping: Mapping[str, Any], field: str, label: str) -> dict[str, Any]:
    value = mapping.get(field)
    if not isinstance(value, dict):
        raise DriftCanaryError(f"{label} {field} is missing or malformed")
    return cast(dict[str, Any], value)


def _resolve_schema(path: Path) -> Path:
    candidates = (
        path,
        Path.cwd() / path,
        Path(__file__).resolve().parents[2] / "schemas" / "control-handoff.schema.json",
        Path("/opt/gloss/schemas/control-handoff.schema.json"),
    )
    resolved = next((candidate for candidate in candidates if candidate.is_file()), None)
    if resolved is None:
        raise DriftCanaryError("Control-authorization schema is unavailable")
    return resolved


def load_frozen_canary_bindings(settings: Settings) -> FrozenCanaryBindings:
    """Load and cross-bind the active manifest, gold evidence, and resolved gold bytes."""
    manifest = _load_object(settings.scoring_manifest_path, "Scoring manifest")
    manifest_sha256 = _jcs_sha256(manifest)
    if manifest_sha256 != settings.active_scoring_manifest_sha256:
        raise DriftCanaryError("Scoring manifest bytes do not match the active release")
    benchmark_version = manifest.get("benchmark_version")
    if (
        not isinstance(benchmark_version, str)
        or benchmark_version not in settings.active_benchmark_versions
    ):
        raise DriftCanaryError("Scoring manifest benchmark version is not active")

    gold = _required_mapping(manifest, "gold", "Scoring manifest")
    original_sha256 = _required_hash(gold, "original_byte_sha256", "Scoring manifest gold")
    resolved_sha256 = _required_hash(gold, "mce_resolved_package_sha256", "Scoring manifest gold")
    canonical_profile_sha256 = _required_hash(
        gold,
        "canonical_package_hash_profile_sha256",
        "Scoring manifest gold",
    )
    canonical_package_sha256 = _required_hash(
        gold, "canonical_package_hash_v1", "Scoring manifest gold"
    )
    scene_graph_sha256 = _required_hash(gold, "scene_graph_sha256", "Scoring manifest gold")
    size_value = gold.get("mce_resolved_package_size_bytes")
    if not isinstance(size_value, int) or isinstance(size_value, bool) or size_value <= 0:
        raise DriftCanaryError("Scoring manifest gold resolved size is invalid")
    png_value = gold.get("canonical_png_sha256s")
    if not isinstance(png_value, list) or len(png_value) != 20:
        raise DriftCanaryError("Scoring manifest must bind exactly 20 canonical PNG hashes")
    png_hashes = tuple(
        _required_hash({"value": value}, "value", "Scoring manifest canonical PNG")
        for value in png_value
    )

    active_bindings = {
        "original gold": (original_sha256, settings.active_gold_byte_sha256),
        "resolved gold": (resolved_sha256, settings.active_gold_mce_resolved_package_sha256),
        "canonical gold": (
            canonical_package_sha256,
            settings.active_gold_canonical_package_sha256,
        ),
        "canonical-package profile": (
            canonical_profile_sha256,
            settings.active_canonical_package_hash_profile_sha256,
        ),
    }
    mismatched = [name for name, pair in active_bindings.items() if pair[0] != pair[1]]
    if mismatched:
        raise DriftCanaryError(
            "Scoring manifest does not match active service state: " + ", ".join(mismatched)
        )
    if _file_sha256(settings.gold_resolved_path) != resolved_sha256:
        raise DriftCanaryError("Resolved gold bytes do not match the scoring manifest")
    try:
        actual_size = settings.gold_resolved_path.stat().st_size
    except OSError as exc:
        raise DriftCanaryError("Resolved gold artifact is unavailable") from exc
    if actual_size != size_value:
        raise DriftCanaryError("Resolved gold size does not match the scoring manifest")

    gold_evidence = _load_object(settings.gold_evidence_path, "Gold evidence")
    gold_evidence_sha256 = _jcs_sha256(gold_evidence)
    if gold_evidence.get("benchmark_version") != benchmark_version:
        raise DriftCanaryError("Gold evidence benchmark version does not match the manifest")
    if gold_evidence.get("scoring_manifest_sha256") != manifest_sha256:
        raise DriftCanaryError("Gold evidence does not bind the active scoring manifest")
    if gold_evidence.get("scene_graph_sha256") != scene_graph_sha256:
        raise DriftCanaryError("Gold evidence scene graph does not match the scoring manifest")
    evidence_profile = _required_mapping(gold_evidence, "profile_hashes", "Gold evidence")
    if evidence_profile.get("canonical_package_hash_profile_sha256") != canonical_profile_sha256:
        raise DriftCanaryError("Gold evidence canonical-package profile is inconsistent")

    controls_value = gold_evidence.get("reference_controls")
    if not isinstance(controls_value, list):
        raise DriftCanaryError("Gold evidence reference controls are missing")
    score_hashes: dict[int, str] = {}
    for item in controls_value:
        if not isinstance(item, dict):
            raise DriftCanaryError("Gold evidence reference control is malformed")
        tier = item.get("targeted_tier")
        if not isinstance(tier, int) or isinstance(tier, bool) or tier not in {1, 2, 3}:
            raise DriftCanaryError("Gold evidence reference-control tier is invalid")
        if tier in score_hashes:
            raise DriftCanaryError("Gold evidence repeats a reference-control tier")
        score_hashes[tier] = _required_hash(
            item, "score_semantic_report_sha256", "Gold evidence reference control"
        )
    if set(score_hashes) != {1, 2, 3}:
        raise DriftCanaryError("Gold evidence must bind one reference control per tier")

    cohort_id = scoring_cohort_id(
        settings.active_scoring_manifest_sha256,
        settings.active_grader_source_tree_sha256,
        settings.active_environment_attestation_sha256,
    )
    return FrozenCanaryBindings(
        benchmark_version=benchmark_version,
        scoring_manifest_sha256=manifest_sha256,
        scoring_cohort_id=cohort_id,
        gold_evidence_sha256=gold_evidence_sha256,
        original_gold_sha256=original_sha256,
        resolved_gold_sha256=resolved_sha256,
        resolved_gold_size_bytes=size_value,
        canonical_package_hash_profile_sha256=canonical_profile_sha256,
        canonical_package_hash_v1=canonical_package_sha256,
        expected_png_sha256s=png_hashes,
        expected_scene_graph_sha256=scene_graph_sha256,
        expected_score_sha256_by_tier=score_hashes,
        manifest=manifest,
        gold_evidence=gold_evidence,
    )


def _control_keys(settings: Settings) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(settings.control_verification_keys_json)
    except json.JSONDecodeError as exc:
        raise ControlAuthorizationError("Control verification-key JSON is invalid") from exc
    if not isinstance(value, dict) or not value:
        raise ControlAuthorizationError("No maintainer control verification keys are configured")
    if value == json.loads(settings.quarantine_verification_keys_json):
        raise ControlAuthorizationError(
            "Maintainer control keys must be distinct from quarantine-verdict keys"
        )
    return cast(dict[str, dict[str, Any]], value)


def verify_control_authorization(
    document: dict[str, Any],
    settings: Settings,
    bindings: FrozenCanaryBindings,
    *,
    now: datetime | None = None,
) -> VerifiedControl:
    """Verify schema, purpose-scoped key, signature, freshness, and every release binding."""
    schema = _load_object(_resolve_schema(settings.control_handoff_schema_path), "Control schema")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        raise ControlAuthorizationError(
            f"Control authorization is not schema-valid: {errors[0].message}"
        )
    if document.get("run_kind") != "reference_control" or document.get("purpose") != (
        "drift_canary"
    ):
        raise ControlAuthorizationError(
            "Drift canary requires a reference_control authorization scoped to drift_canary"
        )

    keys = _control_keys(settings)
    key_id = document.get("issuer_key_id")
    record = keys.get(key_id) if isinstance(key_id, str) else None
    if not isinstance(record, dict):
        raise ControlAuthorizationError("Control authorization issuer key is unknown")
    purposes = record.get("purposes")
    if not isinstance(purposes, list) or "drift_canary" not in purposes:
        raise ControlAuthorizationError("Maintainer key is not scoped to drift_canary")
    public_value = record.get("public_key")
    if not isinstance(public_value, str):
        raise ControlAuthorizationError("Maintainer public key is missing")

    issued_at = parse_utc(document.get("issued_at"), "issued_at")
    expires_at = parse_utc(document.get("expires_at"), "expires_at")
    not_before = parse_utc(record.get("not_before"), "not_before")
    not_after = parse_utc(record.get("not_after"), "not_after")
    revoked_raw = record.get("revoked_at")
    revoked_at = parse_utc(revoked_raw, "revoked_at") if revoked_raw is not None else None
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    if issued_at > moment or expires_at <= issued_at or expires_at <= moment:
        raise ControlAuthorizationError("Control authorization is future-dated or expired")
    if not_before > issued_at or not_after <= issued_at or not_after <= moment:
        raise ControlAuthorizationError("Maintainer control key is inactive")
    if revoked_at is not None and (issued_at >= revoked_at or moment >= revoked_at):
        raise ControlAuthorizationError("Maintainer control key is revoked")

    signature_value = _required_mapping(document, "signature", "Control authorization")
    encoded_signature = signature_value.get("signature_base64")
    if not isinstance(encoded_signature, str):
        raise ControlAuthorizationError("Control authorization signature is missing")
    unsigned = dict(document)
    unsigned.pop("signature", None)
    try:
        signature = base64.b64decode(encoded_signature, validate=True)
        load_public_key(public_value).verify(signature, rfc8785.dumps(unsigned))
    except (ValueError, InvalidSignature) as exc:
        raise ControlAuthorizationError("Control authorization signature is invalid") from exc

    expected_artifact = {
        "original_submission_sha256": bindings.original_gold_sha256,
        "mce_resolved_package_sha256": bindings.resolved_gold_sha256,
        "mce_resolved_package_size_bytes": bindings.resolved_gold_size_bytes,
        "canonical_package_hash_profile_sha256": (bindings.canonical_package_hash_profile_sha256),
        "canonical_package_hash_v1": bindings.canonical_package_hash_v1,
    }
    expected_profiles = {
        "grader_source_tree_sha256": settings.active_grader_source_tree_sha256,
        "environment_attestation_sha256": settings.active_environment_attestation_sha256,
        "mce_profile_sha256": settings.active_mce_profile_sha256,
        "xsd_bundle_sha256": settings.active_schema_bundle_sha256,
        "schema_root_map_sha256": settings.active_schema_root_map_sha256,
        "canonical_package_hash_profile_sha256": (
            settings.active_canonical_package_hash_profile_sha256
        ),
        "scored_assertion_inventory_sha256": (settings.active_scored_assertion_inventory_sha256),
        "checklist_bundle_sha256": settings.active_checklist_bundle_sha256,
    }
    expected_evidence = {
        "evidence_id": bindings.gold_evidence.get("evidence_id"),
        "evidence_sha256": bindings.gold_evidence_sha256,
    }
    exact_bindings = {
        "artifact_identity": expected_artifact,
        "evidence_binding": expected_evidence,
        "scoring_manifest_sha256": bindings.scoring_manifest_sha256,
        "scoring_cohort_id": bindings.scoring_cohort_id,
        "profile_hashes": expected_profiles,
    }
    mismatches = [name for name, value in exact_bindings.items() if document.get(name) != value]
    if mismatches:
        raise ControlAuthorizationError(
            "Control authorization release binding mismatch: " + ", ".join(mismatches)
        )

    tier = document.get("requested_tier")
    authorization_id = document.get("authorization_id")
    nonce = document.get("single_use_nonce")
    if not isinstance(tier, int) or isinstance(tier, bool):
        raise ControlAuthorizationError("Control authorization tier is malformed")
    if not isinstance(authorization_id, str) or not isinstance(nonce, str):
        raise ControlAuthorizationError("Control authorization identity is malformed")
    return VerifiedControl(
        document=document,
        authorization_id=authorization_id,
        authorization_sha256=_jcs_sha256(document),
        nonce_sha256=f"sha256:{hashlib.sha256(nonce.encode()).hexdigest()}",
        issuer_key_id=cast(str, key_id),
        targeted_tier=tier,
    )


def _reserve_authorizations(
    session: Session,
    controls: Sequence[VerifiedControl],
    canary_run_id: str,
    consumed_at: datetime,
) -> None:
    for control in controls:
        if session.get(DriftCanaryAuthorizationUse, control.authorization_id) is not None:
            raise ControlAuthorizationError("Control authorization has already been consumed")
        if session.scalar(
            select(DriftCanaryAuthorizationUse.authorization_id).where(
                DriftCanaryAuthorizationUse.nonce_sha256 == control.nonce_sha256
            )
        ):
            raise ControlAuthorizationError("Control authorization nonce has already been consumed")
        session.add(
            DriftCanaryAuthorizationUse(
                authorization_id=control.authorization_id,
                nonce_sha256=control.nonce_sha256,
                canary_run_id=canary_run_id,
                targeted_tier=control.targeted_tier,
                authorization_sha256=control.authorization_sha256,
                consumed_at=consumed_at,
            )
        )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ControlAuthorizationError("Control authorization or nonce was replayed") from exc


def _reference_binding(
    settings: Settings,
    bindings: FrozenCanaryBindings,
    control: VerifiedControl,
) -> ReferenceControlBinding:
    return ReferenceControlBinding(
        control_authorization_sha256=control.authorization_sha256,
        original_submission_sha256=bindings.original_gold_sha256,
        mce_resolved_package_sha256=bindings.resolved_gold_sha256,
        canonical_package_hash_profile_sha256=(bindings.canonical_package_hash_profile_sha256),
        canonical_package_hash_v1=bindings.canonical_package_hash_v1,
        schema_bundle_sha256=settings.active_schema_bundle_sha256,
        schema_root_map_sha256=settings.active_schema_root_map_sha256,
        mce_profile_sha256=settings.active_mce_profile_sha256,
    )


def _control_result(
    control: VerifiedControl,
    outcome: CanaryGradeOutcome,
    bindings: FrozenCanaryBindings,
) -> tuple[dict[str, Any], bool]:
    report = outcome.report
    actual_score = report.get("score_semantic_report_sha256")
    expected_score = bindings.expected_score_sha256_by_tier[control.targeted_tier]
    report_hash = _jcs_sha256(report)
    perfect = (
        report.get("run_kind") == "reference_control"
        and report.get("verification_label")
        == "grading-verified reference control; no generation attribution"
        and report.get("fidelity_score") == 1.0
        and report.get("deck_passed") is True
        and report.get("eligible") is False
    )
    png_match = tuple(outcome.canonical_png_sha256s) == bindings.expected_png_sha256s
    scene_match = outcome.scene_graph_sha256 == bindings.expected_scene_graph_sha256
    score_match = actual_score == expected_score
    result = {
        "authorization_id": control.authorization_id,
        "authorization_sha256": control.authorization_sha256,
        "issuer_key_id": control.issuer_key_id,
        "nonce_sha256": control.nonce_sha256,
        "targeted_tier": control.targeted_tier,
        "expected_score_semantic_report_sha256": expected_score,
        "actual_score_semantic_report_sha256": actual_score,
        "expected_canonical_png_sha256s": list(bindings.expected_png_sha256s),
        "actual_canonical_png_sha256s": list(outcome.canonical_png_sha256s),
        "expected_scene_graph_sha256": bindings.expected_scene_graph_sha256,
        "actual_scene_graph_sha256": outcome.scene_graph_sha256,
        "report_sha256": report_hash,
        "report": report,
        "comparisons": {
            "canonical_pngs_match": png_match,
            "scene_graph_match": scene_match,
            "score_semantic_report_match": score_match,
            "reference_control_perfect": perfect,
        },
    }
    return result, png_match and scene_match and score_match and perfect


def run_drift_canary(
    session: Session,
    settings: Settings,
    runner: CanaryRunner,
    authorization_documents: Sequence[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> DriftCanaryRun:
    """Consume three signed controls, regrade gold, and persist immutable evidence."""
    started_at = (now or datetime.now(UTC)).astimezone(UTC)
    bindings = load_frozen_canary_bindings(settings)
    controls = [
        verify_control_authorization(document, settings, bindings, now=started_at)
        for document in authorization_documents
    ]
    tiers = [control.targeted_tier for control in controls]
    if sorted(tiers) != [1, 2, 3] or len(set(tiers)) != 3:
        raise ControlAuthorizationError(
            "A drift-canary batch requires one signed reference control per tier"
        )
    if (
        len({control.authorization_id for control in controls}) != 3
        or len({control.nonce_sha256 for control in controls}) != 3
    ):
        raise ControlAuthorizationError(
            "Control authorization identities and nonces must be unique"
        )
    controls.sort(key=lambda control: control.targeted_tier)

    canary_run_id = str(uuid.uuid4())
    _reserve_authorizations(session, controls, canary_run_id, started_at)
    cohort = ScoringCohortBinding(
        scoring_cohort_id=bindings.scoring_cohort_id,
        scoring_manifest_sha256=bindings.scoring_manifest_sha256,
        grader_source_tree_sha256=settings.active_grader_source_tree_sha256,
        environment_attestation_sha256=settings.active_environment_attestation_sha256,
    )
    results: list[dict[str, Any]] = []
    passed = True
    error: dict[str, str] | None = None
    try:
        for control in controls:
            outcome = runner.grade_reference_control(
                settings.gold_resolved_path,
                control.targeted_tier,
                cohort,
                _reference_binding(settings, bindings, control),
            )
            result, control_passed = _control_result(control, outcome, bindings)
            results.append(result)
            passed = passed and control_passed
    except Exception as exc:  # The audit record must survive a controlled runner failure.
        passed = False
        error = {
            "code": "canary_execution_failed",
            "message": f"{type(exc).__name__}: {exc}"[-1000:],
        }

    completed_at = datetime.now(UTC)
    status = "error" if error is not None else "pass" if passed else "drift"
    evidence: dict[str, Any] = {
        "schema_version": "1.0",
        "canary_run_id": canary_run_id,
        "benchmark_version": bindings.benchmark_version,
        "scoring_cohort_id": bindings.scoring_cohort_id,
        "scoring_manifest_sha256": bindings.scoring_manifest_sha256,
        "gold_evidence_sha256": bindings.gold_evidence_sha256,
        "status": status,
        "started_at": utc_text(started_at),
        "completed_at": utc_text(completed_at),
        "controls": results,
        "error": error,
    }
    evidence_sha256 = _jcs_sha256(evidence)
    record = DriftCanaryRun(
        id=canary_run_id,
        benchmark_version=bindings.benchmark_version,
        scoring_cohort_id=bindings.scoring_cohort_id,
        scoring_manifest_sha256=bindings.scoring_manifest_sha256,
        status=status,
        evidence_json=evidence,
        evidence_sha256=evidence_sha256,
        started_at=started_at,
        completed_at=completed_at,
    )
    session.add(record)
    session.commit()
    CANARY_RUNS.labels(status).inc()
    CANARY_LAST_COMPLETED.set(completed_at.timestamp())
    CANARY_BLOCKED.set(0 if status == "pass" else 1)
    return record


def _blocked(code: str, message: str, run_id: str | None = None) -> DriftCanaryHealth:
    CANARY_BLOCKED.set(1)
    return DriftCanaryHealth(False, code, message, run_id)


def drift_canary_health(
    session: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> DriftCanaryHealth:
    """Return the fail-closed production gate for the active scoring cohort."""
    cohort_id = scoring_cohort_id(
        settings.active_scoring_manifest_sha256,
        settings.active_grader_source_tree_sha256,
        settings.active_environment_attestation_sha256,
    )
    record = session.scalar(
        select(DriftCanaryRun)
        .where(
            DriftCanaryRun.scoring_cohort_id == cohort_id,
            DriftCanaryRun.scoring_manifest_sha256 == settings.active_scoring_manifest_sha256,
            DriftCanaryRun.benchmark_version.in_(settings.active_benchmark_versions),
        )
        .order_by(DriftCanaryRun.completed_at.desc())
        .limit(1)
    )
    if record is None:
        return _blocked(
            "drift_canary_missing",
            "No production drift-canary result exists for the active scoring cohort.",
        )
    started_at = (
        record.started_at.replace(tzinfo=UTC)
        if record.started_at.tzinfo is None
        else record.started_at.astimezone(UTC)
    )
    completed_at = (
        record.completed_at.replace(tzinfo=UTC)
        if record.completed_at.tzinfo is None
        else record.completed_at.astimezone(UTC)
    )
    CANARY_LAST_COMPLETED.set(completed_at.timestamp())
    try:
        actual_evidence_sha256 = _jcs_sha256(record.evidence_json)
    except DriftCanaryError:
        return _blocked(
            "drift_canary_tampered",
            "The latest drift-canary evidence is not canonicalizable.",
            record.id,
        )
    if actual_evidence_sha256 != record.evidence_sha256:
        return _blocked(
            "drift_canary_tampered",
            "The latest drift-canary evidence hash is invalid.",
            record.id,
        )
    evidence = record.evidence_json
    column_bindings = {
        "canary_run_id": record.id,
        "benchmark_version": record.benchmark_version,
        "scoring_cohort_id": record.scoring_cohort_id,
        "scoring_manifest_sha256": record.scoring_manifest_sha256,
        "status": record.status,
        "started_at": utc_text(started_at),
        "completed_at": utc_text(completed_at),
    }
    if any(evidence.get(name) != value for name, value in column_bindings.items()):
        return _blocked(
            "drift_canary_tampered",
            "The latest drift-canary evidence does not match its immutable record.",
            record.id,
        )
    if record.status not in {"pass", "drift"}:
        return _blocked(
            "drift_canary_error",
            "The latest drift canary did not complete successfully.",
            record.id,
        )
    controls = evidence.get("controls")
    control_tiers = (
        [item.get("targeted_tier") for item in controls]
        if isinstance(controls, list) and all(isinstance(item, dict) for item in controls)
        else []
    )
    if (
        len(control_tiers) != 3
        or not all(isinstance(tier, int) and not isinstance(tier, bool) for tier in control_tiers)
        or sorted(cast(list[int], control_tiers)) != [1, 2, 3]
    ):
        return _blocked(
            "drift_canary_tampered",
            "The latest drift-canary evidence does not contain all three controls.",
            record.id,
        )
    if record.status == "drift":
        return _blocked(
            "drift_canary_drift",
            "The latest drift canary detected scoring, pixel, or structural drift.",
            record.id,
        )
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    if completed_at < moment - timedelta(seconds=settings.drift_canary_max_age_seconds):
        return _blocked(
            "drift_canary_stale",
            "The latest passing drift canary is older than the production freshness limit.",
            record.id,
        )
    CANARY_BLOCKED.set(0)
    return DriftCanaryHealth(
        True,
        "drift_canary_current",
        "The active scoring cohort has a current passing drift canary.",
        record.id,
    )
