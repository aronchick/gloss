"""Tests for signed release and scoring-cohort provenance."""

from __future__ import annotations

import base64
import hashlib
import json
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
import rfc8785
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from gloss.provenance import (
    ReleaseProvenanceError,
    ScoringCohortProvenance,
    derive_scoring_cohort_id,
    load_signed_release_provenance,
)
from gloss.source_tree import build_grader_source_tree_manifest

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"


def _write_release(
    benchmark_dir: Path,
    *,
    valid_from: str = "2026-01-01T00:00:00Z",
    valid_until: str | None = None,
    revoked_at: str | None = None,
    chain_length: int = 1,
) -> tuple[Ed25519PrivateKey, list[dict[str, Any]]]:
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    source_root = benchmark_dir / "grader-source"
    (source_root / "gloss").mkdir(parents=True)
    (source_root / "gloss" / "__init__.py").write_text(
        '"""Frozen test grader source."""\n', encoding="utf-8"
    )
    source_profile = SCHEMAS / "grader-source-tree-profile-v1.json"
    source_manifest = build_grader_source_tree_manifest(source_root, source_profile)
    source_manifest_bytes = rfc8785.dumps(cast("Any", source_manifest))
    source_manifest_sha256 = f"sha256:{hashlib.sha256(source_manifest_bytes).hexdigest()}"
    source_profile_sha256 = f"sha256:{hashlib.sha256(source_profile.read_bytes()).hexdigest()}"
    (benchmark_dir / "grader-source-tree-manifest.json").write_bytes(source_manifest_bytes)
    manifest = {
        "schema_version": "1.0",
        "release_status": "frozen",
        "benchmark_version": "gloss-v1.0.0",
        "artifacts": {
            "grader_source_tree_sha256": source_manifest_sha256,
            "grader_source_tree_manifest_sha256": source_manifest_sha256,
            "grader_source_tree_profile_sha256": source_profile_sha256,
        },
    }
    manifest_bytes = rfc8785.dumps(cast("Any", manifest))
    manifest_hash = f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}"
    grader_hash = source_manifest_sha256
    environment_hash = f"sha256:{'3' * 64}"
    descriptor = {
        "schema_version": "1.0",
        "scoring_manifest_sha256": manifest_hash,
        "grader_source_tree_sha256": grader_hash,
        "environment_attestation_sha256": environment_hash,
    }
    indexes: list[dict[str, Any]] = []
    for sequence in range(1, chain_length + 1):
        minute = (sequence - 1) * 10
        unsigned_index = {
            "schema_version": "1.0",
            "release_id": "gloss-v1.0.0",
            "benchmark_version": "gloss-v1.0.0",
            "channel": "gloss-v1-stable",
            "issued_at": f"2026-07-18T12:{minute:02d}:00Z",
            "effective_at": f"2026-07-18T12:{minute + 5:02d}:00Z",
            "sequence": sequence,
            "previous_release_index_sha256": (
                None if not indexes else _document_sha256(indexes[-1])
            ),
            "acceptance_policy": "highest_valid_chain_head",
            "state": "active",
            "scoring_manifest_sha256": manifest_hash,
            "cohort_descriptor": descriptor,
            "scoring_cohort_id": derive_scoring_cohort_id(
                manifest_hash, grader_hash, environment_hash
            ),
        }
        indexes.append(_sign_index(private_key, unsigned_index))
    keyring = {
        "schema_version": "1.0",
        "keys": [
            {
                "key_id": "release-test-1",
                "algorithm": "Ed25519",
                "public_key_base64": base64.b64encode(public_key).decode(),
                "valid_from": valid_from,
                "valid_until": valid_until,
                "revoked_at": revoked_at,
            }
        ],
    }
    (benchmark_dir / "scoring-manifest.json").write_bytes(manifest_bytes)
    (benchmark_dir / "RELEASE_KEYS.json").write_bytes(rfc8785.dumps(cast("Any", keyring)))
    _write_indexes(benchmark_dir, indexes)
    return private_key, indexes


