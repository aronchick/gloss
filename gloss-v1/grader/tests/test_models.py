"""Tests for machine-readable and human-readable grade reports."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import jsonschema
import rfc8785

from gloss.models import (
    DisqualificationState,
    GoldDuplicateCheck,
    GradeReport,
    GradingMode,
    RunKind,
    StableError,
)

SHA = {index: f"sha256:{str(index) * 64}" for index in range(10)}


def _environment_attestation() -> dict[str, Any]:
    versions = {
        name: "test-1.0"
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
    }
    return {
        "schema_version": "1.0",
        "attestation_id": "gloss-environment-attestation-v1",
        "canonicalization": "RFC8785-JCS",
        "attestation_state": "verified",
        "attested_at": "2026-07-18T12:00:00Z",
        "platform": "linux/amd64",
        "oci_image_digest": SHA[1],
        "build_inputs": {
            "dockerfile_sha256": SHA[2],
            "grader_lockfile_sha256": SHA[3],
            "base_image_digest": SHA[4],
            "uv_image_digest": SHA[5],
        },
        "runtime_versions": versions,
        "binary_inventory": [
            {"name": name, "path": f"/usr/bin/{name}", "sha256": SHA[index]}
            for index, name in enumerate(
                ("libreoffice", "pdftoppm", "python", "fontconfig", "libfaketime"), start=2
            )
        ],
        "font_environment": {
            "fontconfig_file": "/etc/fonts/fonts.conf",
            "fontconfig_config_sha256": SHA[6],
            "font_manifest_sha256": SHA[7],
            "discovered_fonts": [{"path": "/fonts/Test.ttf", "sha256": SHA[8]}],
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
                "/work/gloss-render",
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
            "export_profile_sha256": SHA[1],
            "png_profile_sha256": SHA[2],
            "ssim_profile_sha256": SHA[3],
            "json_schema_bundle_sha256": SHA[4],
            "xsd_bundle_sha256": SHA[5],
            "schema_root_map_sha256": SHA[6],
            "mce_profile_sha256": SHA[7],
            "scene_graph_profile_sha256": SHA[9],
            "canonical_package_hash_profile_sha256": SHA[8],
        },
        "grader_source_tree_sha256": SHA[2],
        "canary": {
            "canary_id": "grader-test-canary",
            "input_sha256": SHA[8],
            "score_semantic_report_sha256": SHA[9],
        },
        "verification": {
            "architecture_verified": True,
            "binary_hashes_verified": True,
            "font_inventory_verified": True,
            "clock_fixture_verified": True,
            "network_disabled_verified": True,
        },
    }


def _report() -> GradeReport:
    environment_attestation = _environment_attestation()
    environment_hash = (
        f"sha256:{hashlib.sha256(rfc8785.dumps(environment_attestation)).hexdigest()}"
    )
    return GradeReport(
        benchmark_version="gloss-v1.0.0",
        grader_version="1.0.0a1",
        scoring_cohort_id=SHA[0],
        scoring_manifest_sha256=SHA[1],
        grader_source_tree_sha256=SHA[2],
        environment_attestation_sha256=environment_hash,
        grader_package_sha256=SHA[4],
        oci_image_digest=SHA[1],
        prompt_bundle_sha256=SHA[5],
        scored_assertion_inventory_sha256=SHA[6],
        checklist_bundle_sha256=SHA[7],
        schema_bundle_sha256=SHA[8],
        schema_root_map_sha256=SHA[6],
        mce_profile_sha256=SHA[7],
        asset_manifest_sha256=SHA[8],
        font_manifest_sha256=SHA[7],
        grading_mode=GradingMode.HOSTED,
        run_kind=RunKind.SUBMISSION,
        canonical_package_hash_profile_sha256=SHA[8],
        canonical_package_hash_v1=SHA[9],
        gold_duplicate_check=GoldDuplicateCheck.CLEAR,
        generation_seed=None,
        submission_id="00000000-0000-4000-8000-000000000001",
        campaign_id="00000000-0000-4000-8000-000000000002",
        campaign_slot=1,
        robustness_group_id=None,
        submitter_id="00000000-0000-4000-8000-000000000003",
        model_key="00000000-0000-4000-8000-000000000004",
        model_revision_key="00000000-0000-4000-8000-000000000005",
        targeted_tier=1,
        prompt_variant="canonical",
        assistance_class="unassisted",
        generation_profile_sha256=SHA[4],
        submission_sha256=SHA[5],
        mce_resolved_package_sha256=SHA[6],
        gold_submission_sha256=SHA[7],
        gold_mce_resolved_package_sha256=SHA[8],
        gold_canonical_package_hash_v1=SHA[9],
        schema_valid=False,
        schema_validation_performed=True,
        visual_verification_performed=False,
        verification_complete=False,
        scoring_completed=False,
        disqualification_state=DisqualificationState.COMPLETED_INELIGIBLE,
        ineligibility_reasons=["schema_validation_failed", "verification_incomplete"],
        repair_triggered=False,
        grading_duration_seconds=0.0,
        fidelity_score=None,
        campaign_contribution=0.0,
        passed_items=0,
        total_items=0,
        deck_passed=False,
        eligible=False,
        tier_scores={"level_1": None, "level_2": None, "level_3": None},
        schema_violations=[
            StableError(
                "schema_violation",
                part="ppt/slides/slide1.xml",
                details="element <missing>",
            )
        ],
        verification_errors=[
            StableError("schema_validation_failed", details='<script>alert("x")</script>')
        ],
        environment_attestation=environment_attestation,
        verified_metrics={
            "submission_file_size_bytes": 123,
            "grading_duration_seconds": 0.0,
            "schema_valid": False,
            "schema_validation_performed": True,
            "visual_verification_performed": False,
            "verification_complete": False,
            "renderer_version": "unavailable",
        },
        attested_metrics={"generation_strategy": "direct"},
        attestation={
            "method": "artifact-upload",
            "human_intervention": False,
            "post_processing": False,
            "external_resources_used": False,
        },
    )


def _schema(name: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "schemas" / name
    schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return schema


def test_json_contains_verification_provenance() -> None:
    payload = json.loads(_report().to_json())

    assert payload["run_kind"] == "submission"
    assert payload["grading_mode"] == "hosted"
    assert payload["verification_scope"] == "artifact_conformance"
    assert payload["verification_label"] == ("grading-verified artifact score; generation-attested")
    assert payload["schema_validation_performed"] is True
    assert payload["visual_verification_performed"] is False
    assert payload["verification_complete"] is False
    assert payload["verification_errors"][0]["code"] == "schema_validation_failed"


def test_json_conforms_to_normative_report_schema() -> None:
    payload = json.loads(_report().to_json())
    schema = _schema("report.schema.json")
    schema["properties"]["environment_attestation"] = _schema("environment-attestation.schema.json")

    jsonschema.Draft202012Validator(schema).validate(payload)


def test_semantic_projection_conforms_and_hashes_jcs_bytes() -> None:
    report = _report()
    projection = report.semantic_projection()

    jsonschema.Draft202012Validator(_schema("report-semantic-projection.schema.json")).validate(
        projection
    )
    expected = f"sha256:{hashlib.sha256(rfc8785.dumps(projection)).hexdigest()}"
    assert report.score_semantic_report_sha256 == expected


def test_semantic_projection_excludes_diagnostic_details_but_not_outcomes() -> None:
    report = _report()
    changed_details = replace(
        report,
        grading_duration_seconds=9.5,
        verification_errors=[
            StableError("schema_validation_failed", details="different private diagnostic")
        ],
    )
    changed_outcome = replace(
        report,
        verification_errors=[StableError("artifact_renderer_failure")],
    )

    assert changed_details.score_semantic_report_sha256 == report.score_semantic_report_sha256
    assert changed_outcome.score_semantic_report_sha256 != report.score_semantic_report_sha256


def test_html_escapes_untrusted_report_content() -> None:
    rendered = _report().to_html()

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_summary_labels_incomplete_reports() -> None:
    rendered = _report().summary()

    assert "INCOMPLETE" in rendered
    assert "grading-verified artifact score; generation-attested" in rendered
    assert "Leaderboard eligible: False" in rendered
