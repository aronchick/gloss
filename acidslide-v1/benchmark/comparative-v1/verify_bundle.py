# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Verify every published claim in the frozen Gloss comparative-v1 bundle."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Final
from xml.etree import ElementTree

import yaml


PATHS: Final = (
    "native-precise",
    "native-fast",
    "visual-precise",
    "visual-fast",
)
RUNS: Final = (1, 2, 3)
DISCLOSURE: Final = {
    "attribution": "repository-owned path; no model attribution",
    "comparison_scope": "reproducible workflow baselines, not model rankings",
    "verification_label": "local artifact score; self-reported",
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def prefixed_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_visual_item_ids(checklist_root: Path) -> set[str]:
    result: set[str] = set()
    files = [
        checklist_root / "deck.yaml",
        *sorted((checklist_root / "slides").glob("*.yaml")),
    ]
    for path in files:
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not document:
                continue
            documents = document if isinstance(document, list) else [document]
            for item in documents:
                if item.get("verification", {}).get("method") == "visual_ssim":
                    result.add(str(item["id"]))
    return result


def verify_deck(path: Path) -> None:
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        slides = [
            name
            for name in names
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        ]
        require(len(slides) == 20, f"{path}: expected 20 slides")
        require(
            not any(
                "printerSettings" in name or name.endswith("vbaProject.bin")
                for name in names
            ),
            f"{path}: prohibited package part present",
        )
        presentation = ElementTree.fromstring(package.read("ppt/presentation.xml"))
    size = presentation.find(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz"
    )
    require(size is not None, f"{path}: missing p:sldSz")
    require(
        size.get("cx") == "12192000" and size.get("cy") == "6858000",
        f"{path}: non-canonical slide dimensions",
    )


def calculate_metrics(
    report: dict[str, Any],
    visual_item_ids: set[str],
) -> dict[str, Any]:
    items = [
        *report["deck_items"],
        *(item for slide in report["slides"] for item in slide["items"]),
    ]
    native_items = [
        item
        for item in items
        if item["id"] not in visual_item_ids and item["weight"] > 0
    ]
    native_total = sum(item["weight"] for item in native_items)
    native_passed = sum(item["weight"] for item in native_items if item["passed"])
    visual_scores = [
        slide["visual_ssim"]
        for slide in report["slides"]
        if slide["visual_ssim"] is not None
    ]
    return {
        "local_fidelity_percent": round(report["fidelity_score"] * 100, 2),
        "mean_visual_ssim_percent": round(
            sum(visual_scores) / len(visual_scores) * 100,
            2,
        ),
        "native_weight_passed": native_passed,
        "native_weight_total": native_total,
        "native_weighted_pass_percent": round(
            native_passed / native_total * 100,
            2,
        ),
        "scoring_completed": report["scoring_completed"],
        "verification_complete": report["verification_complete"],
    }


def verify_run(
    run_dir: Path,
    expected_path: str,
    expected_run: int,
    visual_item_ids: set[str],
    cohort_id: str,
) -> dict[str, Any]:
    required = {
        "artifact-context.json",
        "artifact-sha256.json",
        "deck.pptx",
        "generation.json",
        "report.json",
    }
    require(
        required.issubset(path.name for path in run_dir.iterdir()),
        f"{run_dir}: missing required artifacts",
    )
    verify_deck(run_dir / "deck.pptx")
    hashes = read_json(run_dir / "artifact-sha256.json")
    for name, expected_hash in hashes.items():
        require(
            prefixed_sha256(run_dir / name) == expected_hash,
            f"{run_dir / name}: hash mismatch",
        )

    generation = read_json(run_dir / "generation.json")
    require(generation["path_id"] == expected_path, f"{run_dir}: path mismatch")
    require(generation["run"] == expected_run, f"{run_dir}: run mismatch")
    require(
        generation["generation_attribution"] == DISCLOSURE["attribution"],
        f"{run_dir}: attribution mismatch",
    )
    require(
        generation["verification_label"] == DISCLOSURE["verification_label"],
        f"{run_dir}: verification label mismatch",
    )
    require(
        generation["external_resources_used"] is False,
        f"{run_dir}: external resources claimed",
    )

    context = read_json(run_dir / "artifact-context.json")
    report = read_json(run_dir / "report.json")
    require(report["scoring_cohort_id"] == cohort_id, f"{run_dir}: cohort mismatch")
    require(report["grading_mode"] == "local", f"{run_dir}: non-local report")
    require(report["run_kind"] == "submission", f"{run_dir}: run kind mismatch")
    require(report["eligible"] is False, f"{run_dir}: local report marked eligible")
    require(
        report["verification_label"] == DISCLOSURE["verification_label"],
        f"{run_dir}: report label mismatch",
    )
    require(report["schema_valid"] is True, f"{run_dir}: schema invalid")
    require(
        report["schema_validation_performed"] is True,
        f"{run_dir}: schema validation not performed",
    )
    require(
        report["visual_verification_performed"] is True,
        f"{run_dir}: visual verification not performed",
    )
    require(
        report["verification_complete"] is True,
        f"{run_dir}: verification incomplete",
    )
    require(report["scoring_completed"] is True, f"{run_dir}: score incomplete")
    require(not report["verification_errors"], f"{run_dir}: verification errors")
    require(not report["schema_violations"], f"{run_dir}: schema violations")
    require(
        report["model_key"] is None and report["model_revision_key"] is None,
        f"{run_dir}: prohibited model attribution",
    )
    require(
        report["submission_sha256"] == context["submission_sha256"],
        f"{run_dir}: submission identity mismatch",
    )
    require(
        report["generation_seed"] == str(generation["seed"]),
        f"{run_dir}: generation seed mismatch",
    )
    return {
        "metrics": calculate_metrics(report, visual_item_ids),
        "path_id": expected_path,
        "run": expected_run,
        "seed": generation["seed"],
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    benchmark_root = root.parent
    summary = read_json(root / "summary.json")
    cohort = read_json(root / "cohort.json")
    manifest = read_json(root / "manifest.json")
    require(summary["disclosure"] == DISCLOSURE, "summary disclosure mismatch")
    require(
        summary["totals"]
        == {
            "runs": 12,
            "seeds": [1103, 2207, 3301],
            "slides": 240,
        },
        "summary totals mismatch",
    )
    require(manifest["disclosure"] == DISCLOSURE, "manifest disclosure mismatch")
    require(
        manifest["summary_sha256"] == prefixed_sha256(root / "summary.json"),
        "summary hash mismatch",
    )
    require(
        manifest["cohort_sha256"] == prefixed_sha256(root / "cohort.json"),
        "cohort hash mismatch",
    )
    for name, expected_hash in manifest["source_hashes"].items():
        require(
            prefixed_sha256(root / name) == expected_hash,
            f"{name}: source hash mismatch",
        )

    visual_item_ids = load_visual_item_ids(benchmark_root / "checklist")
    cohort_id = cohort["provenance"]["scoring_cohort_id"]
    actual_runs: list[dict[str, Any]] = []
    for path_id in PATHS:
        for run in RUNS:
            actual_runs.append(
                verify_run(
                    root / "runs" / path_id / f"run-{run}",
                    path_id,
                    run,
                    visual_item_ids,
                    cohort_id,
                )
            )
    require(len(actual_runs) == 12, "expected 12 verified runs")

    manifest_runs = manifest["runs"]
    require(len(manifest_runs) == 12, "manifest must contain 12 runs")
    for actual in actual_runs:
        recorded = next(
            item
            for item in manifest_runs
            if item["path_id"] == actual["path_id"] and item["run"] == actual["run"]
        )
        require(
            recorded["metrics"] == actual["metrics"],
            f"{actual['path_id']}/run-{actual['run']}: metric mismatch",
        )

    for path in summary["paths"]:
        runs = [item for item in actual_runs if item["path_id"] == path["path_id"]]
        for metric in (
            "local_fidelity_percent",
            "mean_visual_ssim_percent",
            "native_weighted_pass_percent",
        ):
            expected_mean = round(
                sum(float(item["metrics"][metric]) for item in runs) / 3,
                2,
            )
            require(
                path["mean_metrics"][metric] == expected_mean,
                f"{path['path_id']}: {metric} mean mismatch",
            )

    print(
        "comparative-v1 verified: 12/12 runs, 240 slides, "
        "all hashes and published metrics reproduced"
    )


if __name__ == "__main__":
    main()