def _sign_index(private_key: Ed25519PrivateKey, unsigned_index: dict[str, Any]) -> dict[str, Any]:
    signature = private_key.sign(rfc8785.dumps(cast("Any", unsigned_index)))
    return unsigned_index | {
        "signatures": [
            {
                "algorithm": "Ed25519",
                "key_id": "release-test-1",
                "signature_base64": base64.b64encode(signature).decode(),
            }
        ]
    }


def _document_sha256(document: dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(rfc8785.dumps(cast('Any', document))).hexdigest()}"


def _write_indexes(benchmark_dir: Path, indexes: list[dict[str, Any]]) -> None:
    (benchmark_dir / "release-index.json").write_bytes(rfc8785.dumps(cast("Any", indexes[-1])))
    chain_path = benchmark_dir / "release-index-chain.json"
    if len(indexes) == 1:
        chain_path.unlink(missing_ok=True)
        return
    chain = {
        "schema_version": "1.0",
        "channel": "gloss-v1-stable",
        "indexes": indexes,
    }
    chain_path.write_bytes(rfc8785.dumps(cast("Any", chain)))


def _load_release(
    benchmark_dir: Path,
    *,
    acceptance_state_path: Path | None = None,
    trusted_genesis_sha256: str | None = None,
    verification_time: datetime = datetime(2026, 7, 18, 13, 0, tzinfo=UTC),
) -> ScoringCohortProvenance:
    return load_signed_release_provenance(
        benchmark_dir,
        acceptance_state_path=acceptance_state_path or benchmark_dir / "accepted-release-head.json",
        trusted_genesis_sha256=trusted_genesis_sha256,
        verification_time=verification_time,
    )


def test_signed_release_provenance_verifies(tmp_path: Path) -> None:
    _write_release(tmp_path)

    provenance = _load_release(tmp_path)

    assert provenance.scoring_manifest_sha256.startswith("sha256:")
    assert provenance.grader_source_tree_sha256.startswith("sha256:")
    provenance.validate()


def test_manifest_tamper_fails_closed(tmp_path: Path) -> None:
    _write_release(tmp_path)
    (tmp_path / "scoring-manifest.json").write_bytes(
        rfc8785.dumps(
            {
                "schema_version": "1.0",
                "release_status": "frozen",
                "benchmark_version": "gloss-v1.0.0",
                "tampered": True,
            }
        )
    )

    with pytest.raises(ReleaseProvenanceError, match="manifest hash"):
        _load_release(tmp_path)


def test_grader_source_tree_tamper_fails_closed(tmp_path: Path) -> None:
    _write_release(tmp_path)
    (tmp_path / "grader-source" / "gloss" / "__init__.py").write_text(
        '"""Tampered grader source."""\n', encoding="utf-8"
    )

    with pytest.raises(ReleaseProvenanceError, match="does not match its frozen manifest"):
        _load_release(tmp_path)


def test_missing_grader_source_tree_manifest_fails_closed(tmp_path: Path) -> None:
    _write_release(tmp_path)
    (tmp_path / "grader-source-tree-manifest.json").unlink()

    with pytest.raises(ReleaseProvenanceError, match="manifest is unavailable"):
        _load_release(tmp_path)


def test_revoked_release_key_fails_closed(tmp_path: Path) -> None:
    _write_release(tmp_path, revoked_at="2026-07-17T00:00:00Z")

    with pytest.raises(ReleaseProvenanceError, match="no valid signature"):
        _load_release(tmp_path)


def test_legacy_boolean_release_state_fails_closed(tmp_path: Path) -> None:
    _write_release(tmp_path)
    index = json.loads((tmp_path / "release-index.json").read_text(encoding="utf-8"))
    index["state"] = {"active": True, "frozen": True}
    (tmp_path / "release-index.json").write_bytes(rfc8785.dumps(cast("Any", index)))

    with pytest.raises(ReleaseProvenanceError, match="state is unsupported"):
        _load_release(tmp_path)


