"""Validate Gloss v1 normative profiles and candidate/frozen artifacts."""

# ruff: noqa: E402

from __future__ import annotations

import hashlib
import json
import sys
from base64 import b64decode
from binascii import Error as Base64Error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import jsonschema
import rfc8785
import yaml
from referencing import Registry, Resource

BENCHMARK = Path(__file__).resolve().parent
ROOT = BENCHMARK.parent
GRADER = ROOT / "grader"
SCHEMAS = ROOT / "schemas"
sys.path.insert(0, str(GRADER))

from gloss.profile_contract import (  # noqa: E402
    environment_profile_hashes,
    load_render_profiles,
)
from gloss.release_evidence import (
    validate_assertion_inventory_approvals as _validate_assertion_inventory_approvals,
)
from gloss.release_evidence import (
    validate_export_determinism_evidence,
)
from gloss.release_evidence import (
    validate_prompt_review_approvals as _validate_prompt_review_approvals,
)


class Result(Protocol):
    errors: list[str]
    notes: list[str]

    def require(self, condition: bool, message: str) -> None: ...


def _local_schema_registry() -> Registry:
    registry = Registry()
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        identifier = document.get("$id")
        if isinstance(identifier, str):
            registry = registry.with_resource(identifier, Resource.from_contents(document))
    return registry


