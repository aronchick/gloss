from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from acidslide_service.config import Settings
from acidslide_service.quarantine_handoff import encode_public_key, utc_text


def _digest(seed: str) -> str:
    return f"sha256:{hashlib.sha256(seed.encode()).hexdigest()}"


def _production_attestation(
    *,
    oci_image_digest: str,
    grader_source_tree_sha256: str,
    font_manifest_sha256: str,
    schema_bundle_sha256: str,
    schema_root_map_sha256: str,
    mce_profile_sha256: str,
    canonical_package_hash_profile_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "attestation_id": "acidslide-environment-attestation-v1",
        "canonicalization": "RFC8785-JCS",
        "attestation_state": "verified",
        "attested_at": "2026-07-18T00:00:00Z",
        "platform": "linux/amd64",
        "oci_image_digest": oci_image_digest,
        "build_inputs": {
            "dockerfile_sha256": _digest("dockerfile"),
            "grader_lockfile_sha256": _digest("grader-lockfile"),
            "base_image_digest": _digest("base-image"),
            "uv_image_digest": _digest("uv-image"),
        },
        "runtime_versions": {
            name: "1.0.0"
            for name in (
                "libreoffice",
                "poppler",
                "python",
                "pillow",
                "numpy",
                "scikit_image",
                "lxml",
                "grader",
                "libfaketime",
                "fontconfig",
            )
        },
        "binary_inventory": [
            {"name": name, "path": f"/usr/bin/{name}", "sha256": _digest(name)}
            for name in ("fontconfig", "libfaketime", "libreoffice", "pdftoppm", "python")
        ],
        "font_environment": {
            "fontconfig_file": "/etc/fonts/fonts.conf",
            "fontconfig_config_sha256": _digest("fontconfig"),
            "font_manifest_sha256": font_manifest_sha256,
            "discovered_fonts": [
                {
                    "path": "/usr/share/fonts/test.ttf",
                    "sha256": _digest("test-font"),
                }
            ],
            "exact_manifest_match": True,
        },
        "process_environment": {
            "FAKETIME": "@2025-01-01 00:00:00",
            "FAKETIME_DONT_FAKE_MONOTONIC": "1",
            "FAKETIME_NO_CACHE": "1",
            "LD_PRELOAD": "/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1",
            "TZ": "UTC",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
        },
        "export_contract": {
            "libreoffice_command": [
                "libreoffice",
                "--headless",
                "-env:UserInstallation=file://<isolated-temporary-profile>",
                "--convert-to",
                "pdf",
                "--outdir",
                "/work",
                "/input/submission.pptx",
            ],
            "pdftoppm_command": [
                "pdftoppm",
                "-png",
                "-scale-to-x",
                "1920",
                "-scale-to-y",
                "1080",
                "/work/submission.pdf",
                "/work/acidslide-render",
            ],
            "presentation_size_emu": {"cx": 12192000, "cy": 6858000},
            "allowed_page_counts": [5, 12, 20],
            "width_px": 1920,
            "height_px": 1080,
            "color_mode": "RGB",
            "reference_datetime": "2025-01-01T00:00:00Z",
            "pdf_page_geometry": {
                "numeric_parser": "exact-decimal-string",
                "media_box": ["0", "0", "960.009448818898", "540"],
                "crop_box": "absent-or-exactly-equal-to-media-box",
                "rotate": "absent-or-zero",
            },
        },
        "profile_hashes": {
            "export_profile_sha256": _digest("export-profile"),
            "png_profile_sha256": _digest("png-profile"),
            "ssim_profile_sha256": _digest("ssim-profile"),
            "json_schema_bundle_sha256": _digest("json-schema"),
            "xsd_bundle_sha256": schema_bundle_sha256,
            "schema_root_map_sha256": schema_root_map_sha256,
            "mce_profile_sha256": mce_profile_sha256,
            "scene_graph_profile_sha256": _digest("scene-graph-profile"),
            "canonical_package_hash_profile_sha256": (canonical_package_hash_profile_sha256),
        },
        "grader_source_tree_sha256": grader_source_tree_sha256,
        "canary": {
            "canary_id": "release-canary-v1",
            "input_sha256": _digest("canary-input"),
            "score_semantic_report_sha256": _digest("canary-report"),
        },
        "verification": {
            "architecture_verified": True,
            "binary_hashes_verified": True,
            "font_inventory_verified": True,
            "clock_fixture_verified": True,
            "network_disabled_verified": True,
        },
    }