def test_release_key_validity_boundaries_are_inclusive(tmp_path: Path) -> None:
    _write_release(
        tmp_path,
        valid_from="2026-07-18T12:00:00Z",
        valid_until="2026-07-18T12:05:00Z",
    )

    _load_release(tmp_path)


@pytest.mark.parametrize(
    ("valid_from", "valid_until", "revoked_at"),
    [
        ("2026-07-18T12:00:00.000001Z", None, None),
        ("2026-01-01T00:00:00Z", "2026-07-18T12:04:59.999999Z", None),
        ("2026-01-01T00:00:00Z", None, "2026-07-18T12:05:00Z"),
    ],
)
def test_release_key_outside_either_release_boundary_fails_closed(
    tmp_path: Path,
    valid_from: str,
    valid_until: str | None,
    revoked_at: str | None,
) -> None:
    _write_release(
        tmp_path,
        valid_from=valid_from,
        valid_until=valid_until,
        revoked_at=revoked_at,
    )

    with pytest.raises(ReleaseProvenanceError, match="no valid signature"):
        _load_release(tmp_path)


def test_duplicate_release_key_id_fails_closed(tmp_path: Path) -> None:
    _write_release(tmp_path)
    keyring_path = tmp_path / "RELEASE_KEYS.json"
    keyring = json.loads(keyring_path.read_text(encoding="utf-8"))
    keyring["keys"].append(dict(keyring["keys"][0]))
    keyring_path.write_bytes(rfc8785.dumps(cast("Any", keyring)))

    with pytest.raises(ReleaseProvenanceError, match="duplicate key_id"):
        _load_release(tmp_path)


def test_malformed_signature_key_id_fails_closed_without_type_error(tmp_path: Path) -> None:
    _write_release(tmp_path)
    index_path = tmp_path / "release-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["signatures"][0]["key_id"] = ["release-test-1"]
    index_path.write_bytes(rfc8785.dumps(cast("Any", index)))

    with pytest.raises(ReleaseProvenanceError, match="signature key_id is invalid"):
        _load_release(tmp_path)


def test_ambiguous_release_keyring_location_fails_closed(tmp_path: Path) -> None:
    benchmark_dir = tmp_path / "repository" / "benchmark"
    _write_release(benchmark_dir)
    repository_keyring = benchmark_dir.parent / "RELEASE_KEYS.json"
    repository_keyring.write_bytes((benchmark_dir / "RELEASE_KEYS.json").read_bytes())

    with pytest.raises(ReleaseProvenanceError, match="location is ambiguous"):
        _load_release(benchmark_dir)


def test_repository_release_keyring_location_verifies(tmp_path: Path) -> None:
    benchmark_dir = tmp_path / "repository" / "benchmark"
    _write_release(benchmark_dir)
    (benchmark_dir / "RELEASE_KEYS.json").replace(benchmark_dir.parent / "RELEASE_KEYS.json")

    _load_release(benchmark_dir)


def test_complete_release_chain_verifies_and_persists_highest_head(tmp_path: Path) -> None:
    _, indexes = _write_release(tmp_path / "benchmark", chain_length=2)
    state_path = tmp_path / "durable-state" / "release-head.json"
    genesis_sha256 = _document_sha256(indexes[0])

    _load_release(
        tmp_path / "benchmark",
        acceptance_state_path=state_path,
        trusted_genesis_sha256=genesis_sha256,
    )

    raw_state = state_path.read_bytes()
    state = json.loads(raw_state)
    assert raw_state == rfc8785.dumps(cast("Any", state))
    assert state == {
        "schema_version": "1.0",
        "channel": "gloss-v1-stable",
        "trusted_genesis_sha256": genesis_sha256,
        "sequence": 2,
        "release_index_sha256": _document_sha256(indexes[1]),
    }
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600


def test_complete_release_chain_conforms_to_published_schema(tmp_path: Path) -> None:
    _write_release(tmp_path, chain_length=2)
    chain = json.loads((tmp_path / "release-index-chain.json").read_text(encoding="utf-8"))
    chain_schema = json.loads(
        (SCHEMAS / "release-index-chain.schema.json").read_text(encoding="utf-8")
    )
    index_schema = json.loads((SCHEMAS / "release-index.schema.json").read_text(encoding="utf-8"))
    registry = Registry().with_resource(index_schema["$id"], Resource.from_contents(index_schema))

    Draft202012Validator(chain_schema, registry=registry).validate(chain)


