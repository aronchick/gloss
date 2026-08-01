#!/usr/bin/env python3
# ruff: noqa: E402
"""Build a frozen Gloss v1 scoring manifest or fail without writing one.

This command intentionally has no draft/placeholder mode. A manifest is a
release identity, so absent gold, exports, OCI identity, runtime attestation,
or grader package is an error rather than a field containing ``pending``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import rfc8785
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
GRADER = ROOT / "grader"
sys.path.insert(0, str(GRADER))

from gloss.package_hash import canonical_package_sha256, sha256_file
from gloss.profile_contract import (
    deterministic_tree_sha256,
    environment_profile_hashes,
    load_render_profiles,
)
from gloss.release_evidence import validate_export_determinism_evidence


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True, help="validated runtime freeze JSON")
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "benchmark" / "deck" / "gold" / "gloss-v1-gold.pptx",
    )
    parser.add_argument(
        "--gold-exports",
        type=Path,
        default=ROOT / "benchmark" / "deck" / "exports",
    )
    parser.add_argument(
        "--resolved-gold",
        type=Path,
        required=True,
        help="content-addressed Stage-0.5 MCE-resolved gold package",
    )
    parser.add_argument(
        "--gold-pdf",
        type=Path,
        required=True,
        help="canonical 20-page PDF retained from the frozen export run",
    )
    parser.add_argument(
        "--environment-attestation",
        type=Path,
        required=True,
        help="validated environment-attestation JSON reconstructed in the container",
    )
    parser.add_argument(
        "--export-determinism-evidence",
        type=Path,
        required=True,
        help="validated 100-run gold export determinism evidence",
    )
    parser.add_argument(
        "--grader-source-tree-manifest",
        type=Path,
        required=True,
        help="validated complete grader source-tree manifest",
    )
    parser.add_argument("--grader-package", type=Path, required=True, help="release wheel or sdist")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Required release artifact is missing: {path}")
    return f"sha256:{sha256_file(path)}"


def _tree_sha256(path: Path) -> str:
    return deterministic_tree_sha256(path)


def _load_validated(path: Path, schema_path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    registry = Registry()
    for candidate in sorted((ROOT / "schemas").glob("*.schema.json")):
        candidate_schema = json.loads(candidate.read_text(encoding="utf-8"))
        identifier = candidate_schema.get("$id")
        if isinstance(identifier, str):
            registry = registry.with_resource(identifier, Resource.from_contents(candidate_schema))
    jsonschema.Draft202012Validator(
        schema,
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    ).validate(document)
    return document


def _jcs_sha256(document: dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(rfc8785.dumps(document)).hexdigest()}"


class _EvidenceValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.notes: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def build_manifest(
    *,
    runtime_path: Path,
    gold_path: Path,
    gold_exports: Path,
    resolved_gold: Path,
    gold_pdf: Path,
    environment_attestation_path: Path,
    export_determinism_evidence_path: Path,
    grader_source_tree_manifest_path: Path,
    grader_package: Path,
) -> dict[str, Any]:
    """Return a fully resolved manifest; raise on any missing release input."""
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if version != "1.0.0":
        raise ValueError(f"VERSION must be exactly 1.0.0 for the v1 freeze, found {version!r}")
    runtime = _load_validated(
        runtime_path,
        ROOT / "schemas" / "runtime-freeze-input.schema.json",
    )
    environment_attestation = _load_validated(
        environment_attestation_path,
        ROOT / "schemas" / "environment-attestation.schema.json",
    )
    environment_attestation_sha256 = _jcs_sha256(environment_attestation)
    if environment_attestation_sha256 != runtime["environment_attestation_sha256"]:
        raise ValueError(
            "Runtime freeze environment_attestation_sha256 does not match the JCS attestation"
        )
    if runtime["platform"] != environment_attestation["platform"]:
        raise ValueError("Runtime freeze platform does not match the environment attestation")
    if runtime["oci_image_digest"] != environment_attestation["oci_image_digest"]:
        raise ValueError("Runtime freeze OCI digest does not match the environment attestation")
    runtime_versions = environment_attestation["runtime_versions"]
    for field in (
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
    ):
        if runtime[field] != runtime_versions[field]:
            raise ValueError(f"Runtime freeze {field} does not match the environment attestation")
    if (
        runtime["fontconfig_config_sha256"]
        != environment_attestation["font_environment"]["fontconfig_config_sha256"]
    ):
        raise ValueError(
            "Runtime freeze Fontconfig hash does not match the environment attestation"
        )
    libfaketime_records = [
        record
        for record in environment_attestation["binary_inventory"]
        if record["name"] == "libfaketime"
    ]
    if (
        len(libfaketime_records) != 1
        or runtime["libfaketime_library_sha256"] != libfaketime_records[0]["sha256"]
    ):
        raise ValueError(
            "Runtime freeze libfaketime library hash does not match the environment attestation"
        )
    determinism_evidence = _load_validated(
        export_determinism_evidence_path,
        ROOT / "schemas" / "export-determinism-evidence.schema.json",
    )
    source_tree_manifest = _load_validated(
        grader_source_tree_manifest_path,
        ROOT / "schemas" / "grader-source-tree-manifest.schema.json",
    )
    source_tree_sha256 = _jcs_sha256(source_tree_manifest)
    exports = sorted(gold_exports.glob("slide-??.png"))
    if len(exports) != 20 or [path.name for path in exports] != [
        f"slide-{number:02d}.png" for number in range(1, 21)
    ]:
        raise ValueError("Gold export tree must contain exactly slide-01.png through slide-20.png")

    schemas = ROOT / "schemas"
    benchmark = ROOT / "benchmark"
    oracle = benchmark / "requirements" / "prompt-requirements.json"
    scored_inventory = benchmark / "requirements" / "scored-assertion-inventory.json"
    oracle_document = _load_validated(oracle, schemas / "prompt-requirements.schema.json")
    if oracle_document.get("freeze_status") != "frozen":
        raise ValueError("Prompt requirements oracle must be frozen before building a manifest")
    if len(oracle_document.get("independent_reviews", [])) < 2:
        raise ValueError("Prompt requirements oracle requires two independent approvals")
    _load_validated(scored_inventory, schemas / "scored-assertion-inventory.schema.json")
    package_profile = schemas / "canonical-package-hash-v1.json"
    scene_graph_profile = schemas / "scene-graph-profile-v1.json"
    source_tree_profile = schemas / "grader-source-tree-profile-v1.json"
    export_contract = environment_attestation.get("export_contract")
    if not isinstance(export_contract, dict):
        raise ValueError("Environment attestation has no export contract")
    render_profiles = load_render_profiles(schemas)
    expected_environment_profiles = environment_profile_hashes(schemas)
    if environment_attestation.get("profile_hashes") != expected_environment_profiles:
        changed = sorted(
            key
            for key in set(expected_environment_profiles)
            | set(environment_attestation.get("profile_hashes", {}))
            if environment_attestation.get("profile_hashes", {}).get(key)
            != expected_environment_profiles.get(key)
        )
        raise ValueError(
            "Environment attestation has stale or substituted profile hashes: " + ", ".join(changed)
        )
    if export_contract != render_profiles.export_contract():
        raise ValueError("Environment attestation export contract differs from normative profiles")
    expected_source_tree_profile = _sha256(source_tree_profile)
    if source_tree_manifest.get("source_tree_profile_sha256") != expected_source_tree_profile:
        raise ValueError("Grader source-tree manifest is bound to the wrong profile hash")
    if environment_attestation.get("grader_source_tree_sha256") != source_tree_sha256:
        raise ValueError("Environment attestation is bound to the wrong grader source-tree hash")
    resolved_gold_sha256 = _sha256(resolved_gold)
    canonical_package_profile_sha256 = _sha256(package_profile)
    scene_graph_profile_sha256 = _sha256(scene_graph_profile)
    if (
        environment_attestation.get("profile_hashes", {}).get("scene_graph_profile_sha256")
        != scene_graph_profile_sha256
    ):
        raise ValueError("Environment attestation is bound to the wrong scene-graph profile")
    scene_graph_path = benchmark / "fixtures" / "expected-deck.json"
    scene_graph = _load_validated(scene_graph_path, schemas / "scene-graph.schema.json")
    if scene_graph.get("profile_sha256") != scene_graph_profile_sha256:
        raise ValueError("Gold scene graph is bound to the wrong extraction profile")
    if scene_graph.get("mce_resolved_package_sha256") != resolved_gold_sha256:
        raise ValueError("Gold scene graph was not extracted from the resolved gold package")
    if [slide.get("slide") for slide in scene_graph.get("slides", [])] != list(range(1, 21)):
        raise ValueError("Gold scene graph must contain slides exactly 1 through 20")
    canonical_png_sha256s = [_sha256(path) for path in exports]
    original_gold_sha256 = _sha256(gold_path)
    canonical_gold_pdf_sha256 = _sha256(gold_pdf)
    canonical_package_hash_v1 = f"sha256:{canonical_package_sha256(resolved_gold, package_profile)}"
    expected_determinism_bindings = {
        "environment_attestation_sha256": environment_attestation_sha256,
        "original_gold_sha256": original_gold_sha256,
        "resolved_gold_sha256": resolved_gold_sha256,
        "canonical_package_hash_profile_sha256": canonical_package_profile_sha256,
        "canonical_package_hash_v1": canonical_package_hash_v1,
        "canonical_pdf_sha256": canonical_gold_pdf_sha256,
        "canonical_png_sha256s": canonical_png_sha256s,
        "export_profile_sha256": environment_attestation.get("profile_hashes", {}).get(
            "export_profile_sha256"
        ),
        "ssim_profile_sha256": environment_attestation.get("profile_hashes", {}).get(
            "ssim_profile_sha256"
        ),
    }
    evidence_result = _EvidenceValidationResult()
    validate_export_determinism_evidence(
        evidence_result,
        determinism_evidence,
        expected_bindings=expected_determinism_bindings,
    )
    if evidence_result.errors:
        raise ValueError(
            "Invalid export determinism evidence: " + "; ".join(evidence_result.errors)
        )
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "manifest_id": "gloss-scoring-manifest-v1",
        "release_status": "frozen",
        "benchmark_version": "gloss-v1.0.0",
        "platform": runtime["platform"],
        "oci_image_digest": runtime["oci_image_digest"],
        "runtime": {
            key: runtime[key]
            for key in (
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
                "libfaketime_library_sha256",
                "fontconfig_config_sha256",
                "environment_attestation_sha256",
            )
        }
        | {
            "locale": "en_US.UTF-8",
            "timezone": "UTC",
            "reference_datetime": "2025-01-01T00:00:00Z",
            "faketime_environment": {
                "FAKETIME": "@2025-01-01 00:00:00",
                "FAKETIME_DONT_FAKE_MONOTONIC": "1",
                "FAKETIME_NO_CACHE": "1",
                "LD_PRELOAD": "/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1",
                "TZ": "UTC",
                "LANG": "en_US.UTF-8",
                "LC_ALL": "en_US.UTF-8",
            },
        },
        "render_profiles": render_profiles.hashes,
        "export": render_profiles.scoring_export(),
        "visual_comparison": render_profiles.scoring_visual_comparison(),
        "structural_profiles": {
            "mce_profile_sha256": _sha256(schemas / "mce-profile-v1.json"),
            "xsd_bundle_sha256": _tree_sha256(schemas / "ecma-376" / "xsd-transitional"),
            "schema_root_map_sha256": _sha256(schemas / "schema-root-map-v1.json"),
            "scene_graph_profile_sha256": scene_graph_profile_sha256,
            "canonical_package_hash_profile_sha256": _sha256(package_profile),
        },
        "artifacts": {
            "prompt_bundle_sha256": _tree_sha256(benchmark / "prompts"),
            "prompt_requirements_oracle_sha256": _sha256(oracle),
            "scored_assertion_inventory_sha256": _sha256(scored_inventory),
            "checklist_bundle_sha256": _tree_sha256(benchmark / "checklist"),
            "tier_bundle_sha256": _tree_sha256(benchmark / "tiers"),
            "asset_bundle_sha256": _tree_sha256(benchmark / "assets"),
            "font_bundle_sha256": _tree_sha256(benchmark / "fonts"),
            "json_schema_bundle_sha256": _tree_sha256(schemas),
            "conformance_fixture_bundle_sha256": _tree_sha256(benchmark / "fixtures"),
            "grader_source_tree_sha256": source_tree_sha256,
            "grader_source_tree_profile_sha256": expected_source_tree_profile,
            "grader_source_tree_manifest_sha256": source_tree_sha256,
            "grader_package_sha256": _sha256(grader_package),
        },
        "gold": {
            "original_byte_sha256": original_gold_sha256,
            "mce_resolved_package_sha256": resolved_gold_sha256,
            "mce_resolved_package_size_bytes": resolved_gold.stat().st_size,
            "canonical_package_hash_profile_sha256": canonical_package_profile_sha256,
            "canonical_package_hash_v1": canonical_package_hash_v1,
            "scene_graph_sha256": _sha256(scene_graph_path),
            "canonical_pdf_sha256": canonical_gold_pdf_sha256,
            "canonical_png_sha256s": canonical_png_sha256s,
            "export_bundle_sha256": _tree_sha256(gold_exports),
            "export_determinism_evidence_sha256": _jcs_sha256(determinism_evidence),
            "expected_export_count": 20,
        },
    }
    schema = json.loads((schemas / "scoring-manifest.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(manifest)
    return manifest


def main() -> None:
    args = _arguments()
    manifest = build_manifest(
        runtime_path=args.runtime,
        gold_path=args.gold,
        gold_exports=args.gold_exports,
        resolved_gold=args.resolved_gold,
        gold_pdf=args.gold_pdf,
        environment_attestation_path=args.environment_attestation,
        export_determinism_evidence_path=args.export_determinism_evidence,
        grader_source_tree_manifest_path=args.grader_source_tree_manifest,
        grader_package=args.grader_package,
    )
    encoded = rfc8785.dumps(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"wrote {args.output}")
    print(f"scoring_manifest_sha256=sha256:{hashlib.sha256(encoded).hexdigest()}")


if __name__ == "__main__":
    main()