def _validator(schema: dict) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(
        schema,
        registry=_local_schema_registry(),
        format_checker=jsonschema.FormatChecker(),
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_json(result: Result, data_name: str, schema_name: str) -> dict:
    data_path = SCHEMAS / data_name
    if not data_path.is_file():
        data_path = BENCHMARK / data_name
    schema_path = SCHEMAS / schema_name
    result.require(data_path.is_file(), f"normative artifact missing: {data_path}")
    result.require(schema_path.is_file(), f"normative schema missing: {schema_path}")
    if not data_path.is_file() or not schema_path.is_file():
        return {}
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        errors = sorted(_validator(schema).iter_errors(data), key=str)
        for error in errors:
            result.errors.append(f"{data_path.name}: schema: {error.message}")
        return data
    except (json.JSONDecodeError, jsonschema.SchemaError) as error:
        result.errors.append(f"{data_path.name}: {error}")
        return {}


def validate_normative(result: Result, release: bool) -> None:
    export_profile = _validate_json(
        result,
        "export-profile-v1.json",
        "export-profile.schema.json",
    )
    png_profile = _validate_json(
        result,
        "png-profile-v1.json",
        "png-profile.schema.json",
    )
    ssim_profile = _validate_json(
        result,
        "ssim-profile-v1.json",
        "ssim-profile.schema.json",
    )
    mce = _validate_json(result, "mce-profile-v1.json", "mce-profile.schema.json")
    root_map = _validate_json(
        result,
        "schema-root-map-v1.json",
        "schema-root-map.schema.json",
    )
    package_profile = _validate_json(
        result,
        "canonical-package-hash-v1.json",
        "canonical-package-hash-profile.schema.json",
    )
    scene_profile = _validate_json(
        result,
        "scene-graph-profile-v1.json",
        "scene-graph-profile.schema.json",
    )
    _validate_json(
        result,
        "fixtures/package-hash/gold-copy-rejection-v1.json",
        "package-hash-fixture.schema.json",
    )
    oracle = _validate_json(
        result,
        "requirements/prompt-requirements.json",
        "prompt-requirements.schema.json",
    )

    for schema_path in sorted(SCHEMAS.glob("*.schema.json")):
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
        except (json.JSONDecodeError, jsonschema.SchemaError) as error:
            result.errors.append(f"{schema_path.name}: invalid JSON Schema: {error}")

    understood = mce.get("understood_namespaces", [])
    result.require(
        len(understood) == len(set(understood)) and len(understood) >= 7,
        "MCE profile must contain a unique explicit understood-namespace set",
    )
    entries = root_map.get("entries", [])
    mapping_keys = [(entry.get("content_type"), entry.get("root_qname")) for entry in entries]
    result.require(
        len(mapping_keys) == len(set(mapping_keys)),
        "schema/root map has duplicate keys",
    )
    for entry in entries:
        xsd = SCHEMAS / "ecma-376" / "xsd-transitional" / entry.get("xsd", "")
        result.require(xsd.is_file(), f"schema/root map names missing XSD: {xsd.name}")
    result.require(
        package_profile.get("stage_0_5_resolution", {}).get("mce_profile") == "mce-profile-v1.json",
        "canonical package hash is not bound to the v1 MCE profile",
    )
    result.require(
        package_profile.get("stage_0_5_resolution", {}).get("schema_root_map")
        == "schema-root-map-v1.json",
        "canonical package hash is not bound to the v1 schema/root map",
    )
    result.require(
        scene_profile.get("input_contract", {}).get("package_state") == "mce-resolved"
        and scene_profile.get("input_contract", {}).get("mce_namespace_policy")
        == "reject-elements-and-attributes"
        and scene_profile.get("serialization", {}).get("canonicalization") == "RFC8785-JCS",
        "scene-graph profile does not freeze resolved input and JCS output",
    )
    result.require(
        export_profile.get("fresh_isolated_user_profile_per_export") is True
        and export_profile.get("libreoffice_command", [None, None, None])[2]
        == "-env:UserInstallation=file://<isolated-temporary-profile>",
        "export profile does not freeze a fresh isolated LibreOffice profile",
    )
    result.require(
        png_profile.get("width_px") == 1920
        and png_profile.get("height_px") == 1080
        and png_profile.get("color_mode") == "RGB"
        and png_profile.get("encoder", {}).get("compress_level") == 9,
        "PNG profile does not freeze the canonical raster and encoder contract",
    )
    result.require(
        ssim_profile.get("threshold") == 0.9999
        and ssim_profile.get("shape") == [1080, 1920, 3]
        and ssim_profile.get("dimension_mismatch") == "fail-with-zero-similarity",
        "SSIM profile does not freeze the canonical comparison contract",
    )

    _validate_oracle(result, oracle)
    if release:
        result.require(
            oracle.get("freeze_status") == "frozen",
            "release mode: prompt requirements oracle is not frozen",
        )
        _validate_prompt_review_approvals(result, oracle)
        gold_evidence = _validate_json(
            result,
            "gold-evidence.json",
            "gold-evidence.schema.json",
        )
        _validate_gold_evidence_semantics(result, gold_evidence)
        determinism_evidence, environment_attestation = _validate_release_evidence_instances(
            result,
            oracle,
            gold_evidence,
        )
        _validate_frozen_release_files(
            result,
            gold_evidence,
            determinism_evidence,
            environment_attestation,
        )
    else:
        result.notes.append(
            "prompt-requirements oracle is a traceable candidate; independent reviews and "
            "fixtures are pending"
        )


def _validate_gold_evidence_semantics(result: Result, evidence: dict) -> None:
    if not evidence:
        return
    pages = [page.get("page") for page in evidence.get("canonical_export", {}).get("pages", [])]
    result.require(
        pages == list(range(1, 21)),
        "gold evidence canonical-export pages must be sorted and exactly 1..20",
    )
    tiers = [control.get("targeted_tier") for control in evidence.get("reference_controls", [])]
    result.require(
        sorted(tiers) == [1, 2, 3] and len(tiers) == 3,
        "gold evidence reference controls must cover tiers exactly {1,2,3}",
    )


def _validate_release_evidence_instances(
    result: Result,
    oracle: dict,
    gold_evidence: dict,
) -> tuple[dict, dict]:
    assertion_inventory = _validate_json(
        result,
        "requirements/scored-assertion-inventory.json",
        "scored-assertion-inventory.schema.json",
    )
    _validate_scored_assertion_inventory(result, assertion_inventory, oracle)
    _validate_json(
        result,
        "grader-source-tree-manifest.json",
        "grader-source-tree-manifest.schema.json",
    )
    environment_attestation = _validate_json(
        result,
        "environment-attestation.json",
        "environment-attestation.schema.json",
    )
    if environment_attestation:
        try:
            render_profiles = load_render_profiles(SCHEMAS)
            expected_profile_hashes = environment_profile_hashes(SCHEMAS)
            result.require(
                environment_attestation.get("profile_hashes") == expected_profile_hashes,
                "release mode: environment attestation profile hashes do not match normative files",
            )
            result.require(
                environment_attestation.get("export_contract") == render_profiles.export_contract(),
                "release mode: environment attestation export contract differs from "
                "normative profiles",
            )
        except (OSError, ValueError) as error:
            result.errors.append(f"release mode: render-profile reconstruction failed: {error}")
    determinism_evidence = _validate_json(
        result,
        "export-determinism-evidence.json",
        "export-determinism-evidence.schema.json",
    )
    expected_determinism_bindings = {
        "environment_attestation_sha256": (
            f"sha256:{hashlib.sha256(rfc8785.dumps(environment_attestation)).hexdigest()}"
        ),
        "original_gold_sha256": gold_evidence.get("original_authored_gold", {}).get("sha256"),
        "resolved_gold_sha256": gold_evidence.get("resolved_gold", {}).get("sha256"),
        "canonical_package_hash_profile_sha256": gold_evidence.get("profile_hashes", {}).get(
            "canonical_package_hash_profile_sha256"
        ),
        "canonical_package_hash_v1": gold_evidence.get("canonical_package_hash_v1"),
        "canonical_pdf_sha256": gold_evidence.get("canonical_export", {}).get("pdf_sha256"),
        "canonical_png_sha256s": [
            page.get("png_sha256")
            for page in gold_evidence.get("canonical_export", {}).get("pages", [])
        ],
        "export_profile_sha256": environment_attestation.get("profile_hashes", {}).get(
            "export_profile_sha256"
        ),
        "ssim_profile_sha256": environment_attestation.get("profile_hashes", {}).get(
            "ssim_profile_sha256"
        ),
    }
    validate_export_determinism_evidence(
        result,
        determinism_evidence,
        expected_bindings=expected_determinism_bindings,
    )
    release_keys = ROOT / "RELEASE_KEYS.json"
    _validate_path_against_schema(result, release_keys, SCHEMAS / "release-keys.schema.json")

    _validate_assertion_evidence_index(result, assertion_inventory)
    mutations = sorted((BENCHMARK / "fixtures" / "mutations").glob("*.json"))
    result.require(bool(mutations), "release mode: fixture mutation evidence is missing")
    for mutation in mutations:
        try:
            json.loads(mutation.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            result.errors.append(f"{mutation}: {error}")

    scene_profile_sha256 = f"sha256:{_digest(SCHEMAS / 'scene-graph-profile-v1.json')}"
    resolved_gold_sha256 = gold_evidence.get("resolved_gold", {}).get("sha256")
    # Missing normative evidence is already reported by _validate_json. Do not compare
    # dependent fixture bindings against None: that turns one absent root artifact into
    # a misleading deck-plus-20-slides package-drift cascade.
    if gold_evidence:
        result.require(
            gold_evidence.get("profile_hashes", {}).get("scene_graph_profile_sha256")
            == scene_profile_sha256,
            "release mode: gold evidence is bound to the wrong scene-graph profile",
        )
    if environment_attestation:
        result.require(
            environment_attestation.get("profile_hashes", {}).get("scene_graph_profile_sha256")
            == scene_profile_sha256,
            "release mode: environment attestation is bound to the wrong scene-graph profile",
        )
    deck_path = BENCHMARK / "fixtures" / "expected-deck.json"
    deck_scene = _validate_path_against_schema(
        result,
        deck_path,
        SCHEMAS / "scene-graph.schema.json",
    )
    if deck_scene:
        _validate_scene_graph_semantics(
            result,
            deck_scene,
            expected_profile_sha256=scene_profile_sha256,
            expected_package_sha256=resolved_gold_sha256,
            expected_slides=list(range(1, 21)),
            label="expected-deck.json",
        )
        result.require(
            deck_path.read_bytes() == rfc8785.dumps(deck_scene),
            "release mode: expected-deck.json is not RFC 8785 JCS",
        )
        if gold_evidence:
            result.require(
                gold_evidence.get("scene_graph_sha256") == f"sha256:{_digest(deck_path)}",
                "release mode: gold evidence scene-graph hash does not match expected-deck.json",
            )

    scene_paths = [
        BENCHMARK / "fixtures" / "expected-scenegraphs" / f"slide-{slide:02d}.json"
        for slide in range(1, 21)
    ]
    for slide, path in enumerate(scene_paths, 1):
        data = _validate_path_against_schema(result, path, SCHEMAS / "scene-graph.schema.json")
        if data:
            _validate_scene_graph_semantics(
                result,
                data,
                expected_profile_sha256=scene_profile_sha256,
                expected_package_sha256=resolved_gold_sha256,
                expected_slides=[slide],
                label=path.name,
            )
            if deck_scene:
                expected_fixture = dict(deck_scene) | {
                    "slides": [deck_scene.get("slides", [])[slide - 1]]
                }
                result.require(
                    data == expected_fixture,
                    f"release mode: {path.name} is not the exact deck-graph slide projection",
                )

    baseline_names = {
        "human-expert.json": "human_expert",
        "programmatic-copy.json": "programmatic_copy",
        "naive-llm.json": "naive_llm",
    }
    for name, kind in baseline_names.items():
        data = _validate_path_against_schema(
            result,
            BENCHMARK / "baselines" / name,
            SCHEMAS / "baseline-evidence.schema.json",
        )
        if data:
            result.require(
                data.get("baseline_kind") == kind,
                f"release mode: {name} has the wrong baseline_kind",
            )

    result.require(
        (BENCHMARK / "deck" / "gold" / "gloss-v1-gold.pptx").is_file(),
        "release mode: canonical gold deck is missing",
    )
    exports = [BENCHMARK / "deck" / "exports" / f"slide-{slide:02d}.png" for slide in range(1, 21)]
    result.require(
        all(path.is_file() for path in exports),
        "release mode: canonical slide-01..20 PNG exports are incomplete",
    )
    return determinism_evidence, environment_attestation


def _validate_scene_graph_semantics(
    result: Result,
    scene_graph: dict,
    *,
    expected_profile_sha256: str,
    expected_package_sha256: str | None,
    expected_slides: list[int],
    label: str,
) -> None:
    result.require(
        scene_graph.get("profile_sha256") == expected_profile_sha256,
        f"release mode: {label} is bound to the wrong scene-graph profile",
    )
    if expected_package_sha256 is not None:
        result.require(
            scene_graph.get("mce_resolved_package_sha256") == expected_package_sha256,
            f"release mode: {label} is bound to the wrong resolved gold package",
        )
    slides = scene_graph.get("slides", [])
    result.require(
        [slide.get("slide") for slide in slides if isinstance(slide, dict)] == expected_slides,
        f"release mode: {label} has the wrong ordered slide set",
    )
    seen_node_ids: set[str] = set()

    def validate_nodes(
        nodes: object,
        *,
        slide: int,
        source_part: object,
        prefix: tuple[int, ...] = (),
        parents: tuple[str, ...] = (),
    ) -> None:
        if not isinstance(nodes, list):
            return
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            structural_path = prefix + (index,)
            expected_id = f"s{slide}:n" + ".".join(str(value) for value in structural_path)
            node_id = node.get("node_id")
            result.require(
                node_id == expected_id and node.get("z_index") == index,
                f"release mode: {label} has a non-normative node ID or z-index",
            )
            result.require(
                node.get("source_part") == source_part
                and node.get("native_properties", {}).get("parent_group_path") == list(parents),
                f"release mode: {label} has a node with the wrong source/group binding",
            )
            result.require(
                isinstance(node_id, str) and node_id not in seen_node_ids,
                f"release mode: {label} has duplicate node IDs",
            )
            if isinstance(node_id, str):
                seen_node_ids.add(node_id)
                validate_nodes(
                    node.get("children"),
                    slide=slide,
                    source_part=source_part,
                    prefix=structural_path,
                    parents=parents + (node_id,),
                )

    for slide in slides:
        if not isinstance(slide, dict) or not isinstance(slide.get("slide"), int):
            continue
        relationships = slide.get("relationships", [])
        result.require(
            [item.get("id") for item in relationships if isinstance(item, dict)]
            == sorted(item.get("id") for item in relationships if isinstance(item, dict)),
            f"release mode: {label} relationships are not ordered by ID",
        )
        validate_nodes(
            slide.get("nodes"),
            slide=slide["slide"],
            source_part=slide.get("part_name"),
        )


def _checklist_documents() -> list[dict]:
    paths = [BENCHMARK / "checklist" / "deck.yaml"] + sorted(
        (BENCHMARK / "checklist" / "slides").glob("slide-*.yaml")
    )
    documents: list[dict] = []
    for path in paths:
        documents.extend(
            document
            for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
            if isinstance(document, dict)
        )
    return documents


def _reference_region_in_bounds(region: object) -> bool:
    if not isinstance(region, dict):
        return False
    values = [region.get(key) for key in ("x", "y", "width", "height")]
    if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
        return False
    x, y, width, height = values
    return (
        x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= 1920 and y + height <= 1080
    )


def _validate_scored_assertion_inventory(result: Result, inventory: dict, oracle: dict) -> None:
    if not inventory:
        return
    assertions = inventory.get("assertions", [])
    result.require(
        inventory.get("lifecycle_state") == "frozen",
        "release mode: scored assertion inventory is not frozen",
    )
    _validate_assertion_inventory_approvals(result, inventory)
    result.require(
        inventory.get("prompt_bundle_sha256") != "pending"
        and inventory.get("reference_image_bundle_sha256") != "pending"
        and inventory.get("asset_manifest_sha256") != "pending",
        "release mode: scored assertion inventory contains pending bundle hashes",
    )

    checklist = _checklist_documents()
    checklist_by_id = {document.get("id"): document for document in checklist}
    assertions_by_item = {
        assertion.get("checklist_item_id"): assertion
        for assertion in assertions
        if isinstance(assertion, dict)
    }
    result.require(
        len(checklist) == 280
        and len(assertions) == 280
        and len(assertions_by_item) == 280
        and set(assertions_by_item) == set(checklist_by_id),
        "release mode: assertion inventory must map exactly once to all 280 checklist items",
    )
    not_frozen = sum(
        assertion.get("lifecycle_state") != "frozen"
        for assertion in assertions
        if isinstance(assertion, dict)
    )
    incomplete_provenance = sum(
        assertion.get("provenance", {}).get("status") != "complete"
        for assertion in assertions
        if isinstance(assertion, dict)
    )
    incomplete_evidence = sum(
        assertion.get("evidence", {}).get("status") != "complete"
        for assertion in assertions
        if isinstance(assertion, dict)
    )
    result.require(
        not_frozen == 0,
        f"release mode: {not_frozen} scored assertions are not frozen",
    )
    result.require(
        incomplete_provenance == 0,
        f"release mode: {incomplete_provenance} scored assertion provenance records are incomplete",
    )
    result.require(
        incomplete_evidence == 0,
        f"release mode: {incomplete_evidence} scored assertion evidence records are incomplete",
    )

    requirement_by_id = {
        requirement.get("requirement_id"): requirement
        for requirement in oracle.get("requirements", [])
        if isinstance(requirement, dict)
    }
    sources_by_id = {
        source.get("source_id"): source
        for source in oracle.get("sources", [])
        if isinstance(source, dict)
    }
    for checklist_id, assertion in assertions_by_item.items():
        item = checklist_by_id.get(checklist_id)
        if not isinstance(item, dict) or not isinstance(assertion, dict):
            continue
        result.require(
            assertion.get("assertion_id") == item.get("assertion_id")
            and assertion.get("scope") == item.get("scope")
            and assertion.get("slide") == item.get("slide")
            and assertion.get("tier") == item.get("tier")
            and assertion.get("statement") == item.get("description")
            and assertion.get("source_of_truth") == item.get("source_of_truth"),
            f"release mode: assertion/checklist identity mismatch for {checklist_id}",
        )
        expected_method = item.get("verification", {}).get("method")
        if expected_method == "hash_match":
            expected_method = "embedded_media_hash"
        result.require(
            assertion.get("verification_method") == expected_method,
            f"release mode: assertion/checklist verification mismatch for {checklist_id}",
        )
        provenance = assertion.get("provenance", {})
        item_provenance = item.get("provenance", {})
        if provenance.get("status") != "complete" or item_provenance.get("status") != "complete":
            continue
        result.require(
            provenance.get("kind") == item_provenance.get("kind")
            and provenance.get("source_hash") == item_provenance.get("source_hash")
            and provenance.get("locator") == item_provenance.get("locator"),
            f"release mode: assertion/checklist provenance mismatch for {checklist_id}",
        )
        if provenance.get("kind") == "prompt":
            requirement_id = provenance.get("prompt_requirement_id")
            requirement = requirement_by_id.get(requirement_id)
            source = (
                sources_by_id.get(requirement.get("provenance", {}).get("source_id"))
                if isinstance(requirement, dict)
                else None
            )
            result.require(
                requirement is not None
                and item.get("prompt_requirement_id") == requirement_id
                and isinstance(source, dict)
                and provenance.get("source_hash") == f"sha256:{source.get('sha256')}",
                f"release mode: prompt provenance does not resolve for {checklist_id}",
            )
        elif provenance.get("kind") == "reference_image":
            item_reference = item_provenance.get("reference_image", {})
            result.require(
                provenance.get("slide") == item_reference.get("slide")
                and provenance.get("region") == item_reference.get("region")
                and _reference_region_in_bounds(provenance.get("region")),
                f"release mode: reference-image region is invalid for {checklist_id}",
            )
        elif provenance.get("kind") == "asset_manifest":
            result.require(
                provenance.get("asset_id") == item_provenance.get("asset_id"),
                f"release mode: asset provenance does not match for {checklist_id}",
            )


def _validate_assertion_evidence_index(result: Result, inventory: dict) -> None:
    """Cross-bind every frozen assertion's evidence IDs to the release evidence index.

    A syntactically valid index alone is not evidence.  It becomes part of the
    release proof only when it is a one-to-one, exact projection of the frozen
    assertion inventory's complete fixture and mutation identifiers.
    """
    index_path = BENCHMARK / "fixtures" / "index.json"
    result.require(index_path.is_file(), "release mode: fixtures/index.json is missing")
    if not index_path.is_file() or not inventory:
        return
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        inventory_schema = json.loads(
            (SCHEMAS / "scored-assertion-inventory.schema.json").read_text(encoding="utf-8")
        )
        index_schema = {
            "$ref": f"{inventory_schema['$id']}#/$defs/assertion_evidence_index"
        }
        errors = sorted(_validator(index_schema).iter_errors(index), key=str)
        for error in errors:
            result.errors.append(f"fixtures/index.json: schema: {error.message}")
    except (KeyError, json.JSONDecodeError, jsonschema.SchemaError) as error:
        result.errors.append(f"fixtures/index.json: {error}")
        return
    if not isinstance(index, dict):
        return

    result.require(
        index.get("assertion_inventory_review_sha256")
        == _validate_assertion_inventory_projection_sha256(inventory),
        "release mode: fixtures/index.json is bound to the wrong frozen assertion inventory",
    )
    expected: dict[str, tuple[object, object, object, object]] = {}
    for assertion in inventory.get("assertions", []):
        if not isinstance(assertion, dict):
            continue
        evidence = assertion.get("evidence", {})
        assertion_id = assertion.get("assertion_id")
        if not isinstance(assertion_id, str) or not isinstance(evidence, dict):
            continue
        expected[assertion_id] = (
            assertion.get("checklist_item_id"),
            evidence.get("positive_fixture_ids"),
            evidence.get("single_fault_negative_fixture_ids"),
            evidence.get("mutation_expectation_ids"),
        )
    actual: dict[str, tuple[object, object, object, object]] = {}
    for entry in index.get("assertions", []):
        if not isinstance(entry, dict):
            continue
        assertion_id = entry.get("assertion_id")
        if not isinstance(assertion_id, str):
            continue
        actual[assertion_id] = (
            entry.get("checklist_item_id"),
            entry.get("positive_fixture_ids"),
            entry.get("single_fault_negative_fixture_ids"),
            entry.get("mutation_expectation_ids"),
        )
    result.require(
        len(actual) == len(index.get("assertions", []))
        and set(actual) == set(expected)
        and actual == expected,
        "release mode: fixtures/index.json does not exactly cross-bind all frozen "
        "assertion evidence IDs",
    )


def _validate_assertion_inventory_projection_sha256(inventory: dict) -> str:
    projection = {
        "domain": "Gloss scored assertion inventory review v1",
        "inventory": {key: value for key, value in inventory.items() if key != "review"},
    }
    return f"sha256:{hashlib.sha256(rfc8785.dumps(projection)).hexdigest()}"


def _validate_path_against_schema(result: Result, data_path: Path, schema_path: Path) -> dict:
    result.require(data_path.is_file(), f"release mode: normative artifact missing: {data_path}")
    result.require(schema_path.is_file(), f"normative schema missing: {schema_path}")
    if not data_path.is_file() or not schema_path.is_file():
        return {}
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(_validator(schema).iter_errors(data), key=str)
        for error in errors:
            result.errors.append(f"{data_path.name}: schema: {error.message}")
        return data
    except (json.JSONDecodeError, jsonschema.SchemaError) as error:
        result.errors.append(f"{data_path.name}: {error}")
        return {}


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} is not a valid RFC 3339 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a UTC offset")
    return parsed.astimezone(UTC)


def _release_index_hash(index: dict) -> str:
    import rfc8785

    return f"sha256:{hashlib.sha256(rfc8785.dumps(index)).hexdigest()}"


def _verify_release_index_signature(index: dict, release_keys: dict) -> None:
    import rfc8785
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    issued_at = _parse_timestamp(index.get("issued_at"), "issued_at")
    effective_at = _parse_timestamp(index.get("effective_at"), "effective_at")
    keys_by_id = {
        key.get("key_id"): key for key in release_keys.get("keys", []) if isinstance(key, dict)
    }
    if len(keys_by_id) != len(release_keys.get("keys", [])):
        raise ValueError("RELEASE_KEYS.json contains duplicate or invalid key IDs")

    signed_payload = dict(index)
    signatures = signed_payload.pop("signatures", None)
    if not isinstance(signatures, list) or not signatures:
        raise ValueError("release index contains no signatures")
    message = rfc8785.dumps(signed_payload)
    verified_key_ids: set[str] = set()
    failures: list[str] = []
    for signature in signatures:
        if not isinstance(signature, dict):
            failures.append("malformed signature entry")
            continue
        key_id = signature.get("key_id")
        key = keys_by_id.get(key_id)
        if key is None:
            failures.append(f"unknown key {key_id!r}")
            continue
        if key.get("algorithm") != "Ed25519" or signature.get("algorithm") != "Ed25519":
            failures.append(f"key {key_id!r} uses the wrong algorithm")
            continue
        try:
            valid_from = _parse_timestamp(key.get("valid_from"), f"key {key_id} valid_from")
            valid_until = (
                _parse_timestamp(key["valid_until"], f"key {key_id} valid_until")
                if key.get("valid_until") is not None
                else None
            )
            revoked_at = (
                _parse_timestamp(key["revoked_at"], f"key {key_id} revoked_at")
                if key.get("revoked_at") is not None
                else None
            )
            if issued_at < valid_from or effective_at < valid_from:
                raise ValueError("key was not yet valid")
            if valid_until is not None and (issued_at > valid_until or effective_at > valid_until):
                raise ValueError("key validity had expired")
            if revoked_at is not None and (issued_at >= revoked_at or effective_at >= revoked_at):
                raise ValueError("key was revoked")
            public_bytes = b64decode(key["public_key_base64"], validate=True)
            signature_bytes = b64decode(signature["signature_base64"], validate=True)
            if len(public_bytes) != 32 or len(signature_bytes) != 64:
                raise ValueError("key or signature has the wrong byte length")
            Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature_bytes, message)
            verified_key_ids.add(str(key_id))
        except (
            Base64Error,
            InvalidSignature,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            failures.append(f"key {key_id!r}: {error}")
    if not verified_key_ids:
        details = "; ".join(failures) if failures else "no authorized signature"
        raise ValueError(f"release index has no valid authorized signature: {details}")


def verify_release_chain(
    indexes: list[dict],
    release_keys: dict,
    *,
    trusted_genesis_sha256: str | None = None,
    persisted_head: tuple[str, int, str] | None = None,
    now: datetime | None = None,
    clock_skew_seconds: int = 300,
) -> tuple[str, int, str]:
    """Verify a complete signed chain and return its durable highest head.

    ``persisted_head`` is the previously accepted ``(channel, sequence, hash)``.
    Supplying it makes rollback and same-sequence fork checks survive process
    restarts; a caller must persist the returned tuple before activation.
    """

    if not indexes:
        raise ValueError("release index chain is empty")
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    previous: dict | None = None
    previous_hash: str | None = None
    previous_issued: datetime | None = None
    previous_effective: datetime | None = None
    state_order = {"active": 0, "frozen": 1, "superseded": 2}
    seen_sequences: set[int] = set()
    seen_hashes: dict[int, str] = {}

    for position, index in enumerate(indexes):
        if not isinstance(index, dict):
            raise ValueError("release index chain contains a non-object")
        channel = index.get("channel")
        sequence = index.get("sequence")
        state = index.get("state")
        if channel != "gloss-v1-stable":
            raise ValueError("release index channel is not gloss-v1-stable")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise ValueError("release index sequence is invalid")
        if sequence in seen_sequences:
            raise ValueError("release index chain contains a duplicate sequence or fork")
        if state not in state_order:
            raise ValueError("release index state is invalid")

        issued_at = _parse_timestamp(index.get("issued_at"), "issued_at")
        effective_at = _parse_timestamp(index.get("effective_at"), "effective_at")
        if effective_at < issued_at:
            raise ValueError("release index effective_at precedes issued_at")
        if issued_at > moment + timedelta(seconds=clock_skew_seconds):
            raise ValueError("release index was issued outside the allowed clock-skew bound")
        if effective_at > moment:
            raise ValueError("release index is not yet effective")

        current_hash = _release_index_hash(index)
        if position == 0:
            if sequence != 1 or index.get("previous_release_index_sha256") is not None:
                raise ValueError("release chain does not begin at trusted sequence 1 genesis")
            if trusted_genesis_sha256 is not None and current_hash != trusted_genesis_sha256:
                raise ValueError("release genesis does not match the configured trust anchor")
        else:
            assert previous is not None and previous_hash is not None
            if sequence != previous["sequence"] + 1:
                raise ValueError("release index chain contains a sequence gap or rollback")
            if index.get("previous_release_index_sha256") != previous_hash:
                raise ValueError("release index chain contains an unknown fork")
            if previous_issued is not None and issued_at < previous_issued:
                raise ValueError("release index issued_at moved backward")
            if previous_effective is not None and effective_at < previous_effective:
                raise ValueError("release index effective_at moved backward")
            if state_order[state] < state_order[previous["state"]]:
                raise ValueError("release index state moved backward")

        _verify_release_index_signature(index, release_keys)
        seen_sequences.add(sequence)
        seen_hashes[sequence] = current_hash
        previous = index
        previous_hash = current_hash
        previous_issued = issued_at
        previous_effective = effective_at

    assert previous is not None and previous_hash is not None
    head = (str(previous["channel"]), int(previous["sequence"]), previous_hash)
    if persisted_head is not None:
        persisted_channel, persisted_sequence, persisted_hash = persisted_head
        if persisted_channel != head[0]:
            raise ValueError("persisted release head belongs to another channel")
        if head[1] < persisted_sequence:
            raise ValueError("release chain attempts rollback below the persisted head")
        accepted_hash = seen_hashes.get(persisted_sequence)
        if accepted_hash != persisted_hash:
            raise ValueError("release chain does not contain the persisted trusted head")
    return head


def _validate_oracle(result: Result, oracle: dict) -> None:
    sources = {source.get("source_id"): source for source in oracle.get("sources", [])}
    requirements = oracle.get("requirements", [])
    ids = [item.get("requirement_id") for item in requirements]
    result.require(len(ids) == len(set(ids)), "prompt requirements contain duplicate IDs")
    slide_counts = {number: 0 for number in range(1, 21)}
    deck_count = 0
    for source in sources.values():
        path = ROOT / source.get("path", "")
        result.require(path.is_file(), f"oracle source is missing: {path}")
        if path.is_file():
            result.require(
                _digest(path) == source.get("sha256"),
                f"oracle source hash drift: {path}",
            )
    for item in requirements:
        if item.get("scope") == "deck":
            deck_count += 1
        elif item.get("slide") in slide_counts:
            slide_counts[item["slide"]] += 1
        provenance = item.get("provenance", {})
        source = sources.get(provenance.get("source_id"))
        if source is None:
            result.errors.append(f"{item.get('requirement_id')}: unknown source_id")
            continue
        path = ROOT / source["path"]
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        start = provenance.get("line_start", 0)
        end = provenance.get("line_end", 0)
        if not (1 <= start <= end <= len(lines)):
            result.errors.append(f"{item.get('requirement_id')}: invalid source line range")
            continue
        excerpt = "\n".join(lines[start - 1 : end])
        result.require(
            excerpt == provenance.get("excerpt"),
            f"{item.get('requirement_id')}: excerpt drift",
        )
        result.require(
            hashlib.sha256(excerpt.encode("utf-8")).hexdigest() == provenance.get("excerpt_sha256"),
            f"{item.get('requirement_id')}: excerpt hash drift",
        )
    result.require(deck_count > 0, "prompt requirements contain no deck assertions")
    for slide, count in slide_counts.items():
        result.require(
            count > 0,
            f"prompt requirements contain no assertions for slide {slide:02d}",
        )
    result.notes.append(
        f"prompt-requirements inventory: {deck_count} deck + "
        f"{sum(slide_counts.values())} slide clauses"
    )


def _validate_frozen_release_files(
    result: Result,
    gold_evidence: dict,
    determinism_evidence: dict,
    environment_attestation: dict,
) -> None:
    manifest = BENCHMARK / "scoring-manifest.json"
    release_index = BENCHMARK / "release-index.json"
    release_chain = BENCHMARK / "release-index-chain.json"
    result.require(manifest.is_file(), "release mode: scoring-manifest.json is missing")
    result.require(release_index.is_file(), "release mode: release-index.json is missing")
    if not manifest.is_file() or not release_index.is_file():
        return
    try:
        import rfc8785
    except ImportError:
        result.errors.append("release mode: rfc8785 is unavailable for JCS verification")
        return
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    index_data = json.loads(release_index.read_text(encoding="utf-8"))
    _validate_path_against_schema(result, manifest, SCHEMAS / "scoring-manifest.schema.json")
    _validate_path_against_schema(result, release_index, SCHEMAS / "release-index.schema.json")
    indexes = [index_data]
    if release_chain.is_file():
        chain_data = _validate_path_against_schema(
            result,
            release_chain,
            SCHEMAS / "release-index-chain.schema.json",
        )
        result.require(
            release_chain.read_bytes() == rfc8785.dumps(chain_data),
            "release index chain is not RFC 8785 JCS",
        )
        chain_indexes = chain_data.get("indexes", [])
        if isinstance(chain_indexes, list) and chain_indexes:
            indexes = chain_indexes
            result.require(
                rfc8785.dumps(chain_indexes[-1]) == release_index.read_bytes(),
                "release-index.json does not equal the packaged release-chain head",
            )
    else:
        result.require(
            index_data.get("sequence") == 1,
            "release mode: release-index-chain.json is required above sequence 1",
        )
    release_keys_path = ROOT / "RELEASE_KEYS.json"
    release_keys = _validate_path_against_schema(
        result, release_keys_path, SCHEMAS / "release-keys.schema.json"
    )
    if release_keys:
        try:
            channel, sequence, head_hash = verify_release_chain(indexes, release_keys)
            result.notes.append(
                "verified signed release chain head: "
                f"channel={channel}, sequence={sequence}, hash={head_hash}"
            )
        except (ImportError, ValueError) as error:
            result.errors.append(f"release mode: release-index signature/chain: {error}")
    result.require(
        index_data.get("state") == "active",
        "release mode: release-index chain head is not active",
    )
    result.require(
        manifest.read_bytes() == rfc8785.dumps(manifest_data),
        "scoring manifest is not RFC 8785 JCS",
    )
    result.require(
        release_index.read_bytes() == rfc8785.dumps(index_data),
        "release index is not RFC 8785 JCS",
    )
    determinism_path = BENCHMARK / "export-determinism-evidence.json"
    if determinism_evidence and determinism_path.is_file():
        result.require(
            determinism_path.read_bytes() == rfc8785.dumps(determinism_evidence),
            "export determinism evidence is not RFC 8785 JCS",
        )
    descriptor = index_data.get("cohort_descriptor", {})
    expected_manifest = f"sha256:{_digest(manifest)}"
    expected_cohort = f"sha256:{hashlib.sha256(rfc8785.dumps(descriptor)).hexdigest()}"
    result.require(
        index_data.get("scoring_manifest_sha256") == expected_manifest
        and descriptor.get("scoring_manifest_sha256") == expected_manifest,
        "release index scoring-manifest hash mismatch",
    )
    result.require(
        index_data.get("scoring_cohort_id") == expected_cohort,
        "release index cohort ID mismatch",
    )
    if environment_attestation:
        environment_sha256 = (
            f"sha256:{hashlib.sha256(rfc8785.dumps(environment_attestation)).hexdigest()}"
        )
        runtime = manifest_data.get("runtime", {})
        attested_versions = environment_attestation.get("runtime_versions", {})
        attested_fonts = environment_attestation.get("font_environment", {})
        attested_binaries = {
            record.get("name"): record
            for record in environment_attestation.get("binary_inventory", [])
            if isinstance(record, dict)
        }
        result.require(
            runtime.get("environment_attestation_sha256") == environment_sha256
            and descriptor.get("environment_attestation_sha256") == environment_sha256,
            "scoring manifest/release index environment-attestation hash mismatch",
        )
        result.require(
            manifest_data.get("platform") == environment_attestation.get("platform")
            and manifest_data.get("oci_image_digest")
            == environment_attestation.get("oci_image_digest"),
            "scoring manifest platform/OCI digest differs from environment attestation",
        )
        version_fields = (
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
        result.require(
            all(runtime.get(field) == attested_versions.get(field) for field in version_fields),
            "scoring manifest runtime versions differ from environment attestation",
        )
        result.require(
            runtime.get("fontconfig_config_sha256")
            == attested_fonts.get("fontconfig_config_sha256")
            and runtime.get("libfaketime_library_sha256")
            == attested_binaries.get("libfaketime", {}).get("sha256"),
            "scoring manifest runtime file hashes differ from environment attestation",
        )
        try:
            render_profiles = load_render_profiles(SCHEMAS)
            result.require(
                manifest_data.get("render_profiles")
                == render_profiles.hashes
                == {
                    key: environment_attestation.get("profile_hashes", {}).get(key)
                    for key in render_profiles.hashes
                },
                "scoring manifest render-profile hashes are stale or substituted",
            )
            result.require(
                manifest_data.get("export") == render_profiles.scoring_export()
                and manifest_data.get("visual_comparison")
                == render_profiles.scoring_visual_comparison(),
                "scoring manifest render/SSIM projections differ from normative profiles",
            )
        except (OSError, ValueError) as error:
            result.errors.append(f"release mode: render-profile binding failed: {error}")
        result.require(
            manifest_data.get("artifacts", {}).get("grader_source_tree_sha256")
            == environment_attestation.get("grader_source_tree_sha256"),
            "scoring manifest grader source-tree differs from environment attestation",
        )
    if gold_evidence:
        gold = manifest_data.get("gold", {})
        export = gold_evidence.get("canonical_export", {})
        resolved = gold_evidence.get("resolved_gold", {})
        result.require(
            gold.get("original_byte_sha256")
            == gold_evidence.get("original_authored_gold", {}).get("sha256"),
            "scoring manifest original gold hash does not match gold evidence",
        )
        result.require(
            gold.get("mce_resolved_package_sha256") == resolved.get("sha256")
            and gold.get("mce_resolved_package_size_bytes") == resolved.get("size_bytes"),
            "scoring manifest resolved gold identity does not match gold evidence",
        )
        result.require(
            gold.get("canonical_package_hash_profile_sha256")
            == gold_evidence.get("profile_hashes", {}).get("canonical_package_hash_profile_sha256")
            and gold.get("canonical_package_hash_v1")
            == gold_evidence.get("canonical_package_hash_v1"),
            "scoring manifest canonical gold identity does not match gold evidence",
        )
        result.require(
            manifest_data.get("structural_profiles", {}).get("scene_graph_profile_sha256")
            == gold_evidence.get("profile_hashes", {}).get("scene_graph_profile_sha256")
            and gold.get("scene_graph_sha256") == gold_evidence.get("scene_graph_sha256"),
            "scoring manifest scene-graph profile/hash does not match gold evidence",
        )
        result.require(
            gold.get("canonical_pdf_sha256") == export.get("pdf_sha256"),
            "scoring manifest canonical PDF hash does not match gold evidence",
        )
        result.require(
            gold.get("canonical_png_sha256s")
            == [page.get("png_sha256") for page in export.get("pages", [])],
            "scoring manifest canonical PNG hashes/order do not match gold evidence",
        )
        if determinism_evidence and determinism_path.is_file():
            result.require(
                gold.get("export_determinism_evidence_sha256")
                == f"sha256:{_digest(determinism_path)}",
                "scoring manifest does not bind the export determinism evidence",
            )
