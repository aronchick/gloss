"""Tests for the normative 100-run export-determinism evidence contract."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import jsonschema

from gloss.release_evidence import validate_export_determinism_evidence

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas" / "export-determinism-evidence.schema.json"
)


@dataclass
class _Result:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def _hash(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _evidence() -> tuple[dict[str, Any], dict[str, Any]]:
    canonical_pngs = [_hash(f"canonical-page-{page}") for page in range(1, 21)]
    bindings: dict[str, Any] = {
        "environment_attestation_sha256": _hash("environment"),
        "original_gold_sha256": _hash("original-gold"),
        "resolved_gold_sha256": _hash("resolved-gold"),
        "canonical_package_hash_profile_sha256": _hash("package-profile"),
        "canonical_package_hash_v1": _hash("canonical-package"),
        "canonical_pdf_sha256": _hash("canonical-pdf"),
        "canonical_png_sha256s": canonical_pngs,
        "export_profile_sha256": _hash("export-profile"),
        "ssim_profile_sha256": _hash("ssim-profile"),
    }
    runs = []
    for run in range(1, 101):
        runs.append(
            {
                "run": run,
                "pdf_sha256": (
                    bindings["canonical_pdf_sha256"] if run == 1 else _hash(f"pdf-{run}")
                ),
                "export_bundle_sha256": _hash(f"export-bundle-{run}"),
                "pages": [
                    {
                        "page": page,
                        "png_sha256": (
                            canonical_pngs[page - 1]
                            if run == 1
                            else _hash(f"run-{run}-page-{page}")
                        ),
                    }
                    for page in range(1, 21)
                ],
            }
        )
    run_pairs = [
        {
            "run_a": run_a,
            "run_b": run_b,
            "page_comparisons": [{"page": page, "ssim": 1.0} for page in range(1, 21)],
            "minimum_ssim": 1.0,
        }
        for run_a in range(1, 101)
        for run_b in range(run_a + 1, 101)
    ]
    return (
        {
            "schema_version": "1.0",
            "evidence_id": "gloss-export-determinism-evidence-v1",
            "benchmark_version": "gloss-v1.0.0",
            "canonicalization": "RFC8785-JCS",
            "measured_at": "2026-07-18T00:00:00Z",
            "bindings": copy.deepcopy(bindings),
            "run_count": 100,
            "page_count": 20,
            "run_pair_count": 4950,
            "page_pair_comparison_count": 99000,
            "required_minimum_ssim": 0.99999,
            "canonical_run": 1,
            "runs": runs,
            "run_pairs": run_pairs,
            "minimum_ssim_by_page": [{"page": page, "minimum_ssim": 1.0} for page in range(1, 21)],
            "global_minimum_ssim": 1.0,
        },
        bindings,
    )


BASE_EVIDENCE, EXPECTED_BINDINGS = _evidence()


def _schema_validator() -> jsonschema.Draft202012Validator:
    schema = cast("dict[str, Any]", json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )


def test_complete_100_run_matrix_validates_and_recomputes() -> None:
    evidence = copy.deepcopy(BASE_EVIDENCE)
    _schema_validator().validate(evidence)
    result = _Result()

    validate_export_determinism_evidence(
        result,
        evidence,
        expected_bindings=EXPECTED_BINDINGS,
    )

    assert result.errors == []
    assert len(cast("list[Any]", evidence["runs"])) == 100
    assert len(cast("list[Any]", evidence["run_pairs"])) == 4950
    assert (
        sum(
            len(cast("list[Any]", pair["page_comparisons"]))
            for pair in cast("list[dict[str, Any]]", evidence["run_pairs"])
        )
        == 99000
    )


def test_environment_gold_or_score_tampering_fails_closed() -> None:
    evidence = copy.deepcopy(BASE_EVIDENCE)
    bindings = cast("dict[str, Any]", evidence["bindings"])
    bindings["resolved_gold_sha256"] = _hash("substituted-gold")
    first_pair = cast("list[dict[str, Any]]", evidence["run_pairs"])[0]
    cast("list[dict[str, Any]]", first_pair["page_comparisons"])[0]["ssim"] = 0.999995
    result = _Result()

    validate_export_determinism_evidence(
        result,
        evidence,
        expected_bindings=EXPECTED_BINDINGS,
    )

    assert any("wrong environment or gold identity" in error for error in result.errors)
    assert any("run-pair minimum" in error for error in result.errors)
    assert any("per-page minimum" in error for error in result.errors)


def test_missing_run_pair_and_page_comparisons_fail_exact_counts() -> None:
    evidence = copy.deepcopy(BASE_EVIDENCE)
    cast("list[Any]", evidence["run_pairs"]).pop()
    evidence["page_pair_comparison_count"] = 98980
    schema_errors = list(_schema_validator().iter_errors(evidence))
    result = _Result()

    validate_export_determinism_evidence(
        result,
        evidence,
        expected_bindings=EXPECTED_BINDINGS,
    )

    assert schema_errors
    assert any("wrong run/comparison counts" in error for error in result.errors)
    assert any("100-choose-2" in error for error in result.errors)
    assert any("99,000" in error for error in result.errors)


def test_recomputed_minimum_below_099999_fails_threshold() -> None:
    evidence = copy.deepcopy(BASE_EVIDENCE)
    first_pair = cast("list[dict[str, Any]]", evidence["run_pairs"])[0]
    cast("list[dict[str, Any]]", first_pair["page_comparisons"])[0]["ssim"] = 0.99998
    first_pair["minimum_ssim"] = 0.99998
    page_minima = cast("list[dict[str, Any]]", evidence["minimum_ssim_by_page"])
    page_minima[0]["minimum_ssim"] = 0.99998
    evidence["global_minimum_ssim"] = 0.99998
    result = _Result()

    validate_export_determinism_evidence(
        result,
        evidence,
        expected_bindings=EXPECTED_BINDINGS,
    )

    assert result.errors == ["export determinism per-page or global minimum SSIM is below 0.99999"]