def test_multi_index_bootstrap_requires_configured_trusted_genesis(tmp_path: Path) -> None:
    _write_release(tmp_path, chain_length=2)

    with pytest.raises(ReleaseProvenanceError, match="trusted genesis is required"):
        _load_release(tmp_path)


def test_default_acceptance_state_is_durable_state_not_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    benchmark_dir = tmp_path / "benchmark"
    state_home = tmp_path / "state-home"
    cache_home = tmp_path / "cache-home"
    _write_release(benchmark_dir)
    monkeypatch.delenv("GLOSS_RELEASE_STATE_PATH", raising=False)
    monkeypatch.delenv("GLOSS_TRUSTED_GENESIS_SHA256", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))

    load_signed_release_provenance(
        benchmark_dir,
        verification_time=datetime(2026, 7, 18, 13, 0, tzinfo=UTC),
    )

    assert (state_home / "gloss" / "release-head-v1.json").is_file()
    assert not cache_home.exists()


def test_configured_trusted_genesis_mismatch_fails_closed(tmp_path: Path) -> None:
    _write_release(tmp_path, chain_length=2)

    with pytest.raises(ReleaseProvenanceError, match="configured trusted genesis"):
        _load_release(tmp_path, trusted_genesis_sha256=f"sha256:{'f' * 64}")


def test_release_chain_gap_fails_closed(tmp_path: Path) -> None:
    private_key, indexes = _write_release(tmp_path, chain_length=2)
    unsigned_head = dict(indexes[1])
    unsigned_head.pop("signatures")
    unsigned_head["sequence"] = 3
    indexes[1] = _sign_index(private_key, unsigned_head)
    _write_indexes(tmp_path, indexes)

    with pytest.raises(ReleaseProvenanceError, match="sequence gap"):
        _load_release(
            tmp_path,
            trusted_genesis_sha256=_document_sha256(indexes[0]),
        )


def test_release_chain_wrong_previous_hash_fails_closed(tmp_path: Path) -> None:
    private_key, indexes = _write_release(tmp_path, chain_length=2)
    unsigned_head = dict(indexes[1])
    unsigned_head.pop("signatures")
    unsigned_head["previous_release_index_sha256"] = f"sha256:{'0' * 64}"
    indexes[1] = _sign_index(private_key, unsigned_head)
    _write_indexes(tmp_path, indexes)

    with pytest.raises(ReleaseProvenanceError, match="previous hash"):
        _load_release(
            tmp_path,
            trusted_genesis_sha256=_document_sha256(indexes[0]),
        )


def test_release_chain_state_cannot_move_backward(tmp_path: Path) -> None:
    private_key, indexes = _write_release(tmp_path, chain_length=2)
    unsigned_genesis = dict(indexes[0])
    unsigned_genesis.pop("signatures")
    unsigned_genesis["state"] = "frozen"
    indexes[0] = _sign_index(private_key, unsigned_genesis)
    unsigned_head = dict(indexes[1])
    unsigned_head.pop("signatures")
    unsigned_head["previous_release_index_sha256"] = _document_sha256(indexes[0])
    indexes[1] = _sign_index(private_key, unsigned_head)
    _write_indexes(tmp_path, indexes)

    with pytest.raises(ReleaseProvenanceError, match="state moves backward"):
        _load_release(
            tmp_path,
            trusted_genesis_sha256=_document_sha256(indexes[0]),
        )


def test_release_chain_rejects_premature_effective_head(tmp_path: Path) -> None:
    private_key, indexes = _write_release(tmp_path, chain_length=2)
    unsigned_head = dict(indexes[1])
    unsigned_head.pop("signatures")
    unsigned_head["issued_at"] = "2026-07-18T12:59:00Z"
    unsigned_head["effective_at"] = "2026-07-18T13:01:00Z"
    indexes[1] = _sign_index(private_key, unsigned_head)
    _write_indexes(tmp_path, indexes)

    with pytest.raises(ReleaseProvenanceError, match="not effective yet"):
        _load_release(
            tmp_path,
            trusted_genesis_sha256=_document_sha256(indexes[0]),
        )


