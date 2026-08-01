"""Signed, single-use quarantine handoff contract.

The verdict is deliberately independent from the transport used to run the
quarantine sandbox.  Both a local test process and the production Docker
runner emit the same RFC 8785 canonical payload and Ed25519 signature.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


class QuarantineHandoffError(ValueError):
    """The signed quarantine-to-worker handoff failed closed."""


@dataclass(frozen=True)
class ObjectBinding:
    object_version: str
    sha256: str
    size_bytes: int

    def as_dict(self) -> dict[str, str | int]:
        return {
            "object_version": self.object_version,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class QuarantineJobBinding:
    submission_id: str
    campaign_id: str
    campaign_slot: int
    tier: int
    original: ObjectBinding
    resolved_object_version: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> QuarantineJobBinding:
        original = value.get("original")
        if not isinstance(original, dict):
            raise QuarantineHandoffError("Original object binding is missing")
        try:
            return cls(
                submission_id=str(value["submission_id"]),
                campaign_id=str(value["campaign_id"]),
                campaign_slot=int(value["campaign_slot"]),
                tier=int(value["tier"]),
                original=ObjectBinding(
                    object_version=str(original["object_version"]),
                    sha256=str(original["sha256"]),
                    size_bytes=int(original["size_bytes"]),
                ),
                resolved_object_version=str(value["resolved_object_version"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise QuarantineHandoffError("Quarantine job binding is malformed") from exc


@dataclass(frozen=True)
class QuarantineKey:
    key_id: str
    public_key: Ed25519PublicKey
    not_before: datetime
    not_after: datetime
    revoked_at: datetime | None

    def active_at(self, moment: datetime) -> bool:
        return self.not_before <= moment < self.not_after and (
            self.revoked_at is None or moment < self.revoked_at
        )


def jcs_bytes(value: Any) -> bytes:
    """Serialize one JSON value using RFC 8785 canonical JSON."""
    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, rfc8785.FloatDomainError) as exc:
        raise QuarantineHandoffError("Verdict payload is not JCS canonicalizable") from exc


def sha256_id(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def encode_private_key(key: Ed25519PrivateKey) -> str:
    raw = key.private_bytes_raw()
    return base64.b64encode(raw).decode("ascii")


def encode_public_key(key: Ed25519PublicKey) -> str:
    raw = key.public_bytes_raw()
    return base64.b64encode(raw).decode("ascii")


def load_private_key(value: str) -> Ed25519PrivateKey:
    try:
        raw = base64.b64decode(value, validate=True)
        return Ed25519PrivateKey.from_private_bytes(raw)
    except (ValueError, TypeError) as exc:
        raise QuarantineHandoffError("Invalid Ed25519 private key") from exc


def load_public_key(value: str) -> Ed25519PublicKey:
    try:
        raw = base64.b64decode(value, validate=True)
        return Ed25519PublicKey.from_public_bytes(raw)
    except (ValueError, TypeError) as exc:
        raise QuarantineHandoffError("Invalid Ed25519 public key") from exc


def utc_text(value: datetime) -> str:
    normalized = value.astimezone(UTC).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise QuarantineHandoffError(f"Verdict {field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise QuarantineHandoffError(f"Verdict {field} is invalid") from exc
    return parsed.astimezone(UTC)


def load_verification_keys(document: str) -> dict[str, QuarantineKey]:
    """Load the rotation/status document from service configuration."""
    try:
        value = json.loads(document)
    except json.JSONDecodeError as exc:
        raise QuarantineHandoffError("Quarantine verification-key JSON is invalid") from exc
    if not isinstance(value, dict) or not value:
        raise QuarantineHandoffError("No quarantine verification keys are configured")

    keys: dict[str, QuarantineKey] = {}
    for key_id, record in value.items():
        if not isinstance(key_id, str) or not key_id or not isinstance(record, dict):
            raise QuarantineHandoffError("Quarantine verification-key record is malformed")
        revoked_raw = record.get("revoked_at")
        revoked_at = parse_utc(revoked_raw, "revoked_at") if revoked_raw is not None else None
        public_value = record.get("public_key")
        if not isinstance(public_value, str):
            raise QuarantineHandoffError(f"Public key is missing for {key_id}")
        keys[key_id] = QuarantineKey(
            key_id=key_id,
            public_key=load_public_key(public_value),
            not_before=parse_utc(record.get("not_before"), "not_before"),
            not_after=parse_utc(record.get("not_after"), "not_after"),
            revoked_at=revoked_at,
        )
    return keys


def build_payload(
    *,
    verdict_id: str,
    key_id: str,
    outcome: Literal["accepted", "rejected"],
    reason: str,
    original: ObjectBinding,
    resolved: ObjectBinding | None,
    submission_id: str,
    campaign_id: str,
    campaign_slot: int,
    quarantine_profile_sha256: str,
    mce_profile_sha256: str,
    schema_bundle_sha256: str,
    schema_root_map_sha256: str,
    canonical_package_hash_profile_sha256: str,
    canonical_package_hash_v1: str | None,
    gold_duplicate_check: dict[str, Any] | None,
    schema_validation: dict[str, Any] | None,
    run_kind: Literal["submission", "reference_control"],
    control_authorization_sha256: str | None,
    control_authorization_object_version: str | None,
    issued_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    if expires_at <= issued_at:
        raise QuarantineHandoffError("Verdict expiry must follow issue time")
    return {
        "campaign_id": campaign_id,
        "campaign_slot": campaign_slot,
        "canonical_package_hash_v1": canonical_package_hash_v1,
        "control_authorization_object_version": control_authorization_object_version,
        "control_authorization_sha256": control_authorization_sha256,
        "expires_at": utc_text(expires_at),
        "gold_duplicate_check": gold_duplicate_check,
        "issued_at": utc_text(issued_at),
        "key_id": key_id,
        "original": original.as_dict(),
        "outcome": outcome,
        "profiles": {
            "canonical_package_hash_profile_sha256": (canonical_package_hash_profile_sha256),
            "mce_profile_sha256": mce_profile_sha256,
            "quarantine_profile_sha256": quarantine_profile_sha256,
            "schema_bundle_sha256": schema_bundle_sha256,
            "schema_root_map_sha256": schema_root_map_sha256,
        },
        "reason": reason,
        "resolved": resolved.as_dict() if resolved is not None else None,
        "run_kind": run_kind,
        "schema_version": "1.0",
        "schema_validation": schema_validation,
        "submission_id": submission_id,
        "verdict_id": verdict_id,
    }


def sign_payload(payload: dict[str, Any], private_key: Ed25519PrivateKey) -> dict[str, Any]:
    signature = private_key.sign(jcs_bytes(payload))
    return {
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
        "signature_algorithm": "Ed25519",
    }


def verify_envelope(
    envelope: object,
    keys: dict[str, QuarantineKey],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify structure, key status, signature, and freshness."""
    if not isinstance(envelope, dict):
        raise QuarantineHandoffError("Quarantine verdict envelope is missing")
    if envelope.get("signature_algorithm") != "Ed25519":
        raise QuarantineHandoffError("Quarantine verdict signature algorithm is invalid")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise QuarantineHandoffError("Quarantine verdict payload is missing")
    if payload.get("schema_version") != "1.0":
        raise QuarantineHandoffError("Quarantine verdict schema version is unsupported")
    key_id = payload.get("key_id")
    if not isinstance(key_id, str) or key_id not in keys:
        raise QuarantineHandoffError("Quarantine verdict key is unknown")
    issued_at = parse_utc(payload.get("issued_at"), "issued_at")
    expires_at = parse_utc(payload.get("expires_at"), "expires_at")
    if expires_at <= issued_at:
        raise QuarantineHandoffError("Quarantine verdict expiry is invalid")
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    key = keys[key_id]
    if not key.active_at(issued_at) or not key.active_at(moment):
        raise QuarantineHandoffError("Quarantine verdict key is inactive or revoked")
    if issued_at > moment:
        raise QuarantineHandoffError("Quarantine verdict was issued in the future")
    if expires_at <= moment:
        raise QuarantineHandoffError("Quarantine verdict has expired")
    signature_value = envelope.get("signature")
    if not isinstance(signature_value, str):
        raise QuarantineHandoffError("Quarantine verdict signature is missing")
    try:
        signature = base64.b64decode(signature_value, validate=True)
        key.public_key.verify(signature, jcs_bytes(payload))
    except (ValueError, InvalidSignature) as exc:
        raise QuarantineHandoffError("Quarantine verdict signature is invalid") from exc
    return cast(dict[str, Any], payload)


def require_binding(
    payload: dict[str, Any],
    *,
    original: ObjectBinding,
    resolved: ObjectBinding,
    submission_id: str,
    campaign_id: str,
    campaign_slot: int,
    expected_profiles: dict[str, str],
    expected_context: dict[str, object] | None = None,
) -> None:
    """Fail unless the signed payload binds the exact queued submission."""
    expected = {
        "submission_id": submission_id,
        "campaign_id": campaign_id,
        "campaign_slot": campaign_slot,
        "original": original.as_dict(),
        "resolved": resolved.as_dict(),
        "profiles": expected_profiles,
        "outcome": "accepted",
    }
    expected.update(expected_context or {})
    mismatches = [name for name, value in expected.items() if payload.get(name) != value]
    verdict_id = payload.get("verdict_id")
    if not isinstance(verdict_id, str) or not verdict_id:
        mismatches.append("verdict_id")
    if mismatches:
        raise QuarantineHandoffError(
            "Quarantine verdict binding mismatch: " + ", ".join(sorted(set(mismatches)))
        )
