"""Fail-closed validation for review and release-evidence projections."""

from __future__ import annotations

import hashlib
import math
from typing import TYPE_CHECKING, Any, Protocol

import rfc8785

if TYPE_CHECKING:
    from collections.abc import Mapping

EXPORT_RUN_COUNT = 100
EXPORT_PAGE_COUNT = 20
EXPORT_RUN_PAIR_COUNT = 4_950
EXPORT_PAGE_PAIR_COMPARISON_COUNT = 99_000
EXPORT_REQUIRED_MINIMUM_SSIM = 0.99999


class ValidationResult(Protocol):
    """Minimal result collector used by normative and release validation."""

    errors: list[str]
    notes: list[str]

    def require(self, condition: bool, message: str) -> None: ...


def prompt_oracle_review_sha256(oracle: dict[str, Any]) -> str:
    """Hash the domain-separated, approval-free prompt-oracle projection."""
    projection: dict[str, Any] = {
        "domain": "AcidSlide prompt requirements oracle review v1",
        "oracle": {key: value for key, value in oracle.items() if key != "independent_reviews"},
    }
    return hashlib.sha256(rfc8785.dumps(projection)).hexdigest()


def assertion_inventory_review_sha256(inventory: dict[str, Any]) -> str:
    """Hash the domain-separated, approval-free assertion-inventory projection."""
    projection: dict[str, Any] = {
        "domain": "AcidSlide scored assertion inventory review v1",
        "inventory": {key: value for key, value in inventory.items() if key != "review"},
    }
    return f"sha256:{hashlib.sha256(rfc8785.dumps(projection)).hexdigest()}"


def validate_prompt_review_approvals(
    result: ValidationResult,
    oracle: dict[str, Any],
) -> None:
    """Require two distinct approvals over the exact prompt-oracle projection."""
    approvals_value = oracle.get("independent_reviews", [])
    approvals = approvals_value if isinstance(approvals_value, list) else []
    valid_approvals = [approval for approval in approvals if isinstance(approval, dict)]
    reviewer_ids = [
        approval.get("reviewer_id")
        for approval in valid_approvals
        if isinstance(approval.get("reviewer_id"), str)
    ]
    expected_sha256 = prompt_oracle_review_sha256(oracle)
    result.require(
        len(valid_approvals) >= 2
        and len(valid_approvals) == len(approvals)
        and len(reviewer_ids) == len(valid_approvals)
        and len(reviewer_ids) == len(set(reviewer_ids)),
        "release mode: prompt requirements oracle lacks two distinct reviewer approvals",
    )
    result.require(
        bool(valid_approvals)
        and all(
            approval.get("decision") == "approved"
            and approval.get("reviewed_oracle_sha256") == expected_sha256
            for approval in valid_approvals
        ),
        "release mode: prompt reviewer approval hash does not match the review projection",
    )


def validate_assertion_inventory_approvals(
    result: ValidationResult,
    inventory: dict[str, Any],
) -> None:
    """Require two distinct approvals over the exact assertion projection."""
    review = inventory.get("review", {})
    approvals_value = review.get("reviewer_approvals", []) if isinstance(review, dict) else []
    approvals = approvals_value if isinstance(approvals_value, list) else []
    valid_approvals = [approval for approval in approvals if isinstance(approval, dict)]
    reviewer_ids = [
        approval.get("reviewer_id")
        for approval in valid_approvals
        if isinstance(approval.get("reviewer_id"), str)
    ]
    expected_sha256 = assertion_inventory_review_sha256(inventory)
    result.require(
        isinstance(review, dict)
        and review.get("status") == "approved"
        and len(valid_approvals) >= 2
        and len(valid_approvals) == len(approvals)
        and len(reviewer_ids) == len(valid_approvals)
        and len(reviewer_ids) == len(set(reviewer_ids)),
        "release mode: scored assertion inventory lacks two distinct reviewer approvals",
    )
    result.require(
        bool(valid_approvals)
        and all(
            approval.get("inventory_sha256") == expected_sha256 for approval in valid_approvals
        ),
        "release mode: assertion reviewer approval hash does not match the review projection",
    )


