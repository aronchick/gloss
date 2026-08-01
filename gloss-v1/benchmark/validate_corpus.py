#!/usr/bin/env python3
"""Validate the public, non-gold Gloss v1 benchmark corpus."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

import jsonschema
import yaml
from validate_normative import validate_normative

BENCHMARK = Path(__file__).resolve().parent
ROOT = BENCHMARK.parent
TOKEN_PATTERN = re.compile(
    r"#[0-9A-Fa-f]{6}|[A-Za-z0-9_-]+\.(?:png|pptx)|\d+(?:\.\d+)?(?:cm|pt|px|mm|%|°|×)|`[^`\n]+`|\"[^\"\n]+\"|[\u0600-\u06ff]+|[\u3040-\u30ff\u3400-\u9fff]+"
)


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.notes: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(path: Path) -> list[int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"not a PNG: {path}")
    return list(struct.unpack(">II", data[16:24]))


def validate_assets(result: Validation) -> dict[str, str]:
    path = BENCHMARK / "assets" / "manifest.json"
    result.require(path.is_file(), "assets/manifest.json is missing")
    if not path.is_file():
        return {}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assets = manifest.get("assets", [])
    result.require(
        manifest.get("policy") == "allowlist-only",
        "asset manifest policy must be allowlist-only",
    )
    result.require(len(assets) == 3, f"expected 3 assets, found {len(assets)}")
    hashes: dict[str, str] = {}
    for entry in assets:
        asset_id = entry.get("asset_id", "<missing>")
        local = BENCHMARK / "assets" / entry.get("local_path", "")
        source = BENCHMARK / "assets" / entry.get("source_path", "")
        license_path = BENCHMARK / "assets" / entry.get("license_file", "")
        result.require(local.is_file(), f"asset {asset_id}: local file missing")
        result.require(source.is_file(), f"asset {asset_id}: source file missing")
        result.require(license_path.is_file(), f"asset {asset_id}: license file missing")
        result.require(entry.get("license") == "CC0-1.0", f"asset {asset_id}: expected CC0-1.0")
        result.require(
            entry.get("source_url") is None,
            f"asset {asset_id}: self-authored source_url must be null",
        )
        result.require(
            entry.get("accepted_recompression_hashes") == [],
            f"asset {asset_id}: recompression hashes must remain empty until gold extraction",
        )
        result.require(
            entry.get("recompression_status") == "pending_gold_deck_extraction",
            f"asset {asset_id}: recompression status is dishonest",
        )
        if local.is_file():
            actual = digest(local)
            hashes[asset_id] = actual
            result.require(actual == entry.get("sha256"), f"asset {asset_id}: SHA-256 mismatch")
            result.require(
                png_size(local) == entry.get("dimensions_px"),
                f"asset {asset_id}: PNG dimensions mismatch",
            )
        if source.is_file():
            result.require(
                digest(source) == entry.get("source_sha256"),
                f"asset {asset_id}: source SHA-256 mismatch",
            )
    return hashes


def validate_fonts(result: Validation) -> None:
    path = BENCHMARK / "fonts" / "manifest.json"
    result.require(path.is_file(), "fonts/manifest.json is missing")
    result.require((BENCHMARK / "fonts" / "LICENSE").is_file(), "fonts/LICENSE is missing")
    if not path.is_file():
        return
    manifest = json.loads(path.read_text(encoding="utf-8"))
    packages = manifest.get("packages", [])
    files = manifest.get("files", [])
    result.require(
        manifest.get("runtime") == "Ubuntu 22.04 (jammy)",
        "font runtime must match canonical Ubuntu 22.04",
    )
    result.require(len(packages) == 5, f"expected 5 pinned font packages, found {len(packages)}")
    result.require(len(files) == 26, f"expected 26 bundled font files, found {len(files)}")
    families = {entry.get("family") for entry in files}
    required_families = {
        "Liberation Sans",
        "Liberation Serif",
        "Liberation Mono",
        "Carlito",
        "Caladea",
        "Noto Sans",
        "Noto Sans Arabic",
        "Noto Sans CJK JP",
    }
    result.require(
        required_families <= families,
        f"font families missing: {sorted(required_families - families)}",
    )
    for package in packages:
        result.require(
            str(package.get("source_url", "")).startswith("https://archive.ubuntu.com/ubuntu/"),
            f"font package {package.get('package')}: source is not pinned Ubuntu archive",
        )
        result.require(
            re.fullmatch(r"[0-9a-f]{64}", package.get("package_sha256", "")) is not None,
            f"font package {package.get('package')}: package hash invalid",
        )
        result.require(
            (BENCHMARK / "fonts" / package.get("license_file", "")).is_file(),
            f"font package {package.get('package')}: license file missing",
        )
    for entry in files:
        local = BENCHMARK / "fonts" / entry.get("local_path", "")
        result.require(local.is_file(), f"font file missing: {entry.get('local_path')}")
        if local.is_file():
            result.require(
                digest(local) == entry.get("sha256"),
                f"font hash mismatch: {entry.get('local_path')}",
            )


def hard_tokens(text: str) -> list[str]:
    return sorted(TOKEN_PATTERN.findall(text))


def _prompt_validation_metadata(result: Validation, record: Path, slide: int) -> dict:
    text = record.read_text(encoding="utf-8")
    match = re.match(
        r"\A<!-- gloss-prompt-validation-v1\n(.*?)\n-->\n",
        text,
        re.DOTALL,
    )
    result.require(match is not None, f"slide {slide:02d}: machine validation header missing")
    if match is None:
        return {}
    try:
        metadata = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        result.errors.append(f"slide {slide:02d}: invalid validation metadata: {error}")
        return {}
    result.require(
        isinstance(metadata, dict),
        f"slide {slide:02d}: validation metadata must be an object",
    )
    return metadata if isinstance(metadata, dict) else {}


def _prompt_evidence_path(result: Validation, value: object, slide: int, label: str) -> Path | None:
    if not isinstance(value, str) or not value:
        result.errors.append(f"slide {slide:02d}: {label} must be a nonempty relative path")
        return None
    candidate = (BENCHMARK / value).resolve()
    evidence_root = (BENCHMARK / "fixtures" / "prompt-validation").resolve()
    if not candidate.is_relative_to(evidence_root):
        result.errors.append(
            f"slide {slide:02d}: {label} must stay under fixtures/prompt-validation"
        )
        return None
    result.require(candidate.is_file(), f"slide {slide:02d}: {label} is missing: {value}")
    return candidate if candidate.is_file() else None


def _validate_prompt_assertion_report(
    result: Validation,
    *,
    path: Path,
    expected_sha256: object,
    slide: int,
    round_id: str,
    author: dict,
    prompt_hash: str,
    expected_requirement_ids: list[str],
) -> None:
    result.require(
        expected_sha256 == f"sha256:{digest(path)}",
        f"slide {slide:02d}: assertion report hash mismatch for {author.get('author_id')}",
    )
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        result.errors.append(f"slide {slide:02d}: invalid assertion report {path}: {error}")
        return
    required_keys = {
        "schema_version",
        "report_id",
        "round_id",
        "slide",
        "author_id",
        "prompt_variant",
        "prompt_sha256",
        "artifact_sha256",
        "resolved_package_sha256",
        "scene_graph_sha256",
        "results",
    }
    result.require(
        isinstance(report, dict) and set(report) == required_keys,
        f"slide {slide:02d}: assertion report has missing or unknown fields",
    )
    if not isinstance(report, dict):
        return
    result.require(report.get("schema_version") == "1.0", f"slide {slide:02d}: report version")
    result.require(report.get("round_id") == round_id, f"slide {slide:02d}: report round drift")
    result.require(report.get("slide") == slide, f"slide {slide:02d}: report slide drift")
    for field in (
        "author_id",
        "prompt_variant",
        "artifact_sha256",
        "resolved_package_sha256",
        "scene_graph_sha256",
    ):
        result.require(
            report.get(field) == author.get(field),
            f"slide {slide:02d}: report {field} does not match author handoff",
        )
    result.require(
        report.get("prompt_sha256") == prompt_hash,
        f"slide {slide:02d}: report prompt hash drift",
    )
    rows = report.get("results")
    result.require(isinstance(rows, list), f"slide {slide:02d}: report results must be an array")
    if not isinstance(rows, list):
        return
    observed_ids: list[str] = []
    for row in rows:
        result.require(
            isinstance(row, dict) and set(row) == {"requirement_id", "passed", "evidence_ids"},
            f"slide {slide:02d}: malformed assertion-result row",
        )
        if not isinstance(row, dict):
            continue
        requirement_id = row.get("requirement_id")
        if isinstance(requirement_id, str):
            observed_ids.append(requirement_id)
        result.require(row.get("passed") is True, f"slide {slide:02d}: failed mandatory assertion")
        evidence_ids = row.get("evidence_ids")
        result.require(
            isinstance(evidence_ids, list)
            and bool(evidence_ids)
            and all(isinstance(item, str) and item for item in evidence_ids),
            f"slide {slide:02d}: assertion result lacks concrete evidence IDs",
        )
    result.require(
        sorted(observed_ids) == expected_requirement_ids,
        f"slide {slide:02d}: assertion report does not cover the exact prompt requirements",
    )


def _validate_completed_prompt_round(
    result: Validation,
    *,
    metadata: dict,
    slide: int,
    expected_requirement_ids: list[str],
) -> None:
    round_id = metadata.get("round_id")
    result.require(
        isinstance(round_id, str)
        and re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,127}", round_id) is not None,
        f"slide {slide:02d}: completed round_id is invalid",
    )
    if not isinstance(round_id, str):
        return
    authors = metadata.get("authors")
    result.require(
        isinstance(authors, list) and len(authors) == 3,
        f"slide {slide:02d}: completed round must have exactly three authors",
    )
    if not isinstance(authors, list) or len(authors) != 3:
        return
    required_author_keys = {
        "author_id",
        "prompt_variant",
        "clean_context",
        "artifact_path",
        "artifact_sha256",
        "resolved_package_sha256",
        "scene_graph_sha256",
        "assertion_report_path",
        "assertion_report_sha256",
        "mandatory_assertions_total",
        "mandatory_assertions_passed",
    }
    author_ids: list[str] = []
    variants: list[str] = []
    prompt_hashes = metadata.get("prompt_hashes", {})
    for author in authors:
        result.require(
            isinstance(author, dict) and set(author) == required_author_keys,
            f"slide {slide:02d}: author handoff has missing or unknown fields",
        )
        if not isinstance(author, dict):
            continue
        author_id = author.get("author_id")
        variant = author.get("prompt_variant")
        if isinstance(author_id, str):
            author_ids.append(author_id)
        if isinstance(variant, str):
            variants.append(variant)
        result.require(author.get("clean_context") is True, f"slide {slide:02d}: author not blind")
        total = author.get("mandatory_assertions_total")
        passed = author.get("mandatory_assertions_passed")
        result.require(
            total == len(expected_requirement_ids) and passed == total,
            f"slide {slide:02d}: author did not pass every mandatory assertion",
        )
        for field in (
            "artifact_sha256",
            "resolved_package_sha256",
            "scene_graph_sha256",
        ):
            result.require(
                isinstance(author.get(field), str)
                and re.fullmatch(r"sha256:[0-9a-f]{64}", author[field]) is not None,
                f"slide {slide:02d}: author {field} is invalid",
            )
        artifact = _prompt_evidence_path(
            result, author.get("artifact_path"), slide, "author artifact"
        )
        if artifact is not None:
            result.require(
                author.get("artifact_sha256") == f"sha256:{digest(artifact)}",
                f"slide {slide:02d}: author artifact hash mismatch",
            )
        report_path = _prompt_evidence_path(
            result, author.get("assertion_report_path"), slide, "assertion report"
        )
        prompt_hash = prompt_hashes.get(variant) if isinstance(prompt_hashes, dict) else None
        if report_path is not None and isinstance(prompt_hash, str):
            _validate_prompt_assertion_report(
                result,
                path=report_path,
                expected_sha256=author.get("assertion_report_sha256"),
                slide=slide,
                round_id=round_id,
                author=author,
                prompt_hash=prompt_hash,
                expected_requirement_ids=expected_requirement_ids,
            )
    result.require(len(set(author_ids)) == 3, f"slide {slide:02d}: author IDs are not unique")
    result.require(
        set(variants) == {"canonical", "paraphrase-a", "paraphrase-b"},
        f"slide {slide:02d}: completed round must cover all three prompt variants",
    )
    diagnostics = metadata.get("pairwise_similarity_diagnostics")
    result.require(
        isinstance(diagnostics, list) and len(diagnostics) == 3,
        f"slide {slide:02d}: expected exactly three pairwise diagnostics",
    )
    observed_pairs: set[tuple[str, str]] = set()
    if isinstance(diagnostics, list):
        for diagnostic in diagnostics:
            result.require(
                isinstance(diagnostic, dict)
                and set(diagnostic) == {"author_a", "author_b", "scene_graph_similarity"},
                f"slide {slide:02d}: malformed similarity diagnostic",
            )
            if not isinstance(diagnostic, dict):
                continue
            a = diagnostic.get("author_a")
            b = diagnostic.get("author_b")
            similarity = diagnostic.get("scene_graph_similarity")
            if isinstance(a, str) and isinstance(b, str) and a != b:
                observed_pairs.add(tuple(sorted((a, b))))
            result.require(
                isinstance(similarity, (int, float))
                and not isinstance(similarity, bool)
                and 0 <= similarity <= 1,
                f"slide {slide:02d}: invalid diagnostic similarity",
            )
        result.require(
            len(observed_pairs) == 3,
            f"slide {slide:02d}: pairwise diagnostics do not cover all author pairs",
        )


def validate_prompts(result: Validation, release: bool) -> None:
    deck = BENCHMARK / "prompts" / "deck.md"
    brief = BENCHMARK / "prompts" / "DESIGNER_BRIEF.md"
    result.require(deck.is_file(), "prompts/deck.md is missing")
    result.require(brief.is_file(), "prompts/DESIGNER_BRIEF.md is missing")
    if brief.is_file():
        text = brief.read_text(encoding="utf-8")
        result.require(
            "Author in Microsoft PowerPoint" not in text,
            "designer brief still instructs PowerPoint-first authoring",
        )
        result.require(
            "derived from the gold" not in text.lower(),
            "designer brief says prompts derive from gold",
        )
        result.require(
            "pinned LibreOffice Impress environment" in text,
            "designer brief lacks LibreOffice-only authoring contract",
        )
        result.require(
            "grading-verified" in text and "generation-attested" in text,
            "designer brief lacks current verification terminology",
        )
        result.require(
            "Noto Sans JP" not in text,
            "designer brief uses the unbundled Noto Sans JP family name",
        )
        result.require(
            "Noto Sans CJK JP" in text,
            "designer brief lacks the bundled Noto Sans CJK JP family name",
        )
        result.require(
            "will be provided" not in text,
            "designer brief still describes bundled assets as future deliveries",
        )
    variant_files = list((BENCHMARK / "prompts" / "variants").glob("*/slide-*.md"))
    validation_files = list((BENCHMARK / "prompts" / "validation").glob("slide-*.md"))
    result.require(
        len(variant_files) == 60,
        f"expected exactly 60 slide prompt variants, found {len(variant_files)}",
    )
    result.require(
        len(validation_files) == 20,
        f"expected exactly 20 prompt validation records, found {len(validation_files)}",
    )
    oracle_path = BENCHMARK / "requirements" / "prompt-requirements.json"
    oracle = json.loads(oracle_path.read_text(encoding="utf-8")) if oracle_path.is_file() else {}
    requirements_by_slide = {
        slide: sorted(
            item.get("requirement_id")
            for item in oracle.get("requirements", [])
            if item.get("scope") == "slide" and item.get("slide") == slide
        )
        for slide in range(1, 21)
    }
    pending = 0
    for number in range(1, 21):
        paths = {
            name: BENCHMARK / "prompts" / "variants" / name / f"slide-{number:02d}.md"
            for name in ("canonical", "paraphrase-a", "paraphrase-b")
        }
        for name, path in paths.items():
            result.require(path.is_file(), f"slide {number:02d}: missing {name} prompt")
        if all(path.is_file() for path in paths.values()):
            texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
            result.require(
                all("primary directive" in text for text in texts.values()),
                f"slide {number:02d}: prompt-first authority missing",
            )
            result.require(
                all("Noto Sans JP" not in text for text in texts.values()),
                f"slide {number:02d}: prompt uses unbundled Noto Sans JP family",
            )
            canonical_tokens = hard_tokens(texts["canonical"])
            result.require(
                hard_tokens(texts["paraphrase-a"]) == canonical_tokens,
                f"slide {number:02d}: paraphrase A hard-constraint drift",
            )
            result.require(
                hard_tokens(texts["paraphrase-b"]) == canonical_tokens,
                f"slide {number:02d}: paraphrase B hard-constraint drift",
            )
            canonical_blocks = re.findall(r"```.*?```", texts["canonical"], re.DOTALL)
            result.require(
                re.findall(r"```.*?```", texts["paraphrase-a"], re.DOTALL) == canonical_blocks,
                f"slide {number:02d}: paraphrase A changed a literal code/text block",
            )
            result.require(
                re.findall(r"```.*?```", texts["paraphrase-b"], re.DOTALL) == canonical_blocks,
                f"slide {number:02d}: paraphrase B changed a literal code/text block",
            )
            result.require(
                len({texts[name] for name in texts}) == 3,
                f"slide {number:02d}: variants are not distinct",
            )
        record = BENCHMARK / "prompts" / "validation" / f"slide-{number:02d}.md"
        result.require(record.is_file(), f"slide {number:02d}: validation record missing")
        if record.is_file():
            record_text = record.read_text(encoding="utf-8")
            metadata = _prompt_validation_metadata(result, record, number)
            expected_metadata_keys = {
                "schema_version",
                "record_id",
                "slide",
                "prompt_hashes",
                "status",
                "round_id",
                "authors",
                "pairwise_similarity_diagnostics",
            }
            result.require(
                set(metadata) == expected_metadata_keys,
                f"slide {number:02d}: validation metadata has missing or unknown fields",
            )
            result.require(
                metadata.get("schema_version") == "1.0"
                and metadata.get("record_id") == f"gloss-prompt-validation-slide-{number:02d}"
                and metadata.get("slide") == number,
                f"slide {number:02d}: validation metadata identity mismatch",
            )
            expected_hashes = {name: f"sha256:{digest(path)}" for name, path in paths.items()}
            result.require(
                metadata.get("prompt_hashes") == expected_hashes,
                f"slide {number:02d}: validation record prompt hash drift",
            )
            status = metadata.get("status")
            result.require(
                status in {"pending", "completed"},
                f"slide {number:02d}: invalid validation status",
            )
            result.require(
                "hard-constraint parity: pass" in record_text,
                f"slide {number:02d}: static parity not passed",
            )
            result.require(
                "does not claim authoring convergence" in record_text,
                f"slide {number:02d}: convergence disclaimer missing",
            )
            result.require(
                "Required blinded author count: 3" in record_text,
                f"slide {number:02d}: three-author requirement missing",
            )
            result.require(
                "Structural similarity: diagnostic only; no release threshold" in record_text,
                f"slide {number:02d}: diagnostic-only similarity rule missing",
            )
            result.require(
                "80% structural similarity" not in record_text,
                f"slide {number:02d}: stale similarity release threshold remains",
            )
            if status == "pending":
                pending += 1
                result.require(
                    metadata.get("round_id") is None
                    and metadata.get("authors") == []
                    and metadata.get("pairwise_similarity_diagnostics") == [],
                    f"slide {number:02d}: pending record contains claimed run evidence",
                )
                result.require(
                    "Independent-author convergence: not run" in record_text,
                    f"slide {number:02d}: pending status disclaimer missing",
                )
            elif status == "completed":
                result.require(
                    "Independent-author convergence: completed" in record_text,
                    f"slide {number:02d}: completed human-readable status missing",
                )
                _validate_completed_prompt_round(
                    result,
                    metadata=metadata,
                    slide=number,
                    expected_requirement_ids=requirements_by_slide[number],
                )
    result.notes.append(f"independent-author convergence pending: {pending}/20")
    if release:
        result.require(
            pending == 0,
            f"release mode: {pending} prompt convergence records are still pending",
        )


def validate_checklist(result: Validation, release: bool = False) -> None:
    schema = json.loads(
        (ROOT / "schemas" / "checklist-item.schema.json").read_text(encoding="utf-8")
    )
    validator = jsonschema.Draft202012Validator(schema)
    paths = [BENCHMARK / "checklist" / "deck.yaml"] + sorted(
        (BENCHMARK / "checklist" / "slides").glob("slide-*.yaml")
    )
    documents: list[dict] = []
    by_path: dict[Path, list[dict]] = {}
    for path in paths:
        docs = [
            doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc is not None
        ]
        by_path[path] = docs
        documents.extend(docs)
        for doc in docs:
            for error in validator.iter_errors(doc):
                result.errors.append(
                    f"{path.name}:{doc.get('id', '<missing>')}: schema: {error.message}"
                )
    deck_count = len(by_path[BENCHMARK / "checklist" / "deck.yaml"])
    result.require(deck_count == 20, f"expected 20 deck items, found {deck_count}")
    for number in range(1, 21):
        path = BENCHMARK / "checklist" / "slides" / f"slide-{number:02d}.yaml"
        result.require(
            len(by_path.get(path, [])) == 13,
            f"slide {number:02d}: expected 13 items, found {len(by_path.get(path, []))}",
        )
    result.require(len(documents) == 280, f"expected 280 checklist items, found {len(documents)}")
    ids = [doc.get("id") for doc in documents]
    duplicates = [key for key, count in collections.Counter(ids).items() if count > 1]
    result.require(not duplicates, f"duplicate checklist IDs: {duplicates}")
    severity = collections.Counter(doc.get("severity") for doc in documents)
    result.require(
        severity == {"critical": 84, "major": 112, "minor": 84},
        f"severity mix must be exact 30/40/30, found {dict(severity)}",
    )
    sources = collections.Counter(doc.get("source_of_truth") for doc in documents)
    result.require(
        all(sources[key] >= 70 for key in ("ooxml", "render", "both")),
        f"source split is not balanced enough: {dict(sources)}",
    )
    result.require(
        sources["render"] + sources["both"] >= 160,
        f"render-aware item volume too low: {dict(sources)}",
    )
    for doc in documents:
        if doc.get("verification", {}).get("method") == "visual_ssim":
            result.require(
                doc["verification"].get("expectation", {}).get("min_ssim") == 0.9999,
                f"{doc.get('id')}: SSIM threshold is not 0.9999",
            )
    candidate_count = sum(doc.get("lifecycle_state") != "frozen" for doc in documents)
    pending_provenance_count = sum(
        doc.get("provenance", {}).get("status") != "complete" for doc in documents
    )
    pending_evidence_count = sum(
        doc.get("evidence", {}).get("status") != "complete" for doc in documents
    )
    pending_affected_slides_count = sum(
        doc.get("failure_mode", {}).get("affected_slides", {}).get("status") != "complete"
        for doc in documents
        if "failure_mode" in doc
    )
    result.notes.append(
        "checklist release state: "
        f"lifecycle_not_frozen={candidate_count}, "
        f"provenance_not_complete={pending_provenance_count}, "
        f"evidence_not_complete={pending_evidence_count}, "
        f"affected_slides_not_complete={pending_affected_slides_count}"
    )
    if release:
        result.require(
            candidate_count == 0,
            f"release mode: {candidate_count} checklist items are not frozen",
        )
        result.require(
            pending_provenance_count == 0,
            "release mode: "
            f"{pending_provenance_count} checklist provenance records are not complete",
        )
        result.require(
            pending_evidence_count == 0,
            f"release mode: {pending_evidence_count} checklist evidence records are not complete",
        )
        result.require(
            pending_affected_slides_count == 0,
            "release mode: "
            f"{pending_affected_slides_count} automatic-fail affected-slide mappings "
            "are not complete",
        )


def validate_mutation_fixtures(result: Validation) -> None:
    """Validate generated operator coverage without treating it as release evidence."""
    fixture_dir = BENCHMARK / "fixtures" / "mutations"
    paths = {
        "index": fixture_dir / "fixture-index-v1.json",
        "expectations": fixture_dir / "mutation-expectations-v1.json",
        "execution": fixture_dir / "execution-report-v1.json",
    }
    for label, path in paths.items():
        result.require(path.is_file(), f"generated mutation {label} is missing: {path}")
    if not all(path.is_file() for path in paths.values()):
        return

    index = json.loads(paths["index"].read_text(encoding="utf-8"))
    expectations = json.loads(paths["expectations"].read_text(encoding="utf-8"))
    execution = json.loads(paths["execution"].read_text(encoding="utf-8"))
    index_entries = index.get("entries", [])
    expectation_entries = expectations.get("expectations", [])
    execution_entries = execution.get("results", [])
    item_ids = [entry.get("checklist_item_id") for entry in index_entries]

    result.require(len(index_entries) == 280, "mutation fixture index must contain 280 entries")
    result.require(len(set(item_ids)) == 280, "mutation fixture checklist IDs must be unique")
    result.require(
        index.get("summary", {}).get("executable_items") == 280,
        "all 280 current checklist operators must have executable generated fixtures",
    )
    result.require(
        index.get("summary", {}).get("assertion_evidence_complete") == 0,
        "generated operator fixtures must not claim independent assertion evidence",
    )
    result.require(
        all(entry.get("release_evidence_claimed") is False for entry in index_entries),
        "fixture index contains a fabricated release-evidence claim",
    )
    result.require(
        len(expectation_entries) == 280
        and all(entry.get("fault_count") == 1 for entry in expectation_entries),
        "mutation expectations must contain 280 single-fault records",
    )
    result.require(
        all(entry.get("release_evidence_claimed") is False for entry in expectation_entries),
        "mutation expectations contain a fabricated release-evidence claim",
    )
    result.require(
        len(execution_entries) == 280
        and all(entry.get("positive_passed") is True for entry in execution_entries)
        and all(entry.get("negative_passed") is False for entry in execution_entries)
        and all(entry.get("mutant_killed") is True for entry in execution_entries),
        "generated mutation execution must pass 280 positives and kill 280 negatives",
    )
    result.require(
        execution.get("summary", {}).get("assertion_evidence_completed_by_this_run") == 0,
        "generated execution report must not complete assertion evidence",
    )

    registry_path = BENCHMARK / "requirements" / "affected-slide-selectors-v1.json"
    result.require(registry_path.is_file(), "affected-slide selector registry is missing")
    if registry_path.is_file():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        bindings: dict[str, str] = {}
        for entry in registry.get("selectors", []):
            descriptor_bytes = json.dumps(
                entry.get("descriptor"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            actual_hash = f"sha256:{hashlib.sha256(descriptor_bytes).hexdigest()}"
            selector_id = entry.get("selector_id", "<missing>")
            result.require(
                entry.get("selector_sha256") == actual_hash,
                f"affected-slide selector hash mismatch: {selector_id}",
            )
            bindings[selector_id] = actual_hash
        deck_documents = {
            document["id"]: document
            for document in yaml.safe_load_all(
                (BENCHMARK / "checklist" / "deck.yaml").read_text(encoding="utf-8")
            )
            if document is not None
        }
        for item_id in ("deck.font-policy", "deck.no-notes"):
            affected = deck_documents[item_id]["failure_mode"]["affected_slides"]
            result.require(
                affected.get("status") == "complete"
                and affected.get("mode") == "named_selector"
                and affected.get("slides") == []
                and bindings.get(affected.get("selector_id")) == affected.get("selector_sha256"),
                f"{item_id}: named affected-slide binding is incomplete or stale",
            )
        for entry in index_entries:
            if entry.get("checklist_item_id") not in {
                "deck.font-policy",
                "deck.no-notes",
            }:
                continue
            result.require(
                entry.get("operator_coverage_status") == "executable",
                f"{entry.get('checklist_item_id')}: affected-slide operator is not executable",
            )

    result.notes.append(
        "generated operator fixtures: 280/280 positives passed, 280/280 single-fault "
        "mutants killed; independent assertion evidence completed=0/280"
    )


def validate_tiers(result: Validation) -> None:
    expected = {1: list(range(1, 6)), 2: list(range(1, 13)), 3: list(range(1, 21))}
    for tier, slides in expected.items():
        path = BENCHMARK / "tiers" / f"level-{tier}" / "slides.json"
        result.require(path.is_file(), f"tier {tier}: slides.json is missing")
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            result.require(payload.get("tier") == tier, f"tier {tier}: tier field mismatch")
            result.require(
                payload.get("slides") == slides,
                f"tier {tier}: expected prefix {slides}, found {payload.get('slides')}",
            )


def validate_release_documents(result: Validation, release: bool) -> None:
    """Require explicit public-document freeze state for a release build."""
    if not release:
        return
    repository = ROOT.parent
    openspec = repository / "GLOSS_OPENSPEC.md"
    readme = repository / "README.md"
    result.require(openspec.is_file(), "release mode: GLOSS_OPENSPEC.md is missing")
    result.require(readme.is_file(), "release mode: README.md is missing")
    if openspec.is_file():
        status_lines = [
            line
            for line in openspec.read_text(encoding="utf-8").splitlines()
            if line.startswith("Status:")
        ]
        result.require(
            status_lines == ["Status: Frozen — gloss-v1.0.0"],
            "release mode: OpenSpec status must be exactly 'Status: Frozen — gloss-v1.0.0'",
        )
    if readme.is_file():
        result.require(
            "> **Pre-release status:**" not in readme.read_text(encoding="utf-8"),
            "release mode: README still declares pre-release status",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release",
        action="store_true",
        help="also require completed independent-author prompt convergence",
    )
    args = parser.parse_args()
    result = Validation()
    validate_assets(result)
    validate_fonts(result)
    validate_prompts(result, args.release)
    validate_checklist(result, args.release)
    validate_mutation_fixtures(result)
    validate_tiers(result)
    validate_normative(result, args.release)
    validate_release_documents(result, args.release)
    if result.errors:
        print("Gloss corpus validation: FAIL")
        for error in result.errors:
            print(f"- {error}")
        for note in result.notes:
            print(f"- note: {note}")
        return 1
    print("Gloss corpus validation: PASS")
    print("- prompts: 1 deck + 60 slide variants + 20 validation records")
    print("- checklist: 280 unique schema-valid items; severity 84/112/84 (30/40/30)")
    print("- manifests: 3 CC0 assets + 26 redistributable pinned font files")
    for note in result.notes:
        print(f"- note: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
