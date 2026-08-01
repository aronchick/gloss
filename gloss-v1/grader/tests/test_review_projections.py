"""Tests for domain-separated independent-review approval bindings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gloss.release_evidence import (
    assertion_inventory_review_sha256,
    prompt_oracle_review_sha256,
)
from gloss.release_evidence import (
    validate_assertion_inventory_approvals as _validate_assertion_inventory_approvals,
)
from gloss.release_evidence import (
    validate_prompt_review_approvals as _validate_prompt_review_approvals,
)


@dataclass
class _Result:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def _oracle() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "oracle_id": "gloss-prompt-requirements-v1",
        "benchmark_version": "gloss-v1.0.0",
        "freeze_status": "frozen",
        "sources": [{"source_id": "deck-prompt", "sha256": "a" * 64}],
        "independent_reviews": [],
        "requirements": [{"requirement_id": "deck.prompt-r001", "statement": "Exact"}],
    }


def _inventory() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "inventory_id": "gloss-scored-assertion-inventory-v1",
        "lifecycle_state": "frozen",
        "benchmark_version": "gloss-v1.0.0",
        "prompt_bundle_sha256": f"sha256:{'1' * 64}",
        "reference_image_bundle_sha256": f"sha256:{'2' * 64}",
        "asset_manifest_sha256": f"sha256:{'3' * 64}",
        "review": {"status": "pending", "reason": "fixture"},
        "assertions": [{"assertion_id": "deck.assert-example", "expectation": "Exact"}],
    }


def test_prompt_review_projection_requires_matching_hashes_and_distinct_reviewers() -> None:
    oracle = _oracle()
    expected = prompt_oracle_review_sha256(oracle)
    oracle["independent_reviews"] = [
        {"reviewer_id": "reviewer-a", "reviewed_oracle_sha256": expected, "decision": "approved"},
        {"reviewer_id": "reviewer-b", "reviewed_oracle_sha256": expected, "decision": "approved"},
    ]
    result = _Result()

    _validate_prompt_review_approvals(result, oracle)

    assert result.errors == []
    assert prompt_oracle_review_sha256(oracle) == expected

    oracle["requirements"][0]["statement"] = "Tampered"
    tampered = _Result()
    _validate_prompt_review_approvals(tampered, oracle)
    assert any("hash does not match" in error for error in tampered.errors)

    oracle = _oracle()
    expected = prompt_oracle_review_sha256(oracle)
    oracle["independent_reviews"] = [
        {"reviewer_id": "same", "reviewed_oracle_sha256": expected, "decision": "approved"},
        {"reviewer_id": "same", "reviewed_oracle_sha256": expected, "decision": "approved"},
    ]
    duplicate = _Result()
    _validate_prompt_review_approvals(duplicate, oracle)
    assert any("distinct reviewer" in error for error in duplicate.errors)


def test_inventory_review_projection_requires_matching_hashes_and_distinct_reviewers() -> None:
    inventory = _inventory()
    expected = assertion_inventory_review_sha256(inventory)
    inventory["review"] = {
        "status": "approved",
        "reviewer_approvals": [
            {
                "reviewer_id": "reviewer-a",
                "approved_at": "2026-07-18T00:00:00Z",
                "inventory_sha256": expected,
            },
            {
                "reviewer_id": "reviewer-b",
                "approved_at": "2026-07-18T00:01:00Z",
                "inventory_sha256": expected,
            },
        ],
    }
    result = _Result()

    _validate_assertion_inventory_approvals(result, inventory)

    assert result.errors == []
    assert assertion_inventory_review_sha256(inventory) == expected
    assert expected.startswith("sha256:")

    inventory["assertions"][0]["expectation"] = "Tampered"
    tampered = _Result()
    _validate_assertion_inventory_approvals(tampered, inventory)
    assert any("hash does not match" in error for error in tampered.errors)

    inventory = _inventory()
    expected = assertion_inventory_review_sha256(inventory)
    inventory["review"] = {
        "status": "approved",
        "reviewer_approvals": [
            {
                "reviewer_id": "same",
                "approved_at": "2026-07-18T00:00:00Z",
                "inventory_sha256": expected,
            },
            {
                "reviewer_id": "same",
                "approved_at": "2026-07-18T00:01:00Z",
                "inventory_sha256": expected,
            },
        ],
    }
    duplicate = _Result()
    _validate_assertion_inventory_approvals(duplicate, inventory)
    assert any("distinct reviewer" in error for error in duplicate.errors)


def test_review_domains_are_distinct() -> None:
    oracle_hash = prompt_oracle_review_sha256(_oracle())
    inventory_hash = assertion_inventory_review_sha256(_inventory())

    assert inventory_hash != f"sha256:{oracle_hash}"