def test_release_chain_rejects_future_issued_head_outside_clock_skew(tmp_path: Path) -> None:
    private_key, indexes = _write_release(tmp_path, chain_length=2)
    unsigned_head = dict(indexes[1])
    unsigned_head.pop("signatures")
    unsigned_head["issued_at"] = "2026-07-18T13:06:00Z"
    unsigned_head["effective_at"] = "2026-07-18T13:06:00Z"
    indexes[1] = _sign_index(private_key, unsigned_head)
    _write_indexes(tmp_path, indexes)

    with pytest.raises(ReleaseProvenanceError, match="clock-skew bound"):
        _load_release(
            tmp_path,
            trusted_genesis_sha256=_document_sha256(indexes[0]),
        )


def test_release_chain_verifies_every_historical_signature(tmp_path: Path) -> None:
    _, indexes = _write_release(tmp_path, chain_length=2)
    indexes[0]["signatures"][0]["signature_base64"] = base64.b64encode(b"\0" * 64).decode()
    _write_indexes(tmp_path, indexes)

    with pytest.raises(ReleaseProvenanceError, match="no valid signature"):
        _load_release(
            tmp_path,
            trusted_genesis_sha256=_document_sha256(indexes[0]),
        )


def test_packaged_release_index_must_equal_chain_head(tmp_path: Path) -> None:
    _, indexes = _write_release(tmp_path, chain_length=2)
    (tmp_path / "release-index.json").write_bytes(rfc8785.dumps(cast("Any", indexes[0])))

    with pytest.raises(ReleaseProvenanceError, match="packaged chain head"):
        _load_release(
            tmp_path,
            trusted_genesis_sha256=_document_sha256(indexes[0]),
        )


def test_persisted_head_rejects_same_sequence_fork(tmp_path: Path) -> None:
    private_key, indexes = _write_release(tmp_path / "benchmark", chain_length=2)
    state_path = tmp_path / "durable-state" / "release-head.json"
    genesis_sha256 = _document_sha256(indexes[0])
    _load_release(
        tmp_path / "benchmark",
        acceptance_state_path=state_path,
        trusted_genesis_sha256=genesis_sha256,
    )
    alternate_head = dict(indexes[1])
    alternate_head.pop("signatures")
    alternate_head["issued_at"] = "2026-07-18T12:10:01Z"
    alternate_head["effective_at"] = "2026-07-18T12:15:01Z"
    indexes[1] = _sign_index(private_key, alternate_head)
    _write_indexes(tmp_path / "benchmark", indexes)

    with pytest.raises(ReleaseProvenanceError, match="fork at the persisted sequence"):
        _load_release(
            tmp_path / "benchmark",
            acceptance_state_path=state_path,
            trusted_genesis_sha256=genesis_sha256,
        )


def test_cache_clearing_does_not_authorize_persisted_head_rollback(tmp_path: Path) -> None:
    _, indexes = _write_release(tmp_path / "benchmark", chain_length=2)
    state_path = tmp_path / "durable-state" / "release-head.json"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_marker = cache_dir / "ephemeral-state"
    cache_marker.write_text("not authoritative", encoding="utf-8")
    genesis_sha256 = _document_sha256(indexes[0])
    _load_release(
        tmp_path / "benchmark",
        acceptance_state_path=state_path,
        trusted_genesis_sha256=genesis_sha256,
    )
    cache_marker.unlink()
    cache_dir.rmdir()
    _write_indexes(tmp_path / "benchmark", indexes[:1])

    with pytest.raises(ReleaseProvenanceError, match="rollback is prohibited"):
        _load_release(
            tmp_path / "benchmark",
            acceptance_state_path=state_path,
            trusted_genesis_sha256=genesis_sha256,
        )