def test_production_refuses_unsafe_defaults() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(app_env="production")
    message = str(error.value)
    assert "PostgreSQL" in message
    assert "GRADER_IMAGE_DIGEST" in message
    assert "development key" in message
    assert "ENVIRONMENT_ATTESTATION_JSON must hash" in message
    assert "ACTIVE_GRADER_PACKAGE_SHA256" in message


def test_isolated_container_uids_match_the_canonical_images() -> None:
    settings = Settings(_env_file=None)
    assert settings.grader_uid == 10001
    assert settings.quarantine_uid == 10001


def test_environment_attestation_must_be_a_json_object() -> None:
    with pytest.raises(ValidationError, match="must contain a JSON object"):
        Settings(environment_attestation_json="[]")


def test_schema_valid_frozen_production_configuration_is_accepted() -> None:
    oci_image_digest = _digest("official-image")
    grader_source_tree_sha256 = _digest("grader-source")
    font_manifest_sha256 = _digest("font-manifest")
    schema_bundle_sha256 = _digest("xsd-bundle")
    schema_root_map_sha256 = _digest("schema-root-map")
    mce_profile_sha256 = _digest("mce-profile")
    canonical_profile_sha256 = _digest("canonical-package-profile")
    attestation = _production_attestation(
        oci_image_digest=oci_image_digest,
        grader_source_tree_sha256=grader_source_tree_sha256,
        font_manifest_sha256=font_manifest_sha256,
        schema_bundle_sha256=schema_bundle_sha256,
        schema_root_map_sha256=schema_root_map_sha256,
        mce_profile_sha256=mce_profile_sha256,
        canonical_package_hash_profile_sha256=canonical_profile_sha256,
    )
    attestation_sha256 = f"sha256:{hashlib.sha256(rfc8785.dumps(attestation)).hexdigest()}"
    quarantine_key = Ed25519PrivateKey.generate()
    now = datetime.now(UTC)
    verification_keys = json.dumps(
        {
            "production-key": {
                "public_key": encode_public_key(quarantine_key.public_key()),
                "not_before": utc_text(now - timedelta(days=1)),
                "not_after": utc_text(now + timedelta(days=1)),
                "revoked_at": None,
            }
        }
    )

    settings = Settings(
        app_env="production",
        database_url="postgresql+psycopg://service@db/acidslide",
        public_base_url="https://acidslide.dev",
        admin_api_key="a" * 40,
        api_key_pepper="p" * 40,
        encryption_key="qQ_1yAQvQABKVF1vpj6AEuM9UgGPy0L7GtJ2y6kODGc=",
        grader_image_digest=oci_image_digest,
        quarantine_image_digest=_digest("quarantine-image"),
        active_scoring_manifest_sha256=_digest("scoring-manifest"),
        active_grader_source_tree_sha256=grader_source_tree_sha256,
        active_environment_attestation_sha256=attestation_sha256,
        environment_attestation_json=json.dumps(attestation),
        active_grader_package_sha256=_digest("grader-package"),
        active_prompt_bundle_sha256=_digest("prompt-bundle"),
        active_scored_assertion_inventory_sha256=_digest("assertion-inventory"),
        active_checklist_bundle_sha256=_digest("checklist-bundle"),
        active_quarantine_profile_sha256=_digest("quarantine-profile"),
        active_mce_profile_sha256=mce_profile_sha256,
        active_schema_bundle_sha256=schema_bundle_sha256,
        active_schema_root_map_sha256=schema_root_map_sha256,
        active_canonical_package_hash_profile_sha256=canonical_profile_sha256,
        active_gold_byte_sha256=_digest("gold-original"),
        active_gold_mce_resolved_package_sha256=_digest("gold-resolved"),
        active_gold_canonical_package_sha256=_digest("gold-canonical"),
        font_bundle_hash=font_manifest_sha256,
        asset_manifest_hash=_digest("asset-manifest"),
        quarantine_verification_keys_json=verification_keys,
    )

    assert settings.environment_attestation == attestation
    assert settings.active_environment_attestation_sha256 == attestation_sha256


def test_production_refuses_test_runner() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://service@db/acidslide",
            public_base_url="https://acidslide.dev",
            admin_api_key="a" * 40,
            api_key_pepper="p" * 40,
            encryption_key="qQ_1yAQvQABKVF1vpj6AEuM9UgGPy0L7GtJ2y6kODGc=",
            grader_image_digest="sha256:" + "a" * 64,
            allow_insecure_test_runner=True,
        )
    assert "ALLOW_INSECURE_TEST_RUNNER" in str(error.value)
