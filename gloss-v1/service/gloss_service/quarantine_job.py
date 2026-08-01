"""Disposable Stage 0/0.5 quarantine job entrypoint.

This module is intentionally never imported by the API/control-plane module.
It is the process that first opens attacker-controlled ZIP and XML content.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from gloss.mce import load_understood_namespaces, preprocess_markup_compatibility
from gloss.package_hash import PackageHashError, canonical_package_identity
from gloss.resources import resolve_normative_schema_file, resolve_schema_dir
from gloss.schema_validate import validate_schema
from lxml import etree

from gloss_service.config import Settings
from gloss_service.quarantine import inspect_pptx
from gloss_service.quarantine_handoff import (
    ObjectBinding,
    QuarantineJobBinding,
    build_payload,
    jcs_bytes,
    load_private_key,
    sha256_id,
    sign_payload,
)
from gloss_service.storage import hash_file


class QuarantineJobError(RuntimeError):
    pass


def _xml_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
        huge_tree=False,
        remove_blank_text=False,
    )


def _is_mce_part(name: str) -> bool:
    return name.startswith("ppt/") and name.endswith(".xml") and "/_rels/" not in name


def _resolved_xml(data: bytes, understood: set[str]) -> bytes:
    root = etree.fromstring(data, parser=_xml_parser())
    preprocess_markup_compatibility(root, understood, preserved_evidence=[])
    return etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=False,
    )


def write_resolved_package(original: Path, resolved: Path) -> None:
    """Write the deterministic MCE-resolved package consumed by every later stage."""
    understood = load_understood_namespaces()
    with (
        zipfile.ZipFile(original, "r") as source,
        zipfile.ZipFile(
            resolved,
            "x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as destination,
    ):
        members = {info.filename: info for info in source.infolist()}
        if len(members) != len(source.infolist()):
            raise QuarantineJobError("Duplicate ZIP member names are forbidden")
        for name in sorted(members):
            info = members[name]
            data = source.read(info)
            if _is_mce_part(name):
                data = _resolved_xml(data, understood)
            normalized = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            normalized.compress_type = zipfile.ZIP_DEFLATED
            normalized.create_system = 3
            normalized.external_attr = (0o100400 & 0xFFFF) << 16
            normalized.flag_bits = 0
            destination.writestr(
                normalized,
                data,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    os.chmod(resolved, 0o600)


def _file_sha256(path: Path) -> str:
    return sha256_id(path.read_bytes())


@lru_cache(maxsize=4)
def _schema_bundle_sha256(schema_dir: Path) -> str:
    inventory = [
        {
            "path": str(path.relative_to(schema_dir)),
            "sha256": _file_sha256(path),
        }
        for path in sorted(schema_dir.rglob("*.xsd"))
        if path.is_file()
    ]
    if not inventory:
        raise QuarantineJobError("The ECMA-376 schema bundle is empty")
    return sha256_id(jcs_bytes(inventory))


def quarantine_profile_sha256(settings: Settings) -> str:
    profile = {
        "dangerous_extensions": sorted(
            [
                ".app",
                ".bat",
                ".cmd",
                ".com",
                ".dll",
                ".dylib",
                ".exe",
                ".jar",
                ".js",
                ".msi",
                ".ps1",
                ".py",
                ".scr",
                ".sh",
                ".so",
                ".vbs",
            ]
        ),
        "max_decompression_ratio": settings.max_decompression_ratio,
        "max_uncompressed_bytes": settings.max_uncompressed_bytes,
        "max_upload_bytes": settings.max_upload_bytes,
        "max_zip_entries": settings.max_zip_entries,
        "profile_id": "gloss-quarantine-profile-v1",
        "reject_active_content": True,
        "embedded_spreadsheet_policy": "safe-ooxml-chart-workbooks-only",
        "reject_encrypted_entries": True,
        "reject_external_relationships": True,
        "reject_unapproved_nested_archives": True,
        "reject_ole": True,
    }
    return sha256_id(jcs_bytes(profile))


def normative_profile_hashes(settings: Settings) -> dict[str, str]:
    mce_profile = resolve_normative_schema_file("mce-profile-v1.json")
    root_map = resolve_normative_schema_file("schema-root-map-v1.json")
    package_hash_profile = resolve_normative_schema_file("canonical-package-hash-v1.json")
    schema_dir = resolve_schema_dir()
    return {
        "canonical_package_hash_profile_sha256": _file_sha256(package_hash_profile),
        "mce_profile_sha256": _file_sha256(mce_profile),
        "quarantine_profile_sha256": quarantine_profile_sha256(settings),
        "schema_bundle_sha256": _schema_bundle_sha256(schema_dir),
        "schema_root_map_sha256": _file_sha256(root_map),
    }


def execute_quarantine_job(
    *,
    original_path: Path,
    resolved_path: Path,
    binding: QuarantineJobBinding,
    settings: Settings,
    private_key_value: str,
    key_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Inspect, resolve, XSD-validate, and sign one sandbox verdict."""
    issued_at = (now or datetime.now(UTC)).astimezone(UTC)
    expires_at = issued_at + timedelta(seconds=settings.quarantine_verdict_ttl_seconds)
    profiles = normative_profile_hashes(settings)
    actual_digest, actual_size = hash_file(original_path)
    outcome = "accepted"
    reason = ""
    resolved_binding: ObjectBinding | None = None
    canonical_package_hash_v1: str | None = None
    gold_duplicate_check: dict[str, Any] | None = None
    schema_validation: dict[str, Any] | None = None
    if (
        f"sha256:{actual_digest}" != binding.original.sha256
        or actual_size != binding.original.size_bytes
    ):
        outcome = "rejected"
        reason = "Original immutable object digest or size changed"
    else:
        result = inspect_pptx(original_path, binding.tier, settings)
        if not result.passed:
            outcome = "rejected"
            reason = result.reason
        else:
            try:
                write_resolved_package(original_path, resolved_path)
                resolved_digest, resolved_size = hash_file(resolved_path)
                resolved_binding = ObjectBinding(
                    object_version=binding.resolved_object_version,
                    sha256=f"sha256:{resolved_digest}",
                    size_bytes=resolved_size,
                )
                validation = validate_schema(resolved_path)
                schema_validation = {
                    "performed": validation.performed,
                    "valid": validation.valid,
                    "violations": validation.violations,
                }
                identity = canonical_package_identity(resolved_path)
                canonical_package_hash_v1 = f"sha256:{identity.canonical_package_sha256}"
                if (
                    f"sha256:{identity.package_hash_profile_sha256}"
                    != profiles["canonical_package_hash_profile_sha256"]
                ):
                    raise QuarantineJobError(
                        "Canonical package hash profile changed during quarantine"
                    )
                byte_match = f"sha256:{actual_digest}" == settings.active_gold_byte_sha256
                canonical_match = (
                    canonical_package_hash_v1 == settings.active_gold_canonical_package_sha256
                )
                gold_duplicate_check = {
                    "byte_match": byte_match,
                    "canonical_package_match": canonical_match,
                    "decision": (
                        "byte_match"
                        if byte_match
                        else "canonical_match"
                        if canonical_match
                        else "clear"
                    ),
                }
            except (PackageHashError, QuarantineJobError, etree.Error, ValueError) as exc:
                resolved_path.unlink(missing_ok=True)
                resolved_binding = None
                outcome = "rejected"
                reason = f"Stage 0.5 package resolution failed: {exc}"[:4000]

    payload = build_payload(
        verdict_id=str(uuid.uuid4()),
        key_id=key_id,
        outcome=outcome,  # type: ignore[arg-type]
        reason=reason,
        original=binding.original,
        resolved=resolved_binding,
        submission_id=binding.submission_id,
        campaign_id=binding.campaign_id,
        campaign_slot=binding.campaign_slot,
        quarantine_profile_sha256=profiles["quarantine_profile_sha256"],
        mce_profile_sha256=profiles["mce_profile_sha256"],
        schema_bundle_sha256=profiles["schema_bundle_sha256"],
        schema_root_map_sha256=profiles["schema_root_map_sha256"],
        canonical_package_hash_profile_sha256=profiles["canonical_package_hash_profile_sha256"],
        canonical_package_hash_v1=canonical_package_hash_v1,
        gold_duplicate_check=gold_duplicate_check,
        schema_validation=schema_validation,
        run_kind="submission",
        control_authorization_sha256=None,
        control_authorization_object_version=None,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return sign_payload(payload, load_private_key(private_key_value))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--resolved", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--verdict", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    args = parser.parse_args()
    binding_value = json.loads(args.binding.read_text(encoding="utf-8"))
    settings = Settings(_env_file=None)
    envelope = execute_quarantine_job(
        original_path=args.input,
        resolved_path=args.resolved,
        binding=QuarantineJobBinding.from_dict(binding_value),
        settings=settings,
        private_key_value=args.private_key.read_text(encoding="ascii").strip(),
        key_id=args.key_id,
    )
    args.verdict.write_bytes(jcs_bytes(envelope))
    os.chmod(args.verdict, 0o600)


if __name__ == "__main__":
    main()
