"""Core data models for AcidSlide grader."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


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


@dataclass
class SlideResult:
    slide_number: int
    tier: int
    visual_ssim: float
    visual_pixel_exact: bool
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
    environment_hash: str
    submission: str
    schema_valid: bool
    repair_triggered: bool
    fidelity_score: float
    passed_items: int
    total_items: int
    deck_passed: bool
    eligible: bool
    tier_scores: dict[str, dict]
    slides: list[SlideResult] = field(default_factory=list)
    deck_items: list[ChecklistItemResult] = field(default_factory=list)
    anti_cheat_flags: list[str] = field(default_factory=list)
    verified_metrics: dict = field(default_factory=dict)
    attested_metrics: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self._to_dict(), indent=2)

    def _to_dict(self) -> dict:
        return {
            "benchmark_version": self.benchmark_version,
            "grader_version": self.grader_version,
            "environment_hash": self.environment_hash,
            "submission": self.submission,
            "schema_valid": self.schema_valid,
            "repair_triggered": self.repair_triggered,
            "fidelity_score": self.fidelity_score,
            "passed_items": self.passed_items,
            "total_items": self.total_items,
            "deck_passed": self.deck_passed,
            "eligible": self.eligible,
            "tier_scores": self.tier_scores,
            "verified_metrics": self.verified_metrics,
            "attested_metrics": self.attested_metrics,
            "anti_cheat_flags": self.anti_cheat_flags,
            "slides": [
                {
                    "slide": s.slide_number,
                    "tier": s.tier,
                    "visual_ssim": s.visual_ssim,
                    "visual_pixel_exact": s.visual_pixel_exact,
                    "passed_items": s.passed_items,
                    "total_items": s.total_items,
                    "items": [
                        {
                            "id": i.id,
                            "passed": i.passed,
                            "severity": i.severity.value,
                            "source_of_truth": i.source_of_truth.value,
                            "details": i.details,
                        }
                        for i in s.items
                    ],
                }
                for s in self.slides
            ],
            "deck_items": [
                {
                    "id": i.id,
                    "passed": i.passed,
                    "severity": i.severity.value,
                    "source_of_truth": i.source_of_truth.value,
                    "details": i.details,
                }
                for i in self.deck_items
            ],
        }

    def summary(self) -> str:
        status = "[green]PASS[/green]" if self.deck_passed else "[red]FAIL[/red]"
        lines = [
            f"AcidSlide Grade Report — {status}",
            f"  Fidelity: {self.fidelity_score:.4f}",
            f"  Items: {self.passed_items}/{self.total_items}",
            f"  Schema valid: {self.schema_valid}",
            f"  Repair triggered: {self.repair_triggered}",
        ]
        if self.anti_cheat_flags:
            lines.append(f"  Anti-cheat flags: {self.anti_cheat_flags}")
        return "\n".join(lines)