def _objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _score(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    score = float(value)
    return score if math.isfinite(score) and 0.0 <= score <= 1.0 else None


def validate_export_determinism_evidence(
    result: ValidationResult,
    evidence: dict[str, Any],
    *,
    expected_bindings: Mapping[str, Any] | None = None,
) -> None:
    """Recompute the complete 100-run export-determinism evidence matrix."""
    if not evidence:
        return

    threshold = _score(evidence.get("required_minimum_ssim"))
    result.require(
        threshold == EXPORT_REQUIRED_MINIMUM_SSIM,
        "export determinism evidence has the wrong required minimum SSIM",
    )
    result.require(
        evidence.get("run_count") == EXPORT_RUN_COUNT
        and evidence.get("page_count") == EXPORT_PAGE_COUNT
        and evidence.get("run_pair_count") == EXPORT_RUN_PAIR_COUNT
        and evidence.get("page_pair_comparison_count") == EXPORT_PAGE_PAIR_COMPARISON_COUNT,
        "export determinism evidence declares the wrong run/comparison counts",
    )

    bindings = evidence.get("bindings")
    if expected_bindings is not None:
        result.require(
            isinstance(bindings, dict) and bindings == dict(expected_bindings),
            "export determinism evidence is bound to the wrong environment or gold identity",
        )

    expected_pages = list(range(1, EXPORT_PAGE_COUNT + 1))
    runs = _objects(evidence.get("runs"))
    result.require(
        len(runs) == EXPORT_RUN_COUNT
        and [run.get("run") for run in runs] == list(range(1, EXPORT_RUN_COUNT + 1)),
        "export determinism evidence runs must be ordered exactly 1..100",
    )
    for run in runs:
        pages = _objects(run.get("pages"))
        result.require(
            len(pages) == EXPORT_PAGE_COUNT
            and [page.get("page") for page in pages] == expected_pages,
            f"export determinism run {run.get('run')} pages must be ordered exactly 1..20",
        )

    canonical_run_number = evidence.get("canonical_run")
    result.require(
        canonical_run_number == 1,
        "export determinism evidence canonical_run must be run 1",
    )
    if runs and isinstance(bindings, dict):
        canonical_run = runs[0]
        canonical_pages = _objects(canonical_run.get("pages"))
        result.require(
            canonical_run.get("pdf_sha256") == bindings.get("canonical_pdf_sha256")
            and [page.get("png_sha256") for page in canonical_pages]
            == bindings.get("canonical_png_sha256s"),
            "export determinism canonical run does not match the bound gold export hashes",
        )

    expected_pairs = [
        (run_a, run_b)
        for run_a in range(1, EXPORT_RUN_COUNT + 1)
        for run_b in range(run_a + 1, EXPORT_RUN_COUNT + 1)
    ]
    run_pairs = _objects(evidence.get("run_pairs"))
    actual_pairs = [(pair.get("run_a"), pair.get("run_b")) for pair in run_pairs]
    result.require(
        len(run_pairs) == EXPORT_RUN_PAIR_COUNT and actual_pairs == expected_pairs,
        "export determinism run pairs must be the ordered complete 100-choose-2 matrix",
    )

    comparison_count = 0
    all_scores: list[float] = []
    scores_by_page: dict[int, list[float]] = {page: [] for page in range(1, EXPORT_PAGE_COUNT + 1)}
    pair_minima_match = True
    pair_pages_match = True
    for pair in run_pairs:
        comparisons = _objects(pair.get("page_comparisons"))
        comparison_count += len(comparisons)
        if (
            len(comparisons) != EXPORT_PAGE_COUNT
            or [comparison.get("page") for comparison in comparisons] != expected_pages
        ):
            pair_pages_match = False
        pair_scores: list[float] = []
        for comparison in comparisons:
            page = comparison.get("page")
            score = _score(comparison.get("ssim"))
            if score is None:
                continue
            pair_scores.append(score)
            all_scores.append(score)
            if isinstance(page, int) and page in scores_by_page:
                scores_by_page[page].append(score)
        recorded_minimum = _score(pair.get("minimum_ssim"))
        if (
            len(pair_scores) != EXPORT_PAGE_COUNT
            or recorded_minimum is None
            or recorded_minimum != min(pair_scores)
        ):
            pair_minima_match = False

    result.require(
        pair_pages_match,
        "each export determinism run pair must compare pages exactly 1..20",
    )
    result.require(
        comparison_count == EXPORT_PAGE_PAIR_COMPARISON_COUNT
        and len(all_scores) == EXPORT_PAGE_PAIR_COMPARISON_COUNT,
        "export determinism evidence must contain exactly 99,000 numeric page comparisons",
    )
    result.require(
        pair_minima_match,
        "export determinism run-pair minimum SSIM values do not recompute",
    )

    recorded_page_minima = _objects(evidence.get("minimum_ssim_by_page"))
    page_minima_match = (
        len(recorded_page_minima) == EXPORT_PAGE_COUNT
        and [item.get("page") for item in recorded_page_minima] == expected_pages
    )
    computed_page_minima: list[float] = []
    for page, item in zip(expected_pages, recorded_page_minima, strict=False):
        scores = scores_by_page[page]
        recorded = _score(item.get("minimum_ssim"))
        if len(scores) != EXPORT_RUN_PAIR_COUNT:
            page_minima_match = False
            continue
        computed = min(scores)
        computed_page_minima.append(computed)
        if recorded != computed:
            page_minima_match = False
    result.require(
        page_minima_match and len(computed_page_minima) == EXPORT_PAGE_COUNT,
        "export determinism per-page minimum SSIM values do not recompute",
    )

    recorded_global_minimum = _score(evidence.get("global_minimum_ssim"))
    computed_global_minimum = min(all_scores) if all_scores else None
    result.require(
        recorded_global_minimum is not None
        and recorded_global_minimum == computed_global_minimum
        and bool(computed_page_minima)
        and recorded_global_minimum == min(computed_page_minima),
        "export determinism global minimum SSIM does not recompute",
    )
    result.require(
        threshold is not None
        and bool(computed_page_minima)
        and all(minimum >= threshold for minimum in computed_page_minima)
        and computed_global_minimum is not None
        and computed_global_minimum >= threshold,
        "export determinism per-page or global minimum SSIM is below 0.99999",
    )
