# /// script
# requires-python = ">=3.12"
# ///
"""Grade the frozen Gloss comparative bundle inside the canonical container.

This deliberately bypasses signed-release loading and supplies an explicit local
cohort to the grader. The resulting reports are non-official, self-reported
artifact scores and contain no model attribution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Final

import rfc8785

from acidslide.checklist import load_checklist
from acidslide.environment import environment_details
from acidslide.models import (
    ArtifactReportContext,
    GoldDuplicateCheck,
    GradingMode,
    RunKind,
)
from acidslide.package_hash import canonical_package_identity, sha256_file
from acidslide.pipeline import run_pipeline
from acidslide.provenance import (
    ScoringCohortProvenance,
    derive_scoring_cohort_id,
)


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


def prefixed_sha256(path: Path) -> str:
    return f"sha256:{sha256_file(path)}"


def canonical_hash(value: Any) -> str:
    return f"sha256:{hashlib.sha256(rfc8785.dumps(value)).hexdigest()}"


def tree_manifest(
    root: Path, *, excludes: tuple[str, ...] = ()
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(root).as_posix()
        if any(
            relative == item or relative.startswith(f"{item}/") for item in excludes
        ):
            continue
        entries.append(
            {
                "bytes": path.stat().st_size,
                "path": relative,
                "sha256": prefixed_sha256(path),
            }
        )
    return entries


def tree_hash(root: Path, *, excludes: tuple[str, ...] = ()) -> str:
    return canonical_hash(tree_manifest(root, excludes=excludes))


def git_revision(repo_root: Path) -> str:
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"
    return f"{revision}+working-tree" if dirty else revision


def build_cohort(
    benchmark_root: Path,
    schemas_root: Path,
    grader_root: Path,
    image_digest: str,
) -> tuple[
    dict[str, Any],
    ScoringCohortProvenance,
    dict[str, str],
    dict[str, Any],
]:
    runtime = environment_details()
    environment_attestation = {
        "container_image_digest": image_digest,
        "local_cohort": True,
        "render_runtime": runtime,
        "schema_version": "1.0",
    }
    bundle_hashes = {
        "asset_manifest_sha256": prefixed_sha256(
            benchmark_root / "assets" / "manifest.json"
        ),
        "checklist_bundle_sha256": tree_hash(benchmark_root / "checklist"),
        "font_manifest_sha256": prefixed_sha256(
            benchmark_root / "fonts" / "manifest.json"
        ),
        "grader_source_tree_sha256": tree_hash(
            grader_root,
            excludes=(
                ".mypy_cache",
                ".pytest_cache",
                ".ruff_cache",
                ".venv",
                "__pycache__",
                "dist",
            ),
        ),
        "prompt_bundle_sha256": tree_hash(benchmark_root / "prompts"),
        "schema_bundle_sha256": tree_hash(schemas_root),
        "scored_assertion_inventory_sha256": prefixed_sha256(
            benchmark_root / "requirements" / "scored-assertion-inventory.json"
        ),
    }
    scoring_manifest = {
        "bundle_hashes": bundle_hashes,
        "disclosure": DISCLOSURE,
        "environment_attestation_sha256": canonical_hash(environment_attestation),
        "image_digest": image_digest,
        "schema_version": "1.0",
    }
    scoring_manifest_sha256 = canonical_hash(scoring_manifest)
    cohort = ScoringCohortProvenance(
        scoring_cohort_id=derive_scoring_cohort_id(
            scoring_manifest_sha256,
            bundle_hashes["grader_source_tree_sha256"],
            scoring_manifest["environment_attestation_sha256"],
        ),
        scoring_manifest_sha256=scoring_manifest_sha256,
        grader_source_tree_sha256=bundle_hashes["grader_source_tree_sha256"],
        environment_attestation_sha256=scoring_manifest[
            "environment_attestation_sha256"
        ],
    )
    cohort.validate()
    return scoring_manifest, cohort, bundle_hashes, environment_attestation


def build_context(
    *,
    deck: Path,
    generation: dict[str, Any],
    generation_path: Path,
    gold: Path,
    cohort: ScoringCohortProvenance,
    bundle_hashes: dict[str, str],
    environment_attestation: dict[str, Any],
    image_digest: str,
) -> ArtifactReportContext:
    identity = canonical_package_identity(deck)
    gold_identity = canonical_package_identity(gold)
    submission_sha256 = prefixed_sha256(deck)
    gold_submission_sha256 = prefixed_sha256(gold)
    canonical_sha256 = f"sha256:{identity.canonical_package_sha256}"
    gold_canonical_sha256 = f"sha256:{gold_identity.canonical_package_sha256}"
    duplicate_check = (
        GoldDuplicateCheck.BYTE_MATCH
        if submission_sha256 == gold_submission_sha256
        else GoldDuplicateCheck.CANONICAL_MATCH
        if canonical_sha256 == gold_canonical_sha256
        else GoldDuplicateCheck.CLEAR
    )
    context = ArtifactReportContext(
        grading_mode=GradingMode.LOCAL,
        run_kind=RunKind.SUBMISSION,
        targeted_tier=3,
        prompt_variant=str(generation["prompt_variant"]),
        generation_seed=str(generation["seed"]),
        grader_package_sha256=cohort.grader_source_tree_sha256,
        oci_image_digest=image_digest,
        prompt_bundle_sha256=bundle_hashes["prompt_bundle_sha256"],
        scored_assertion_inventory_sha256=bundle_hashes[
            "scored_assertion_inventory_sha256"
        ],
        checklist_bundle_sha256=bundle_hashes["checklist_bundle_sha256"],
        schema_bundle_sha256=bundle_hashes["schema_bundle_sha256"],
        schema_root_map_sha256=f"sha256:{identity.schema_root_map_sha256}",
        mce_profile_sha256=f"sha256:{identity.mce_profile_sha256}",
        asset_manifest_sha256=bundle_hashes["asset_manifest_sha256"],
        font_manifest_sha256=bundle_hashes["font_manifest_sha256"],
        canonical_package_hash_profile_sha256=(
            f"sha256:{identity.package_hash_profile_sha256}"
        ),
        canonical_package_hash_v1=canonical_sha256,
        gold_duplicate_check=duplicate_check,
        submission_sha256=submission_sha256,
        mce_resolved_package_sha256=None,
        gold_submission_sha256=gold_submission_sha256,
        gold_mce_resolved_package_sha256=gold_submission_sha256,
        gold_canonical_package_hash_v1=gold_canonical_sha256,
        environment_attestation=environment_attestation,
        assistance_class="human-assisted",
        generation_profile_sha256=prefixed_sha256(generation_path),
        attested_metrics={
            "external_resources_used": generation["external_resources_used"],
            "human_intervention": generation["human_intervention"],
            "post_processing": generation["post_processing"],
        },
        attestation={
            "attribution": DISCLOSURE["attribution"],
            "generator_kind": generation["generator_kind"],
            "generator_sha256": generation["generator_sha256"],
        },
        submission_id=None,
        campaign_id=None,
        campaign_slot=None,
        robustness_group_id=None,
        submitter_id=None,
        model_key=None,
        model_revision_key=None,
    )
    context.validate()
    return context


def run_metrics(report: Any, visual_item_ids: set[str]) -> dict[str, Any]:
    items = [
        *report.deck_items,
        *(item for slide in report.slides for item in slide.items),
    ]
    native_items = [
        item for item in items if item.id not in visual_item_ids and item.weight > 0
    ]
    native_weight_total = sum(item.weight for item in native_items)
    native_weight_passed = sum(item.weight for item in native_items if item.passed)
    visual_scores = [
        slide.visual_ssim for slide in report.slides if slide.visual_ssim is not None
    ]
    return {
        "local_fidelity_percent": round(
            float(report.fidelity_score or 0.0) * 100,
            2,
        ),
        "mean_visual_ssim_percent": round(
            sum(visual_scores) / len(visual_scores) * 100,
            2,
        )
        if visual_scores
        else None,
        "native_weight_passed": native_weight_passed,
        "native_weight_total": native_weight_total,
        "native_weighted_pass_percent": round(
            native_weight_passed / native_weight_total * 100,
            2,
        )
        if native_weight_total
        else None,
        "scoring_completed": report.scoring_completed,
        "verification_complete": report.verification_complete,
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def freeze_existing_manifest(comparative_root: Path) -> None:
    summary_path = comparative_root / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    runs: list[dict[str, Any]] = []
    for path in summary["paths"]:
        for run in path["runs"]:
            run_dir = comparative_root / "runs" / run["path_id"] / f"run-{run['run']}"
            runs.append(
                {
                    **run,
                    "artifacts": json.loads(
                        (run_dir / "artifact-sha256.json").read_text(encoding="utf-8")
                    ),
                }
            )
    manifest = {
        "cohort_sha256": prefixed_sha256(comparative_root / "cohort.json"),
        "disclosure": DISCLOSURE,
        "reproduction_command": (
            "./acidslide-v1/benchmark/comparative-v1/reproduce.sh"
        ),
        "runs": runs,
        "schema_version": "1.0",
        "source_hashes": {
            "generate_baselines.py": prefixed_sha256(
                comparative_root / "generate_baselines.py"
            ),
            "score_bundle.py": prefixed_sha256(comparative_root / "score_bundle.py"),
        },
        "summary_sha256": prefixed_sha256(summary_path),
    }
    write_json(comparative_root / "manifest.json", manifest)


def score_all(
    comparative_root: Path,
    benchmark_root: Path,
    schemas_root: Path,
    grader_root: Path,
    image_digest: str,
) -> None:
    scoring_manifest, cohort, bundle_hashes, environment_attestation = build_cohort(
        benchmark_root,
        schemas_root,
        grader_root,
        image_digest,
    )
    repo_root = comparative_root.parents[2]
    cohort_document = {
        "disclosure": DISCLOSURE,
        "grader_revision": git_revision(repo_root),
        "provenance": {
            "environment_attestation_sha256": (cohort.environment_attestation_sha256),
            "grader_source_tree_sha256": cohort.grader_source_tree_sha256,
            "scoring_cohort_id": cohort.scoring_cohort_id,
            "scoring_manifest_sha256": cohort.scoring_manifest_sha256,
        },
        "scoring_manifest": scoring_manifest,
    }
    write_json(comparative_root / "cohort.json", cohort_document)

    visual_item_ids = {
        item.id
        for item in load_checklist(benchmark_root / "checklist", 3)
        if item.verification.method == "visual_ssim"
    }
    gold = benchmark_root / "deck" / "gold" / "acidslide-v1-gold.pptx"
    run_summaries: list[dict[str, Any]] = []
    for path_id in PATHS:
        for run in RUNS:
            run_dir = comparative_root / "runs" / path_id / f"run-{run}"
            deck = run_dir / "deck.pptx"
            generation_path = run_dir / "generation.json"
            generation = json.loads(generation_path.read_text(encoding="utf-8"))
            context = build_context(
                deck=deck,
                generation=generation,
                generation_path=generation_path,
                gold=gold,
                cohort=cohort,
                bundle_hashes=bundle_hashes,
                environment_attestation=environment_attestation,
                image_digest=image_digest,
            )
            context_path = run_dir / "artifact-context.json"
            write_json(context_path, context.as_dict())
            report = run_pipeline(
                deck,
                tier=3,
                artifact_context=context,
                benchmark_dir=benchmark_root,
                output_format="json",
                cohort_provenance=cohort,
            )
            report_path = run_dir / "report.json"
            report_path.write_text(report.to_json() + "\n", encoding="utf-8")
            metrics = run_metrics(report, visual_item_ids)
            run_summary = {
                "metrics": metrics,
                "path_id": path_id,
                "run": run,
                "seed": generation["seed"],
            }
            artifact_hashes = {
                "artifact-context.json": prefixed_sha256(context_path),
                "deck.pptx": prefixed_sha256(deck),
                "generation.json": prefixed_sha256(generation_path),
                "report.json": prefixed_sha256(report_path),
            }
            write_json(
                run_dir / "artifact-sha256.json",
                artifact_hashes,
            )
            run_summary["artifacts"] = artifact_hashes
            run_summaries.append(run_summary)
            print(
                f"{path_id}/run-{run}: "
                f"{metrics['local_fidelity_percent']:.2f}% local fidelity"
            )

    paths: list[dict[str, Any]] = []
    for path_id in PATHS:
        path_runs = [item for item in run_summaries if item["path_id"] == path_id]
        metric_names = (
            "local_fidelity_percent",
            "mean_visual_ssim_percent",
            "native_weighted_pass_percent",
        )
        means = {
            name: round(
                sum(float(item["metrics"][name]) for item in path_runs)
                / len(path_runs),
                2,
            )
            for name in metric_names
        }
        paths.append(
            {
                "label": str(
                    json.loads(
                        (
                            comparative_root
                            / "runs"
                            / path_id
                            / "run-1"
                            / "generation.json"
                        ).read_text(encoding="utf-8")
                    )["path_label"]
                ),
                "mean_metrics": means,
                "path_id": path_id,
                "runs": path_runs,
            }
        )
    summary = {
        "cohort": cohort_document["provenance"],
        "disclosure": DISCLOSURE,
        "metric_definitions": {
            "local_fidelity_percent": (
                "AcidSlide weighted artifact score multiplied by 100"
            ),
            "mean_visual_ssim_percent": (
                "mean slide SSIM against gold renders multiplied by 100"
            ),
            "native_weighted_pass_percent": (
                "severity-weighted checklist pass rate excluding visual_ssim checks"
            ),
        },
        "paths": paths,
        "schema_version": "1.0",
        "totals": {
            "runs": len(run_summaries),
            "seeds": sorted({item["seed"] for item in run_summaries}),
            "slides": len(run_summaries) * 20,
        },
    }
    summary_path = comparative_root / "summary.json"
    write_json(summary_path, summary)
    manifest = {
        "cohort_sha256": prefixed_sha256(comparative_root / "cohort.json"),
        "disclosure": DISCLOSURE,
        "reproduction_command": (
            "./acidslide-v1/benchmark/comparative-v1/reproduce.sh"
        ),
        "runs": run_summaries,
        "schema_version": "1.0",
        "source_hashes": {
            "generate_baselines.py": prefixed_sha256(
                comparative_root / "generate_baselines.py"
            ),
            "score_bundle.py": prefixed_sha256(comparative_root / "score_bundle.py"),
        },
        "summary_sha256": prefixed_sha256(summary_path),
    }
    write_json(comparative_root / "manifest.json", manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--comparative-root",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    parser.add_argument(
        "--benchmark-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--schemas-root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "schemas",
    )
    parser.add_argument(
        "--grader-root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "grader",
    )
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    if args.freeze_only:
        freeze_existing_manifest(args.comparative_root)
        return
    score_all(
        args.comparative_root,
        args.benchmark_root,
        args.schemas_root,
        args.grader_root,
        args.image_digest,
    )


if __name__ == "__main__":
    main()
