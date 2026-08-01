"""Tests for CLI serialization, exit status, and export display."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from click.testing import CliRunner
from test_models import _environment_attestation
from test_models import _report as _diagnostic_report
from test_pipeline import _benchmark, _cohort, _context, _patch_successful_stages, _submission

from gloss.cli import main
from gloss.models import (
    DisqualificationState,
    GradeReport,
    QuarantineResult,
    SchemaValidationResult,
    SlideExport,
)

if TYPE_CHECKING:
    import pytest


def _report(*, complete: bool) -> GradeReport:
    report = _diagnostic_report()
    if not complete:
        return report
    return replace(
        report,
        schema_valid=True,
        visual_verification_performed=True,
        verification_complete=True,
        scoring_completed=True,
        disqualification_state=DisqualificationState.NONE,
        ineligibility_reasons=[],
        fidelity_score=1.0,
        campaign_contribution=1.0,
        passed_items=1,
        total_items=1,
        deck_passed=True,
        eligible=True,
        tier_scores={
            "level_1": {"fidelity_score": 1.0, "passed": 1, "total": 1},
            "level_2": None,
            "level_3": None,
        },
        schema_violations=[],
        verification_errors=[],
        verified_metrics=report.verified_metrics
        | {
            "schema_valid": True,
            "visual_verification_performed": True,
            "verification_complete": True,
        },
    )


def _context_file(path: Path, submission: Path) -> tuple[Path, dict[str, Any]]:
    environment_attestation = _environment_attestation()
    context_path = path / "artifact-context.json"
    context_path.write_text(
        json.dumps(_context(submission, environment_attestation).as_dict()),
        encoding="utf-8",
    )
    return context_path, environment_attestation


def test_grade_writes_real_html(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    submission = _submission(tmp_path / "submission.pptx")
    context_path, _environment = _context_file(tmp_path, submission)
    output = tmp_path / "report.html"
    monkeypatch.setattr("gloss.pipeline.run_pipeline", lambda **_kwargs: _report(complete=True))

    result = CliRunner().invoke(
        main,
        [
            "grade",
            str(submission),
            "--tier",
            "1",
            "--artifact-context",
            str(context_path),
            "--format",
            "html",
            "-o",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_grade_incomplete_report_exits_two(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    submission = _submission(tmp_path / "submission.pptx")
    context_path, _environment = _context_file(tmp_path, submission)
    monkeypatch.setattr(
        "gloss.pipeline.run_pipeline",
        lambda **_kwargs: _report(complete=False),
    )

    result = CliRunner().invoke(
        main,
        [
            "grade",
            str(submission),
            "--tier",
            "1",
            "--artifact-context",
            str(context_path),
        ],
    )

    assert result.exit_code == 2
    assert "INCOMPLETE" in result.output
    assert "schema_validation_failed" in result.output


def test_grade_requires_artifact_context(tmp_path: Path) -> None:
    submission = _submission(tmp_path / "submission.pptx")

    result = CliRunner().invoke(main, ["grade", str(submission), "--tier", "1"])

    assert result.exit_code == 2
    assert "Missing option '--artifact-context'" in result.output


def test_grade_rejects_missing_and_unknown_context_fields(tmp_path: Path) -> None:
    submission = _submission(tmp_path / "submission.pptx")
    context_path = tmp_path / "artifact-context.json"
    context_path.write_text("{}", encoding="utf-8")

    missing = CliRunner().invoke(
        main,
        [
            "grade",
            str(submission),
            "--tier",
            "1",
            "--artifact-context",
            str(context_path),
        ],
    )
    assert missing.exit_code == 2
    assert "missing field(s)" in missing.output

    environment_attestation = _environment_attestation()
    payload = _context(submission, environment_attestation).as_dict() | {"invented": True}
    context_path.write_text(json.dumps(payload), encoding="utf-8")
    unknown = CliRunner().invoke(
        main,
        [
            "grade",
            str(submission),
            "--tier",
            "1",
            "--artifact-context",
            str(context_path),
        ],
    )
    assert unknown.exit_code == 2
    assert "unknown field(s): invented" in unknown.output


def test_grade_real_local_pipeline_accepts_verified_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    benchmark = _benchmark(tmp_path / "benchmark")
    submission = _submission(tmp_path / "submission.pptx")
    context_path, environment_attestation = _context_file(tmp_path, submission)
    _patch_successful_stages(monkeypatch)
    monkeypatch.setattr(
        "gloss.pipeline.load_signed_release_provenance",
        lambda _benchmark: _cohort(environment_attestation),
    )

    result = CliRunner().invoke(
        main,
        [
            "grade",
            str(submission),
            "--tier",
            "1",
            "--benchmark-dir",
            str(benchmark),
            "--artifact-context",
            str(context_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["grading_mode"] == "local"
    assert payload["verification_complete"] is True
    assert payload["eligible"] is False
    assert payload["campaign_contribution"] == 0.0


def test_grade_rejects_environment_attestation_jcs_tamper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    benchmark = _benchmark(tmp_path / "benchmark")
    submission = _submission(tmp_path / "submission.pptx")
    environment_attestation = _environment_attestation()
    context = _context(submission, environment_attestation)
    context_payload = context.as_dict()
    context_payload["environment_attestation"] = environment_attestation | {"tampered": True}
    context_path = tmp_path / "artifact-context.json"
    context_path.write_text(json.dumps(context_payload), encoding="utf-8")
    monkeypatch.setattr(
        "gloss.pipeline.load_signed_release_provenance",
        lambda _benchmark: _cohort(environment_attestation),
    )

    result = CliRunner().invoke(
        main,
        [
            "grade",
            str(submission),
            "--tier",
            "1",
            "--benchmark-dir",
            str(benchmark),
            "--artifact-context",
            str(context_path),
        ],
    )

    assert result.exit_code == 2
    assert "environment attestation payload" in result.output
    assert "match the scoring cohort" in result.output


def test_export_prints_slide_path_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    submission = tmp_path / "submission.pptx"
    submission.write_bytes(b"pptx")
    monkeypatch.setattr(
        "gloss.export.export_slides",
        lambda _submission, output, **_kwargs: [SlideExport(1, output / "slide-01.png")],
    )

    result = CliRunner().invoke(main, ["export", str(submission), "--outdir", str(tmp_path)])

    assert result.exit_code == 0
    assert "slide-01.png" in result.output


def test_validate_exits_two_when_schema_cannot_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    submission = tmp_path / "submission.pptx"
    submission.write_bytes(b"pptx")
    monkeypatch.setattr(
        "gloss.quarantine.quarantine_check",
        lambda _path: QuarantineResult(passed=True),
    )
    monkeypatch.setattr(
        "gloss.schema_validate.validate_schema",
        lambda _path: SchemaValidationResult(
            valid=False,
            performed=False,
            violations=["schemas unavailable"],
        ),
    )

    result = CliRunner().invoke(main, ["validate", str(submission)])

    assert result.exit_code == 2
    assert "not performed" in result.output
    assert "schemas unavailable" in result.output


def test_check_reports_exact_gold_deck() -> None:
    root = Path(__file__).resolve().parents[2]
    gold = root / "benchmark" / "deck" / "gold" / "gloss-v1-gold.pptx"

    result = CliRunner().invoke(main, ["check", str(gold)])

    assert result.exit_code == 0
    assert "Exact match" in result.output
    assert "No native objects changed" in result.output
