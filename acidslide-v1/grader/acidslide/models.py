"""Core data models for AcidSlide grader."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum
from html import escape
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import rfc8785

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

VERIFICATION_SCOPE = "artifact_conformance"
HOSTED_VERIFICATION_LABEL = "grading-verified artifact score; generation-attested"
LOCAL_VERIFICATION_LABEL = "local artifact score; self-reported"
REFERENCE_CONTROL_LABEL = "grading-verified reference control; no generation attribution"
BASELINE_CONTROL_LABEL = "grading-verified baseline control; not a leaderboard result"


class Severity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFORMATIONAL = "informational"


class SourceOfTruth(StrEnum):
    OOXML = "ooxml"
    RENDER = "render"
    BOTH = "both"


class Propagation(StrEnum):
    ZERO_SLIDE = "zero_slide"
    ZERO_ITEM = "zero_item"
    ZERO_AFFECTED_SLIDES = "zero_affected_slides"


class GradingMode(StrEnum):
    LOCAL = "local"
    HOSTED = "hosted"


class RunKind(StrEnum):
    SUBMISSION = "submission"
    REFERENCE_CONTROL = "reference_control"
    BASELINE_CONTROL = "baseline_control"


class GoldDuplicateCheck(StrEnum):
    CLEAR = "clear"
    BYTE_MATCH = "byte_match"
    CANONICAL_MATCH = "canonical_match"
    INCOMPLETE = "incomplete"


class DisqualificationState(StrEnum):
    NONE = "none"
    COMPLETED_INELIGIBLE = "completed_ineligible"
    NON_OFFICIAL_LOCAL = "non_official_local"


@dataclass
class QuarantineResult:
    passed: bool
    reason: str = ""
    file_size_bytes: int = 0
    slide_count: int = 0
    has_macros: bool = False
    has_activex: bool = False
    has_ole: bool = False
    has_external_links: bool = False
    has_password: bool = False


@dataclass
class SchemaValidationResult:
    valid: bool
    performed: bool = True
    violations: list[str] = field(default_factory=list)


@dataclass
class SlideExport:
    slide_number: int
    path: Path
    width: int = 1920
    height: int = 1080


@dataclass
class VisualComparisonResult:
    slide_number: int
    ssim: float
    pixel_exact: bool
    diff_path: Path | None = None

    @property
    def passed(self) -> bool:
        return self.ssim >= 0.9999


@dataclass
class ChecklistItemResult:
    id: str
    passed: bool
    severity: Severity
    source_of_truth: SourceOfTruth
    details: str = ""
    assertion_id: str = ""
    weight: int = 0
    outcome_code: str = "failed"
    tier_affected_slides: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "assertion_id": self.assertion_id,
            "passed": self.passed,
            "severity": self.severity.value,
            "weight": self.weight,
            "source_of_truth": self.source_of_truth.value,
            "outcome_code": self.outcome_code,
            "tier_affected_slides": sorted(set(self.tier_affected_slides)),
            "details": self.details,
        }


@dataclass(frozen=True)
class AntiCheatFlag:
    rule_id: str
    disposition: str
    affected_slides: tuple[int, ...]
    tier_affected_slides: tuple[int, ...]
    outcome_code: str = "triggered"
    details: str = ""

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "rule_id": self.rule_id,
            "disposition": self.disposition,
            "affected_slides": sorted(set(self.affected_slides)),
            "tier_affected_slides": sorted(set(self.tier_affected_slides)),
            "outcome_code": self.outcome_code,
        }
        if self.details:
            result["details"] = self.details
        return result


@dataclass(frozen=True)
class StableError:
    code: str
    part: str | None = None
    location: str | None = None
    details: str = ""

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "part": self.part,
            "location": self.location,
        }
        if self.details:
            result["details"] = self.details
        return result


@dataclass(frozen=True)
class ArtifactReportContext:
    """Caller-supplied identities that the grader must never invent."""

    grading_mode: GradingMode
    run_kind: RunKind
    targeted_tier: int
    prompt_variant: str
    generation_seed: str | None
    grader_package_sha256: str
    oci_image_digest: str
    prompt_bundle_sha256: str
    scored_assertion_inventory_sha256: str
    checklist_bundle_sha256: str
    schema_bundle_sha256: str
    schema_root_map_sha256: str
    mce_profile_sha256: str
    asset_manifest_sha256: str
    font_manifest_sha256: str
    canonical_package_hash_profile_sha256: str
    canonical_package_hash_v1: str | None
    gold_duplicate_check: GoldDuplicateCheck
    submission_sha256: str
    mce_resolved_package_sha256: str | None
    gold_submission_sha256: str
    gold_mce_resolved_package_sha256: str
    gold_canonical_package_hash_v1: str
    environment_attestation: dict[str, Any]
    assistance_class: str | None
    generation_profile_sha256: str | None
    attested_metrics: dict[str, Any] | None
    attestation: dict[str, Any] | None
    submission_id: str | None = None
    campaign_id: str | None = None
    campaign_slot: int | None = None
    robustness_group_id: str | None = None
    submitter_id: str | None = None
    model_key: str | None = None
    model_revision_key: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ArtifactReportContext:
        """Load a context without accepting implicit or unknown provenance."""
        expected = {item.name for item in fields(cls)}
        supplied = set(value)
        if missing := sorted(expected - supplied):
            raise ValueError(f"artifact report context is missing field(s): {', '.join(missing)}")
        if unknown := sorted(supplied - expected):
            raise ValueError(f"artifact report context has unknown field(s): {', '.join(unknown)}")

        payload = dict(value)
        try:
            payload["grading_mode"] = GradingMode(payload["grading_mode"])
            payload["run_kind"] = RunKind(payload["run_kind"])
            payload["gold_duplicate_check"] = GoldDuplicateCheck(payload["gold_duplicate_check"])
        except (TypeError, ValueError) as exc:
            raise ValueError("artifact report context contains an invalid enum value") from exc
        context = cls(**cast("Any", payload))
        context.validate()
        return context

    def as_dict(self) -> dict[str, Any]:
        """Return a complete JSON-compatible caller handoff."""
        result = asdict(self)
        result["grading_mode"] = self.grading_mode.value
        result["run_kind"] = self.run_kind.value
        result["gold_duplicate_check"] = self.gold_duplicate_check.value
        return result

    def validate(self) -> None:
        if not isinstance(self.grading_mode, GradingMode):
            raise ValueError("grading_mode must be local or hosted")
        if not isinstance(self.run_kind, RunKind):
            raise ValueError("run_kind is invalid")
        if not isinstance(self.gold_duplicate_check, GoldDuplicateCheck):
            raise ValueError("gold_duplicate_check is invalid")
        if not isinstance(self.targeted_tier, int) or isinstance(self.targeted_tier, bool):
            raise ValueError("targeted_tier must be an integer")
        if self.targeted_tier not in {1, 2, 3}:
            raise ValueError("targeted_tier must be 1, 2, or 3")
        if not isinstance(self.prompt_variant, str) or not self.prompt_variant:
            raise ValueError("prompt_variant must be non-empty")
        if self.generation_seed is not None and not isinstance(self.generation_seed, str):
            raise ValueError("generation_seed must be a string or null")
        if self.generation_seed is not None and len(self.generation_seed.encode("utf-8")) > 256:
            raise ValueError("generation_seed exceeds 256 UTF-8 bytes")
        prefixed_hashes = (
            self.grader_package_sha256,
            self.oci_image_digest,
            self.prompt_bundle_sha256,
            self.scored_assertion_inventory_sha256,
            self.checklist_bundle_sha256,
            self.schema_bundle_sha256,
            self.schema_root_map_sha256,
            self.mce_profile_sha256,
            self.asset_manifest_sha256,
            self.font_manifest_sha256,
            self.canonical_package_hash_profile_sha256,
            self.submission_sha256,
            self.gold_submission_sha256,
            self.gold_mce_resolved_package_sha256,
            self.gold_canonical_package_hash_v1,
        )
        optional_hashes = (
            self.canonical_package_hash_v1,
            self.mce_resolved_package_sha256,
            self.generation_profile_sha256,
        )
        if any(
            not isinstance(value, str) or not _is_prefixed_sha256(value)
            for value in prefixed_hashes
        ):
            raise ValueError("artifact report context contains a non-canonical SHA-256")
        if any(
            value is not None and (not isinstance(value, str) or not _is_prefixed_sha256(value))
            for value in optional_hashes
        ):
            raise ValueError("artifact report context contains a non-canonical optional SHA-256")
        if not isinstance(self.environment_attestation, dict):
            raise ValueError("environment_attestation must be an object")
        if self.assistance_class is not None and not isinstance(self.assistance_class, str):
            raise ValueError("assistance_class must be a string or null")
        if self.attested_metrics is not None and not isinstance(self.attested_metrics, dict):
            raise ValueError("attested_metrics must be an object or null")
        if self.attestation is not None and not isinstance(self.attestation, dict):
            raise ValueError("attestation must be an object or null")
        identifier_fields = (
            ("submission_id", self.submission_id),
            ("campaign_id", self.campaign_id),
            ("robustness_group_id", self.robustness_group_id),
            ("submitter_id", self.submitter_id),
            ("model_key", self.model_key),
            ("model_revision_key", self.model_revision_key),
        )
        for name, value in identifier_fields:
            if value is not None and (not isinstance(value, str) or not _is_canonical_uuid(value)):
                raise ValueError(f"{name} must be a canonical UUID or null")
        if self.campaign_slot is not None and (
            not isinstance(self.campaign_slot, int)
            or isinstance(self.campaign_slot, bool)
            or self.campaign_slot not in {1, 2, 3}
        ):
            raise ValueError("campaign_slot must be 1, 2, 3, or null")
        if self.grading_mode is GradingMode.LOCAL:
            local_identifiers = (
                self.submission_id,
                self.campaign_id,
                self.campaign_slot,
                self.robustness_group_id,
                self.submitter_id,
                self.model_key,
                self.model_revision_key,
            )
            if any(value is not None for value in local_identifiers):
                raise ValueError("local report context cannot carry hosted identifiers")
            if self.run_kind is not RunKind.SUBMISSION:
                raise ValueError("local report context supports submission runs only")
            if self.assistance_class not in {"unassisted", "human-assisted"}:
                raise ValueError("local submission requires an assistance_class")
            if self.attested_metrics is None or self.attestation is None:
                raise ValueError("local submission requires attested generation metadata")
        if self.grading_mode is GradingMode.HOSTED and self.run_kind is RunKind.SUBMISSION:
            required_hosted = (
                self.submission_id,
                self.campaign_id,
                self.campaign_slot,
                self.submitter_id,
                self.model_key,
                self.model_revision_key,
                self.assistance_class,
                self.generation_profile_sha256,
                self.attested_metrics,
                self.attestation,
            )
            if any(value is None for value in required_hosted):
                raise ValueError("hosted submission report context is incomplete")
        if self.run_kind is not RunKind.SUBMISSION and self.grading_mode is not GradingMode.HOSTED:
            raise ValueError("control report context must use hosted grading_mode")
        if self.run_kind is not RunKind.SUBMISSION and any(
            value is not None
            for value in (
                self.submission_id,
                self.campaign_id,
                self.campaign_slot,
                self.robustness_group_id,
                self.submitter_id,
                self.model_key,
                self.model_revision_key,
                self.assistance_class,
                self.generation_profile_sha256,
                self.attested_metrics,
                self.attestation,
            )
        ):
            raise ValueError("control report context contains submission-only metadata")


def _is_prefixed_sha256(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _is_canonical_uuid(value: str) -> bool:
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


@dataclass
class SlideResult:
    slide_number: int
    tier: int
    visual_ssim: float | None
    visual_pixel_exact: bool | None
    items: list[ChecklistItemResult] = field(default_factory=list)

    @property
    def passed_items(self) -> int:
        return sum(1 for i in self.items if i.passed)

    @property
    def total_items(self) -> int:
        return len(self.items)


@dataclass
class GradeReport:
    benchmark_version: str
    grader_version: str
    scoring_cohort_id: str
    scoring_manifest_sha256: str
    grader_source_tree_sha256: str
    environment_attestation_sha256: str
    grader_package_sha256: str
    oci_image_digest: str
    prompt_bundle_sha256: str
    scored_assertion_inventory_sha256: str
    checklist_bundle_sha256: str
    schema_bundle_sha256: str
    schema_root_map_sha256: str
    mce_profile_sha256: str
    asset_manifest_sha256: str
    font_manifest_sha256: str
    grading_mode: GradingMode
    run_kind: RunKind
    canonical_package_hash_profile_sha256: str
    canonical_package_hash_v1: str | None
    gold_duplicate_check: GoldDuplicateCheck
    generation_seed: str | None
    submission_id: str | None
    campaign_id: str | None
    campaign_slot: int | None
    robustness_group_id: str | None
    submitter_id: str | None
    model_key: str | None
    model_revision_key: str | None
    targeted_tier: int
    prompt_variant: str
    assistance_class: str | None
    generation_profile_sha256: str | None
    submission_sha256: str
    mce_resolved_package_sha256: str | None
    gold_submission_sha256: str
    gold_mce_resolved_package_sha256: str
    gold_canonical_package_hash_v1: str
    schema_valid: bool
    schema_validation_performed: bool
    visual_verification_performed: bool
    verification_complete: bool
    scoring_completed: bool
    disqualification_state: DisqualificationState
    ineligibility_reasons: list[str]
    repair_triggered: bool
    grading_duration_seconds: float
    fidelity_score: float | None
    campaign_contribution: float
    passed_items: int
    total_items: int
    deck_passed: bool
    eligible: bool
    tier_scores: dict[str, dict[str, int | float] | None]
    slides: list[SlideResult] = field(default_factory=list)
    deck_items: list[ChecklistItemResult] = field(default_factory=list)
    anti_cheat_flags: list[AntiCheatFlag] = field(default_factory=list)
    schema_violations: list[StableError] = field(default_factory=list)
    verification_errors: list[StableError] = field(default_factory=list)
    environment_attestation: dict[str, Any] = field(default_factory=dict)
    verified_metrics: dict[str, bool | int | float | str] = field(default_factory=dict)
    attested_metrics: dict[str, Any] | None = None
    attestation: dict[str, Any] | None = None

    @property
    def verification_label(self) -> str:
        if self.run_kind is RunKind.REFERENCE_CONTROL:
            return REFERENCE_CONTROL_LABEL
        if self.run_kind is RunKind.BASELINE_CONTROL:
            return BASELINE_CONTROL_LABEL
        if self.grading_mode is GradingMode.LOCAL:
            return LOCAL_VERIFICATION_LABEL
        return HOSTED_VERIFICATION_LABEL

    def to_json(self) -> str:
        return json.dumps(self._to_dict(), indent=2)

    def semantic_projection(self) -> dict[str, Any]:
        """Return the exact score-semantic projection used for compatibility."""

        def item_outcome(item: ChecklistItemResult) -> dict[str, Any]:
            return {
                "id": item.id,
                "assertion_id": item.assertion_id,
                "passed": item.passed,
                "severity": item.severity.value,
                "weight": item.weight,
                "outcome_code": item.outcome_code,
                "tier_affected_slides": sorted(set(item.tier_affected_slides)),
            }

        def stable_error(error: StableError) -> dict[str, Any]:
            return {
                "code": error.code,
                "part": error.part,
                "location": error.location,
            }

        return {
            "projection_schema_version": "1.0",
            "run_kind": self.run_kind.value,
            "grading_mode": self.grading_mode.value,
            "targeted_tier": self.targeted_tier,
            "prompt_variant": self.prompt_variant,
            "schema_validation_performed": self.schema_validation_performed,
            "schema_valid": self.schema_valid,
            "visual_verification_performed": self.visual_verification_performed,
            "verification_complete": self.verification_complete,
            "scoring_completed": self.scoring_completed,
            "eligible": self.eligible,
            "disqualification_state": self.disqualification_state.value,
            "ineligibility_reasons": sorted(set(self.ineligibility_reasons)),
            "repair_triggered": self.repair_triggered,
            "gold_duplicate_check": self.gold_duplicate_check.value,
            "fidelity_score": self.fidelity_score,
            "campaign_contribution": self.campaign_contribution,
            "passed_items": self.passed_items,
            "total_items": self.total_items,
            "tier_scores": self.tier_scores,
            "slides": [
                {
                    "slide": slide.slide_number,
                    "tier": slide.tier,
                    "passed_items": slide.passed_items,
                    "total_items": slide.total_items,
                    "items": [
                        item_outcome(item)
                        for item in sorted(slide.items, key=lambda value: value.id)
                    ],
                }
                for slide in sorted(self.slides, key=lambda value: value.slide_number)
            ],
            "deck_items": [
                item_outcome(item) for item in sorted(self.deck_items, key=lambda value: value.id)
            ],
            "anti_cheat_flags": [
                {
                    "rule_id": flag.rule_id,
                    "disposition": flag.disposition,
                    "affected_slides": sorted(set(flag.affected_slides)),
                    "tier_affected_slides": sorted(set(flag.tier_affected_slides)),
                }
                for flag in sorted(
                    self.anti_cheat_flags,
                    key=lambda value: (
                        value.rule_id,
                        value.disposition,
                        value.affected_slides,
                    ),
                )
            ],
            "schema_errors": [
                stable_error(error)
                for error in sorted(
                    self.schema_violations,
                    key=lambda value: (value.code, value.part or "", value.location or ""),
                )
            ],
            "verification_errors": [
                stable_error(error)
                for error in sorted(
                    self.verification_errors,
                    key=lambda value: (value.code, value.part or "", value.location or ""),
                )
            ],
        }

    @property
    def score_semantic_report_sha256(self) -> str:
        canonical = rfc8785.dumps(self.semantic_projection())
        return f"sha256:{hashlib.sha256(canonical).hexdigest()}"

    def _to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "benchmark_version": self.benchmark_version,
            "grading_mode": self.grading_mode.value,
            "run_kind": self.run_kind.value,
            "verification_scope": VERIFICATION_SCOPE,
            "verification_label": self.verification_label,
            "grader_version": self.grader_version,
            "scoring_cohort_id": self.scoring_cohort_id,
            "scoring_manifest_sha256": self.scoring_manifest_sha256,
            "grader_source_tree_sha256": self.grader_source_tree_sha256,
            "environment_attestation_sha256": self.environment_attestation_sha256,
            "grader_package_sha256": self.grader_package_sha256,
            "oci_image_digest": self.oci_image_digest,
            "prompt_bundle_sha256": self.prompt_bundle_sha256,
            "scored_assertion_inventory_sha256": self.scored_assertion_inventory_sha256,
            "checklist_bundle_sha256": self.checklist_bundle_sha256,
            "schema_bundle_sha256": self.schema_bundle_sha256,
            "schema_root_map_sha256": self.schema_root_map_sha256,
            "mce_profile_sha256": self.mce_profile_sha256,
            "asset_manifest_sha256": self.asset_manifest_sha256,
            "font_manifest_sha256": self.font_manifest_sha256,
            "canonical_package_hash_profile_sha256": (self.canonical_package_hash_profile_sha256),
            "canonical_package_hash_v1": self.canonical_package_hash_v1,
            "gold_duplicate_check": self.gold_duplicate_check.value,
            "generation_seed": self.generation_seed,
            "submission_id": self.submission_id,
            "campaign_id": self.campaign_id,
            "campaign_slot": self.campaign_slot,
            "robustness_group_id": self.robustness_group_id,
            "submitter_id": self.submitter_id,
            "model_key": self.model_key,
            "model_revision_key": self.model_revision_key,
            "targeted_tier": self.targeted_tier,
            "prompt_variant": self.prompt_variant,
            "assistance_class": self.assistance_class,
            "generation_profile_sha256": self.generation_profile_sha256,
            "submission_sha256": self.submission_sha256,
            "mce_resolved_package_sha256": self.mce_resolved_package_sha256,
            "gold_submission_sha256": self.gold_submission_sha256,
            "gold_mce_resolved_package_sha256": self.gold_mce_resolved_package_sha256,
            "gold_canonical_package_hash_v1": self.gold_canonical_package_hash_v1,
            "schema_valid": self.schema_valid,
            "schema_validation_performed": self.schema_validation_performed,
            "visual_verification_performed": self.visual_verification_performed,
            "verification_complete": self.verification_complete,
            "scoring_completed": self.scoring_completed,
            "disqualification_state": self.disqualification_state.value,
            "ineligibility_reasons": sorted(set(self.ineligibility_reasons)),
            "repair_triggered": self.repair_triggered,
            "grading_duration_seconds": self.grading_duration_seconds,
            "fidelity_score": self.fidelity_score,
            "campaign_contribution": self.campaign_contribution,
            "passed_items": self.passed_items,
            "total_items": self.total_items,
            "deck_passed": self.deck_passed,
            "eligible": self.eligible,
            "score_semantic_report_sha256": self.score_semantic_report_sha256,
            "environment_attestation": self.environment_attestation,
            "tier_scores": self.tier_scores,
            "verified_metrics": self.verified_metrics,
            "attested_metrics": self.attested_metrics,
            "attestation": self.attestation,
            "anti_cheat_flags": [
                flag.as_dict()
                for flag in sorted(
                    self.anti_cheat_flags,
                    key=lambda value: (
                        value.rule_id,
                        value.disposition,
                        value.affected_slides,
                    ),
                )
            ],
            "schema_violations": [
                error.as_dict()
                for error in sorted(
                    self.schema_violations,
                    key=lambda value: (value.code, value.part or "", value.location or ""),
                )
            ],
            "verification_errors": [
                error.as_dict()
                for error in sorted(
                    self.verification_errors,
                    key=lambda value: (value.code, value.part or "", value.location or ""),
                )
            ],
            "slides": [
                {
                    "slide": s.slide_number,
                    "tier": s.tier,
                    "visual_ssim": s.visual_ssim,
                    "visual_pixel_exact": s.visual_pixel_exact,
                    "passed_items": s.passed_items,
                    "total_items": s.total_items,
                    "items": [i.as_dict() for i in sorted(s.items, key=lambda item: item.id)],
                }
                for s in sorted(self.slides, key=lambda slide: slide.slide_number)
            ],
            "deck_items": [
                item.as_dict() for item in sorted(self.deck_items, key=lambda item: item.id)
            ],
        }
        return payload

    def to_html(self) -> str:
        """Render a standalone, escaped HTML report."""
        status = "PASS" if self.deck_passed else "FAIL"
        if not self.verification_complete:
            status = "INCOMPLETE"

        error_items = "".join(
            f"<li>{escape(error.code)}: {escape(error.details)}</li>"
            for error in self.verification_errors
        )
        errors = f"<h2>Verification errors</h2><ul>{error_items}</ul>" if error_items else ""
        rows: list[str] = []
        for slide in self.slides:
            visual_ssim = f"{slide.visual_ssim:.4f}" if slide.visual_ssim is not None else "n/a"
            rows.append(
                "<tr>"
                f"<td>{slide.slide_number}</td>"
                f"<td>{slide.tier}</td>"
                f"<td>{visual_ssim}</td>"
                f"<td>{slide.passed_items}/{slide.total_items}</td>"
                "</tr>"
            )
        slide_rows = "".join(rows)
        fidelity = f"{self.fidelity_score:.4f}" if self.fidelity_score is not None else "n/a"
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AcidSlide report — {escape(self.submission_id or "local/control")}</title>
  <style>
    body {{ font: 16px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 72rem;
      padding: 0 1rem; }}
    dl {{ display: grid; grid-template-columns: max-content 1fr; gap: .35rem 1rem; }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: .5rem; text-align: left; }}
  </style>
</head>
<body>
  <h1>AcidSlide grade report — {status}</h1>
  <p><strong>{self.verification_label}</strong></p>
  <dl>
    <dt>Submission</dt><dd>{escape(self.submission_id or "local/control")}</dd>
    <dt>Fidelity</dt><dd>{fidelity}</dd>
    <dt>Items</dt><dd>{self.passed_items}/{self.total_items}</dd>
    <dt>Verification complete</dt><dd>{str(self.verification_complete).lower()}</dd>
    <dt>Leaderboard eligible</dt><dd>{str(self.eligible).lower()}</dd>
    <dt>Environment</dt><dd><code>{escape(self.environment_attestation_sha256)}</code></dd>
  </dl>
  {errors}
  <h2>Slides</h2>
  <table>
    <thead><tr><th>Slide</th><th>Tier</th><th>SSIM</th><th>Items</th></tr></thead>
    <tbody>{slide_rows}</tbody>
  </table>
</body>
</html>
"""

    def summary(self) -> str:
        if not self.verification_complete:
            status = "[yellow]INCOMPLETE[/yellow]"
        else:
            status = "[green]PASS[/green]" if self.deck_passed else "[red]FAIL[/red]"
        lines = [
            f"AcidSlide Grade Report — {status}",
            f"  Verification: {self.verification_label}",
            f"  Fidelity: {self.fidelity_score:.4f}"
            if self.fidelity_score is not None
            else "  Fidelity: n/a",
            f"  Items: {self.passed_items}/{self.total_items}",
            f"  Schema valid: {self.schema_valid}",
            f"  Repair triggered: {self.repair_triggered}",
            f"  Verification complete: {self.verification_complete}",
            f"  Leaderboard eligible: {self.eligible}",
        ]
        if self.anti_cheat_flags:
            lines.append(f"  Anti-cheat flags: {self.anti_cheat_flags}")
        if self.schema_violations:
            lines.append(f"  Schema violations: {len(self.schema_violations)}")
        if self.verification_errors:
            lines.append("  Verification errors:")
            lines.extend(
                f"    - {error.code}: {error.details}" for error in self.verification_errors
            )
        return "\n".join(lines)
