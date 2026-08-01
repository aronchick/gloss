from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from gloss.package_hash import (
    PackageHashError,
    PackageHashProfileMismatchError,
    canonical_package_sha256,
    detect_gold_copy,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "benchmark" / "fixtures" / "package-hash" / "gold-copy-rejection-v1.json"
PROFILE = ROOT / "schemas" / "canonical-package-hash-v1.json"
MCE_PROFILE = ROOT / "schemas" / "mce-profile-v1.json"
ROOT_MAP = ROOT / "schemas" / "schema-root-map-v1.json"
REFERENCE_DECK = ROOT / "benchmark" / "deck" / "gold" / "gloss-v1-gold.pptx"


def _write_zip(path: Path, parts: dict[str, bytes], *, reverse: bool = False) -> None:
    names = sorted(parts, reverse=reverse)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as package:
        for index, name in enumerate(names):
            info = zipfile.ZipInfo(name, date_time=(2020 + index, 1, 2, 3, 4, 6))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o600 + index) << 16
            package.writestr(info, parts[name])


def _parts() -> dict[str, bytes]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {name: base64.b64decode(data) for name, data in fixture["gold_parts"].items()}


def test_gold_copy_fixture_covers_exact_repacked_and_mutated_cases(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parts = _parts()
    gold = tmp_path / "gold.pptx"
    _write_zip(gold, parts)
    expected_byte = hashlib.sha256(gold.read_bytes()).hexdigest()
    expected_package = canonical_package_sha256(gold, PROFILE)

    assert expected_package == fixture["expected_canonical_sha256"]
    for case in fixture["cases"]:
        candidate = tmp_path / f"{case['id']}.pptx"
        candidate_parts = dict(parts)
        if case["recipe"] == "exact_bytes":
            candidate.write_bytes(gold.read_bytes())
        elif case["recipe"] == "repacked":
            _write_zip(candidate, candidate_parts, reverse=True)
        elif case["recipe"] == "volatile_core_changed":
            candidate_parts["docProps/core.xml"] = (
                candidate_parts["docProps/core.xml"]
                .replace(b"2026-07-18T00:00:00Z", b"2040-01-01T00:00:00Z")
                .replace(b">1</cp:revision>", b">999</cp:revision>")
            )
            _write_zip(candidate, candidate_parts, reverse=True)
        else:
            candidate_parts["ppt/presentation.xml"] = candidate_parts[
                "ppt/presentation.xml"
            ].replace(b"<p:sldIdLst/>", b'<p:sldIdLst show="changed"/>')
            _write_zip(candidate, candidate_parts, reverse=True)

        decision = detect_gold_copy(
            candidate,
            gold_byte_sha256=expected_byte,
            gold_canonical_package_sha256=expected_package,
            expected_package_hash_profile_sha256=sha256_file(PROFILE),
            expected_mce_profile_sha256=sha256_file(MCE_PROFILE),
            expected_schema_root_map_sha256=sha256_file(ROOT_MAP),
            profile_path=PROFILE,
            mce_profile_path=MCE_PROFILE,
            root_map_path=ROOT_MAP,
        )
        assert decision.byte_match is case["expect_byte_match"]
        assert decision.canonical_package_match is case["expect_package_match"]
        assert (decision.reason or "not_a_gold_copy") == case["expected_decision"]

    with pytest.raises(PackageHashProfileMismatchError, match="MCE"):
        detect_gold_copy(
            gold,
            gold_byte_sha256=expected_byte,
            gold_canonical_package_sha256=expected_package,
            expected_package_hash_profile_sha256=sha256_file(PROFILE),
            expected_mce_profile_sha256="0" * 64,
            expected_schema_root_map_sha256=sha256_file(ROOT_MAP),
            profile_path=PROFILE,
            mce_profile_path=MCE_PROFILE,
            root_map_path=ROOT_MAP,
        )


def test_canonical_profile_covers_reference_deck_content_types() -> None:
    """The published profile must cover normal parts emitted by the reference authoring path."""
    assert REFERENCE_DECK.is_file()
    assert len(canonical_package_sha256(REFERENCE_DECK, PROFILE)) == 64


def test_package_hash_rejects_duplicate_and_unsafe_part_names(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.pptx"
    with zipfile.ZipFile(duplicate, "w") as package:
        package.writestr("ppt/presentation.xml", b"one")
        with pytest.warns(UserWarning, match="Duplicate name"):
            package.writestr("ppt/presentation.xml", b"two")
    with pytest.raises(PackageHashError, match="Duplicate"):
        canonical_package_sha256(duplicate, PROFILE)

    unsafe = tmp_path / "unsafe.pptx"
    with zipfile.ZipFile(unsafe, "w") as package:
        package.writestr("../escape.xml", b"bad")
    with pytest.raises(PackageHashError, match="Unsafe"):
        canonical_package_sha256(unsafe, PROFILE)
