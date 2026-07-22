"""Verification of the signed release identity carried by every grade report."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from acidslide.resources import resolve_normative_schema_file
from acidslide.source_tree import (
    GraderSourceTreeError,
    GraderSourceTreeIdentity,
    verify_grader_source_tree,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_PREFIXED_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_KEY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_RELEASE_CHANNEL = "acidslide-v1-stable"
_DEFAULT_CLOCK_SKEW = timedelta(minutes=5)
_INDEX_FIELDS = {
    "schema_version",
    "release_id",
    "benchmark_version",
    "channel",
    "issued_at",
    "effective_at",
    "sequence",
    "previous_release_index_sha256",
    "acceptance_policy",
    "state",
    "scoring_manifest_sha256",
    "cohort_descriptor",
    "scoring_cohort_id",
    "signatures",
}
_SIGNATURE_FIELDS = {"algorithm", "key_id", "signature_base64"}
_KEY_FIELDS = {
    "key_id",
    "algorithm",
    "public_key_base64",
    "valid_from",
    "valid_until",
    "revoked_at",
}


class ReleaseProvenanceError(RuntimeError):
    """Raised when a benchmark release identity cannot be trusted."""


@dataclass(frozen=True)
class ScoringCohortProvenance:
    """The exact four-field comparison identity required in every report."""

    scoring_cohort_id: str
    scoring_manifest_sha256: str
    grader_source_tree_sha256: str
    environment_attestation_sha256: str

    def validate(self) -> None:
        for name, value in (
            ("scoring_cohort_id", self.scoring_cohort_id),
            ("scoring_manifest_sha256", self.scoring_manifest_sha256),
            ("grader_source_tree_sha256", self.grader_source_tree_sha256),
            ("environment_attestation_sha256", self.environment_attestation_sha256),
        ):
            if not _PREFIXED_SHA256.fullmatch(value):
                raise ReleaseProvenanceError(f"{name} is not a canonical prefixed SHA-256")
        expected = derive_scoring_cohort_id(
            self.scoring_manifest_sha256,
            self.grader_source_tree_sha256,
            self.environment_attestation_sha256,
        )
        if self.scoring_cohort_id != expected:
            raise ReleaseProvenanceError("scoring_cohort_id does not match its JCS descriptor")


@dataclass(frozen=True)
class _VerifiedReleaseIndex:
    document: dict[str, Any]
    sha256: str
    sequence: int
    issued_at: datetime
    effective_at: datetime


def derive_scoring_cohort_id(
    scoring_manifest_sha256: str,
    grader_source_tree_sha256: str,
    environment_attestation_sha256: str,
) -> str:
    """Derive the cohort ID using the exact OpenSpec RFC 8785 descriptor."""
    descriptor = {
        "schema_version": "1.0",
        "scoring_manifest_sha256": scoring_manifest_sha256,
        "grader_source_tree_sha256": grader_source_tree_sha256,
        "environment_attestation_sha256": environment_attestation_sha256,
    }
    return f"sha256:{hashlib.sha256(rfc8785.dumps(descriptor)).hexdigest()}"


def load_signed_release_provenance(
    benchmark_dir: Path,
    *,
    acceptance_state_path: Path | None = None,
    trusted_genesis_sha256: str | None = None,
    verification_time: datetime | None = None,
    clock_skew: timedelta = _DEFAULT_CLOCK_SKEW,
    grader_source_path: Path | None = None,
    source_tree_profile_path: Path | None = None,
) -> ScoringCohortProvenance:
    """Verify a complete signed release chain and persist its highest accepted head.

    A sequence-1 ``release-index.json`` remains a valid legacy chain. Later heads
    require a canonical ``release-index-chain.json`` containing every index from
    genesis through the exact packaged head.
    """
    manifest_path = benchmark_dir / "scoring-manifest.json"
    index_path = benchmark_dir / "release-index.json"
    keys_path = _release_keys_path(benchmark_dir)
    manifest_bytes, manifest = _load_canonical_json(manifest_path, "scoring manifest")
    index_bytes, index = _load_canonical_json(index_path, "release index")
    _, keyring = _load_canonical_json(keys_path, "release keyring")
    indexes = _load_release_chain(benchmark_dir, index_bytes, index)
    now = _verification_time(verification_time)
    verified_chain = _verify_release_chain(indexes, keyring, now=now, clock_skew=clock_skew)
    head = verified_chain[-1]
    index = head.document

    if manifest.get("release_status") != "frozen":
        raise ReleaseProvenanceError("scoring manifest is not frozen")
    if index.get("state") != "active":
        raise ReleaseProvenanceError("release index chain head is not active")
    if index.get("benchmark_version") != manifest.get("benchmark_version"):
        raise ReleaseProvenanceError("release index and scoring manifest versions differ")

    actual_manifest_hash = f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}"
    if index.get("scoring_manifest_sha256") != actual_manifest_hash:
        raise ReleaseProvenanceError("scoring manifest hash does not match the release index")

    descriptor = _mapping(index.get("cohort_descriptor"), "cohort descriptor")
    if descriptor.get("schema_version") != "1.0":
        raise ReleaseProvenanceError("unsupported cohort descriptor version")
    if descriptor.get("scoring_manifest_sha256") != actual_manifest_hash:
        raise ReleaseProvenanceError("cohort descriptor does not bind the scoring manifest")

    provenance = ScoringCohortProvenance(
        scoring_cohort_id=_string(index.get("scoring_cohort_id"), "scoring_cohort_id"),
        scoring_manifest_sha256=actual_manifest_hash,
        grader_source_tree_sha256=_string(
            descriptor.get("grader_source_tree_sha256"), "grader_source_tree_sha256"
        ),
        environment_attestation_sha256=_string(
            descriptor.get("environment_attestation_sha256"),
            "environment_attestation_sha256",
        ),
    )
    provenance.validate()
    resolved_source = _resolve_grader_source(benchmark_dir, grader_source_path)
    resolved_source_profile = resolve_normative_schema_file(
        "grader-source-tree-profile-v1.json", source_tree_profile_path
    )
    try:
        source_identity = verify_grader_source_tree(
            resolved_source,
            benchmark_dir / "grader-source-tree-manifest.json",
            resolved_source_profile,
        )
    except GraderSourceTreeError as exc:
        raise ReleaseProvenanceError(str(exc)) from exc
    _validate_source_tree_bindings(manifest, provenance, source_identity)
    _accept_release_head(
        verified_chain,
        acceptance_state_path or _default_acceptance_state_path(),
        trusted_genesis_sha256=trusted_genesis_sha256
        or os.getenv("ACIDSLIDE_TRUSTED_GENESIS_SHA256"),
    )
    return provenance


def _resolve_grader_source(benchmark_dir: Path, explicit: Path | None) -> Path:
    configured = explicit
    if configured is None:
        environment_path = os.getenv("ACIDSLIDE_GRADER_SOURCE_PATH")
        configured = Path(environment_path).expanduser() if environment_path else None
    if configured is not None:
        return configured
    candidates = (
        benchmark_dir.parent / "grader",
        benchmark_dir / "grader-source",
        benchmark_dir / "grader-source-tree.tar",
    )
    existing = [candidate for candidate in candidates if candidate.exists()]
    if len(existing) > 1:
        raise ReleaseProvenanceError("grader source-tree location is ambiguous")
    if existing:
        return existing[0]
    raise ReleaseProvenanceError("grader source tree or release archive is unavailable")


def _validate_source_tree_bindings(
    scoring_manifest: dict[str, Any],
    provenance: ScoringCohortProvenance,
    identity: GraderSourceTreeIdentity,
) -> None:
    if identity.manifest_sha256 != provenance.grader_source_tree_sha256:
        raise ReleaseProvenanceError(
            "reconstructed grader source-tree hash differs from the signed cohort"
        )
    artifacts = _mapping(scoring_manifest.get("artifacts"), "scoring manifest artifacts")
    for field in ("grader_source_tree_sha256", "grader_source_tree_manifest_sha256"):
        if artifacts.get(field) != identity.manifest_sha256:
            raise ReleaseProvenanceError(f"scoring manifest {field} does not match reconstruction")
    if artifacts.get("grader_source_tree_profile_sha256") != identity.profile_sha256:
        raise ReleaseProvenanceError(
            "scoring manifest source-tree profile hash does not match reconstruction"
        )


def _load_release_chain(
    benchmark_dir: Path,
    head_bytes: bytes,
    head: dict[str, Any],
) -> list[dict[str, Any]]:
    chain_path = benchmark_dir / "release-index-chain.json"
    if not chain_path.is_file():
        return [head]
    _, chain = _load_canonical_json(chain_path, "release index chain")
    if set(chain) != {"schema_version", "channel", "indexes"}:
        raise ReleaseProvenanceError("release index chain has unsupported fields")
    if chain.get("schema_version") != "1.0" or chain.get("channel") != _RELEASE_CHANNEL:
        raise ReleaseProvenanceError("release index chain identity is unsupported")
    indexes = chain.get("indexes")
    if not isinstance(indexes, list) or not indexes:
        raise ReleaseProvenanceError("release index chain has no indexes")
    if not all(isinstance(candidate, dict) for candidate in indexes):
        raise ReleaseProvenanceError("release index chain entries must be objects")
    typed_indexes = list(indexes)
    if rfc8785.dumps(typed_indexes[-1]) != head_bytes:
        raise ReleaseProvenanceError("release index does not match the packaged chain head")
    return typed_indexes


def _verify_release_chain(
    indexes: list[dict[str, Any]],
    keyring: dict[str, Any],
    *,
    now: datetime,
    clock_skew: timedelta,
) -> list[_VerifiedReleaseIndex]:
    if clock_skew < timedelta(0):
        raise ReleaseProvenanceError("release clock skew cannot be negative")
    verified: list[_VerifiedReleaseIndex] = []
    previous_issued_at: datetime | None = None
    previous_effective_at: datetime | None = None
    previous_state_order: int | None = None
    state_order = {"active": 0, "frozen": 1, "superseded": 2}
    for expected_sequence, index in enumerate(indexes, start=1):
        _validate_index_shape(index)
        if index.get("channel") != _RELEASE_CHANNEL:
            raise ReleaseProvenanceError("release index channel is not acidslide-v1-stable")
        if index.get("acceptance_policy") != "highest_valid_chain_head":
            raise ReleaseProvenanceError("release index acceptance policy is unsupported")
        state = index.get("state")
        if not isinstance(state, str) or state not in state_order:
            raise ReleaseProvenanceError("release index state is unsupported")
        if previous_state_order is not None and state_order[state] < previous_state_order:
            raise ReleaseProvenanceError("release index state moves backward")
        sequence = index.get("sequence")
        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or sequence != expected_sequence
        ):
            raise ReleaseProvenanceError("release index chain has a sequence gap")
        expected_previous = None if not verified else verified[-1].sha256
        if index.get("previous_release_index_sha256") != expected_previous:
            raise ReleaseProvenanceError(
                "release index previous hash does not match its predecessor"
            )

        issued_at = _timestamp(index.get("issued_at"), "issued_at")
        effective_at = _timestamp(index.get("effective_at"), "effective_at")
        if effective_at < issued_at:
            raise ReleaseProvenanceError("release index effective_at precedes issued_at")
        if previous_issued_at is not None and issued_at < previous_issued_at:
            raise ReleaseProvenanceError("release index issued_at moves backward")
        if previous_effective_at is not None and effective_at < previous_effective_at:
            raise ReleaseProvenanceError("release index effective_at moves backward")
        if issued_at > now + clock_skew:
            raise ReleaseProvenanceError("release index issued_at exceeds the clock-skew bound")
        if effective_at > now:
            raise ReleaseProvenanceError("release index is not effective yet")

        _validate_index_cohort(index)
        _verify_release_signature(index, keyring, issued_at=issued_at, effective_at=effective_at)
        verified.append(
            _VerifiedReleaseIndex(
                document=index,
                sha256=_canonical_document_sha256(index),
                sequence=expected_sequence,
                issued_at=issued_at,
                effective_at=effective_at,
            )
        )
        previous_issued_at = issued_at
        previous_effective_at = effective_at
        previous_state_order = state_order[state]
    return verified


def _validate_index_cohort(index: dict[str, Any]) -> None:
    descriptor = _mapping(index.get("cohort_descriptor"), "cohort descriptor")
    if descriptor.get("schema_version") != "1.0":
        raise ReleaseProvenanceError("unsupported cohort descriptor version")
    scoring_manifest_sha256 = _string(
        index.get("scoring_manifest_sha256"), "scoring_manifest_sha256"
    )
    _require_prefixed_sha256(scoring_manifest_sha256, "scoring_manifest_sha256")
    if descriptor.get("scoring_manifest_sha256") != scoring_manifest_sha256:
        raise ReleaseProvenanceError("cohort descriptor does not bind the release manifest")
    grader_sha256 = _string(
        descriptor.get("grader_source_tree_sha256"), "grader_source_tree_sha256"
    )
    environment_sha256 = _string(
        descriptor.get("environment_attestation_sha256"),
        "environment_attestation_sha256",
    )
    _require_prefixed_sha256(grader_sha256, "grader_source_tree_sha256")
    _require_prefixed_sha256(environment_sha256, "environment_attestation_sha256")
    expected = derive_scoring_cohort_id(
        scoring_manifest_sha256,
        grader_sha256,
        environment_sha256,
    )
    _require_prefixed_sha256(
        _string(index.get("scoring_cohort_id"), "scoring_cohort_id"), "scoring_cohort_id"
    )
    if index.get("scoring_cohort_id") != expected:
        raise ReleaseProvenanceError("release index scoring_cohort_id is invalid")


def _canonical_document_sha256(document: dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(rfc8785.dumps(document)).hexdigest()}"


def _validate_index_shape(index: dict[str, Any]) -> None:
    if set(index) != _INDEX_FIELDS:
        raise ReleaseProvenanceError("release index has missing or unsupported fields")
    if index.get("schema_version") != "1.0":
        raise ReleaseProvenanceError("release index schema version is unsupported")
    if index.get("release_id") != "acidslide-v1.0.0":
        raise ReleaseProvenanceError("release index release_id is unsupported")
    if index.get("benchmark_version") != "acidslide-v1.0.0":
        raise ReleaseProvenanceError("release index benchmark_version is unsupported")


def _release_keys_path(benchmark_dir: Path) -> Path:
    """Resolve the repository keyring and the equivalent packaged-wheel location."""
    candidates = (benchmark_dir.parent / "RELEASE_KEYS.json", benchmark_dir / "RELEASE_KEYS.json")
    existing = [candidate for candidate in candidates if candidate.is_file()]
    if len(existing) > 1:
        raise ReleaseProvenanceError("release keyring location is ambiguous")
    if existing:
        return existing[0]
    return candidates[0]


def _load_canonical_json(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReleaseProvenanceError(f"{label} is unavailable: {path}") from exc
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseProvenanceError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(document, dict):
        raise ReleaseProvenanceError(f"{label} must be a JSON object")
    try:
        canonical = rfc8785.dumps(document)
    except rfc8785.CanonicalizationError as exc:
        raise ReleaseProvenanceError(f"{label} cannot be canonicalized") from exc
    if raw != canonical:
        raise ReleaseProvenanceError(f"{label} is not RFC 8785 canonical JSON")
    return raw, document


def _verification_time(value: datetime | None) -> datetime:
    now = value or datetime.now(UTC)
    if now.tzinfo is None:
        raise ReleaseProvenanceError("release verification time must include a timezone")
    return now.astimezone(UTC)


def _default_acceptance_state_path() -> Path:
    explicit = os.getenv("ACIDSLIDE_RELEASE_STATE_PATH")
    if explicit:
        return Path(explicit).expanduser()
    state_home = os.getenv("XDG_STATE_HOME")
    root = Path(state_home).expanduser() if state_home else Path.home() / ".local" / "state"
    return root / "acidslide" / "release-head-v1.json"


def _accept_release_head(
    chain: list[_VerifiedReleaseIndex],
    state_path: Path,
    *,
    trusted_genesis_sha256: str | None,
) -> None:
    genesis_sha256 = chain[0].sha256
    head = chain[-1]
    if trusted_genesis_sha256 is not None:
        _require_prefixed_sha256(trusted_genesis_sha256, "trusted genesis")
        if trusted_genesis_sha256 != genesis_sha256:
            raise ReleaseProvenanceError(
                "release chain does not match the configured trusted genesis"
            )

    with _acceptance_state_lock(state_path):
        persisted = _load_acceptance_state(state_path) if state_path.is_file() else None
        if persisted is None:
            if len(chain) > 1 and trusted_genesis_sha256 is None:
                raise ReleaseProvenanceError(
                    "trusted genesis is required to bootstrap a multi-index release chain"
                )
        else:
            persisted_genesis = _string(
                persisted.get("trusted_genesis_sha256"), "persisted trusted_genesis_sha256"
            )
            if persisted_genesis != genesis_sha256:
                raise ReleaseProvenanceError("release chain genesis differs from persisted state")
            persisted_sequence = persisted.get("sequence")
            if not isinstance(persisted_sequence, int) or isinstance(persisted_sequence, bool):
                raise ReleaseProvenanceError("persisted release sequence must be an integer")
            if persisted_sequence < 1:
                raise ReleaseProvenanceError("persisted release sequence must be positive")
            persisted_head = _string(
                persisted.get("release_index_sha256"), "persisted release_index_sha256"
            )
            _require_prefixed_sha256(persisted_head, "persisted release_index_sha256")
            if head.sequence < persisted_sequence:
                raise ReleaseProvenanceError("release index rollback is prohibited")
            if persisted_sequence > len(chain):
                raise ReleaseProvenanceError("release chain omits the persisted head")
            chain_checkpoint = chain[persisted_sequence - 1].sha256
            if chain_checkpoint != persisted_head:
                if head.sequence == persisted_sequence:
                    raise ReleaseProvenanceError("release index fork at the persisted sequence")
                raise ReleaseProvenanceError("release chain forks from the persisted head")

        state = {
            "schema_version": "1.0",
            "channel": _RELEASE_CHANNEL,
            "trusted_genesis_sha256": genesis_sha256,
            "sequence": head.sequence,
            "release_index_sha256": head.sha256,
        }
        if persisted != state:
            _write_acceptance_state(state_path, state)


def _load_acceptance_state(path: Path) -> dict[str, Any]:
    _, state = _load_canonical_json(path, "persisted release acceptance state")
    if set(state) != {
        "schema_version",
        "channel",
        "trusted_genesis_sha256",
        "sequence",
        "release_index_sha256",
    }:
        raise ReleaseProvenanceError("persisted release acceptance state has unsupported fields")
    if state.get("schema_version") != "1.0" or state.get("channel") != _RELEASE_CHANNEL:
        raise ReleaseProvenanceError("persisted release acceptance state identity is unsupported")
    return state


@contextmanager
def _acceptance_state_lock(state_path: Path) -> Iterator[None]:
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = state_path.with_name(f"{state_path.name}.lock")
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise ReleaseProvenanceError(
            f"release acceptance state is unavailable: {state_path}"
        ) from exc


def _write_acceptance_state(path: Path, state: dict[str, Any]) -> None:
    descriptor: int | None = None
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(rfc8785.dumps(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError as exc:
        raise ReleaseProvenanceError(f"could not persist release acceptance state: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_name is not None:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)


def _require_prefixed_sha256(value: str, name: str) -> None:
    if not _PREFIXED_SHA256.fullmatch(value):
        raise ReleaseProvenanceError(f"{name} is not a canonical prefixed SHA-256")


def _verify_release_signature(
    index: dict[str, Any],
    keyring: dict[str, Any],
    *,
    issued_at: datetime,
    effective_at: datetime,
) -> None:
    _validate_keyring_shape(keyring)
    signatures = index.get("signatures")
    keys = keyring.get("keys")
    if not isinstance(signatures, list) or not signatures:
        raise ReleaseProvenanceError("release index has no signatures")
    if not isinstance(keys, list) or not keys:
        raise ReleaseProvenanceError("release keyring has no keys")

    signed_payload = dict(index)
    signed_payload.pop("signatures", None)
    message = rfc8785.dumps(signed_payload)
    keys_by_id: dict[str, dict[str, Any]] = {}
    for key in keys:
        if not isinstance(key, dict):
            raise ReleaseProvenanceError("release keyring entries must be objects")
        key_id = key.get("key_id")
        if not isinstance(key_id, str):
            raise ReleaseProvenanceError("release key_id must be a string")
        if key_id in keys_by_id:
            raise ReleaseProvenanceError(f"release keyring contains duplicate key_id: {key_id}")
        keys_by_id[key_id] = key
    for signature in signatures:
        if not isinstance(signature, dict) or set(signature) != _SIGNATURE_FIELDS:
            raise ReleaseProvenanceError("release signature has missing or unsupported fields")
        if signature.get("algorithm") != "Ed25519":
            raise ReleaseProvenanceError("release signature algorithm is unsupported")
        signature_key_id = signature.get("key_id")
        if not isinstance(signature_key_id, str) or not _KEY_ID.fullmatch(signature_key_id):
            raise ReleaseProvenanceError("release signature key_id is invalid")
        key = keys_by_id.get(signature_key_id)
        if not isinstance(key, dict) or not _key_valid_for_release(key, issued_at, effective_at):
            continue
        try:
            public_bytes = base64.b64decode(
                _string(key.get("public_key_base64"), "public key"), validate=True
            )
            signature_bytes = base64.b64decode(
                _string(signature.get("signature_base64"), "release signature"), validate=True
            )
            Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature_bytes, message)
        except (ValueError, InvalidSignature):
            continue
        return
    raise ReleaseProvenanceError(
        "release index has no valid signature from a non-revoked key valid at released_at"
    )


def _validate_keyring_shape(keyring: dict[str, Any]) -> None:
    if set(keyring) != {"schema_version", "keys"} or keyring.get("schema_version") != "1.0":
        raise ReleaseProvenanceError("release keyring identity or fields are unsupported")
    keys = keyring.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ReleaseProvenanceError("release keyring has no keys")
    for key in keys:
        if not isinstance(key, dict) or set(key) != _KEY_FIELDS:
            raise ReleaseProvenanceError("release key has missing or unsupported fields")
        key_id = key.get("key_id")
        if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
            raise ReleaseProvenanceError("release key_id is invalid")
        if key.get("algorithm") != "Ed25519":
            raise ReleaseProvenanceError("release key algorithm is unsupported")
        try:
            public_bytes = base64.b64decode(
                _string(key.get("public_key_base64"), "public key"), validate=True
            )
        except ValueError as exc:
            raise ReleaseProvenanceError("release public key is not canonical base64") from exc
        if len(public_bytes) != 32:
            raise ReleaseProvenanceError("release public key is not 32 bytes")
        _timestamp(key.get("valid_from"), "valid_from")
        for name in ("valid_until", "revoked_at"):
            value = key.get(name)
            if value is not None:
                _timestamp(value, name)


def _key_valid_for_release(
    key: dict[str, Any], issued_at: datetime, effective_at: datetime
) -> bool:
    if key.get("algorithm") != "Ed25519":
        return False
    try:
        valid_from = _timestamp(key.get("valid_from"), "valid_from")
        valid_until_raw = key.get("valid_until")
        valid_until = (
            _timestamp(valid_until_raw, "valid_until") if valid_until_raw is not None else None
        )
        revoked_at_raw = key.get("revoked_at")
        revoked_at = (
            _timestamp(revoked_at_raw, "revoked_at") if revoked_at_raw is not None else None
        )
    except ReleaseProvenanceError:
        return False
    if issued_at < valid_from or effective_at < valid_from:
        return False
    if valid_until is not None and (issued_at > valid_until or effective_at > valid_until):
        return False
    return revoked_at is None or (issued_at < revoked_at and effective_at < revoked_at)


def _timestamp(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise ReleaseProvenanceError(f"{name} must be an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseProvenanceError(f"{name} must be an RFC 3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ReleaseProvenanceError(f"{name} must include a timezone")
    return parsed


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseProvenanceError(f"{name} must be an object")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ReleaseProvenanceError(f"{name} must be a string")
    return value
