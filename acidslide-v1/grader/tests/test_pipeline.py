"""Tests for fail-closed grading orchestration."""

from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import jsonschema
import pytest
import rfc8785
from test_models import _environment_attestation

from acidslide import pipeline
from acidslide.checklist import ChecklistItem, Verification
from acidslide.inspect_ooxml import DeckGraph, SceneObject, SlideGraph
from acidslide.models import (
    ArtifactReportContext,
    DisqualificationState,
    GoldDuplicateCheck,
    GradeReport,
    GradingMode,
    QuarantineResult,
    RunKind,
    SchemaValidationResult,
    SlideExport,
    StableError,
    VisualComparisonResult,
)
from acidslide.package_hash import canonical_package_identity, sha256_file
from acidslide.provenance import ScoringCohortProvenance, derive_scoring_cohort_id

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_FIXTURE = ROOT / "benchmark" / "fixtures" / "package-hash" / "gold-copy-rejection-v1.json"


def _sha(character: str) -> str:
    return f"sha256:{character * 64}"


def _cohort(environment_attestation: dict[str, Any]) -> ScoringCohortProvenance:
    manifest = _sha("1")
    grader = _sha("2")
    environment = f"sha256:{hashlib.sha256(rfc8785.dumps(environment_attestation)).hexdigest()}"
    return ScoringCohortProvenance(
        scoring_cohort_id=derive_scoring_cohort_id(manifest, grader, environment),
        scoring_manifest_sha256=manifest,
        grader_source_tree_sha256=grader,
        environment_attestation_sha256=environment,
    )


def _submission(path: Path) -> Path:
    fixture = json.loads(PACKAGE_FIXTURE.read_text(encoding="utf-8"))
    parts = {name: base64.b64decode(data) for name, data in fixture["gold_parts"].items()}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name, content in sorted(parts.items()):
            package.writestr(name, content)
    return path


def _context(
    package: Path,
    environment_attestation: dict[str, Any],
    *,
    grading_mode: GradingMode = GradingMode.LOCAL,
) -> ArtifactReportContext:
    identity = canonical_package_identity(package)
    package_sha256 = f"sha256:{sha256_file(package)}"
    hosted = grading_mode is GradingMode.HOSTED
    return ArtifactReportContext(
        grading_mode=grading_mode,
        run_kind=RunKind.SUBMISSION,
        targeted_tier=1,
        prompt_variant="canonical",
        generation_seed=None,
        grader_package_sha256=_sha("4"),
        oci_image_digest=_sha("1"),
        prompt_bundle_sha256=_sha("5"),
        scored_assertion_inventory_sha256=_sha("6"),
        checklist_bundle_sha256=_sha("7"),
        schema_bundle_sha256=_sha("8"),
        schema_root_map_sha256=f"sha256:{identity.schema_root_map_sha256}",
        mce_profile_sha256=f"sha256:{identity.mce_profile_sha256}",
        asset_manifest_sha256=_sha("8"),
        font_manifest_sha256=_sha("7"),
        canonical_package_hash_profile_sha256=(f"sha256:{identity.package_hash_profile_sha256}"),
        canonical_package_hash_v1=f"sha256:{identity.canonical_package_sha256}",
        gold_duplicate_check=GoldDuplicateCheck.CLEAR,
        submission_sha256=package_sha256,
        mce_resolved_package_sha256=package_sha256,
        gold_submission_sha256=_sha("d"),
        gold_mce_resolved_package_sha256=_sha("e"),
        gold_canonical_package_hash_v1=_sha("f"),
        environment_attestation=environment_attestation,
        assistance_class="unassisted",
        generation_profile_sha256=_sha("4"),
        attested_metrics={"generation_strategy": "direct"},
        attestation={
            "method": "artifact-upload",
            "human_intervention": False,
            "post_processing": False,
            "external_resources_used": False,
        },
        submission_id="00000000-0000-4000-8000-000000000001" if hosted else None,
        campaign_id="00000000-0000-4000-8000-000000000002" if hosted else None,
        campaign_slot=1 if hosted else None,
        robustness_group_id=None,
        submitter_id="00000000-0000-4000-8000-000000000003" if hosted else None,
        model_key="00000000-0000-4000-8000-000000000004" if hosted else None,
        model_revision_key="00000000-0000-4000-8000-000000000005" if hosted else None,
    )


def _benchmark(path: Path) -> Path:
    (path / "checklist" / "slides").mkdir(parents=True)
    (path / "deck" / "exports").mkdir(parents=True)
    tier_dir = path / "tiers" / "level-1"
    tier_dir.mkdir(parents=True)
    (tier_dir / "slides.json").write_text(json.dumps({"slides": [1, 2, 3, 4, 5]}))
    for slide_number in range(1, 6):
        (path / "deck" / "exports" / f"slide-{slide_number:02d}.png").write_bytes(b"gold")
    return path


def _item() -> ChecklistItem:
    return ChecklistItem(
        schema_version="1.0",
        id="slide-01.shape",
        assertion_id="slide-01.assert-shape",
        scope="slide",
        slide=1,
        tier=1,
        title="Shape",
        description="Shape required",
        kind="structure",
        severity="critical",
        source_of_truth="ooxml",
        verification=Verification(
            method="object_compare",
            selector="shape",
            expectation={"min_count": 1},
        ),
    )


def _patch_successful_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "environment_details", lambda: {"libreoffice": "test"})
    monkeypatch.setattr(
        pipeline,
        "quarantine_check",
        lambda _path: QuarantineResult(passed=True, slide_count=5),
    )
    monkeypatch.setattr(
        pipeline,
        "validate_schema",
        lambda _path: SchemaValidationResult(valid=True, performed=True),
    )

    def fake_export(
        _submission: Path, output_dir: Path, *, expected_page_count: int | None = None
    ) -> list[SlideExport]:
        assert expected_page_count == 5
        return [
            SlideExport(slide_number=number, path=output_dir / f"slide-{number:02d}.png")
            for number in range(1, 6)
        ]

    monkeypatch.setattr(pipeline, "export_slides", fake_export)
    monkeypatch.setattr(
        pipeline,
        "compare_slides",
        lambda _submission, _gold, _diff: [
            VisualComparisonResult(number, 1.0, True) for number in range(1, 6)
        ],
    )
    deck = DeckGraph(slides=[SlideGraph(slide_number=1, objects=[SceneObject(obj_type="shape")])])
    monkeypatch.setattr(pipeline, "extract_deck_graph", lambda _path: deck)
    monkeypatch.setattr(pipeline, "load_checklist", lambda _path, _tier: [_item()])


def _local_inputs(
    tmp_path: Path,
) -> tuple[Path, Path, ArtifactReportContext, ScoringCohortProvenance]:
    benchmark = _benchmark(tmp_path / "benchmark")
    submission = _submission(tmp_path / "submission.pptx")
    environment_attestation = _environment_attestation()
    return (
        benchmark,
        submission,
        _context(submission, environment_attestation),
        _cohort(environment_attestation),
    )


def _run_local(
    submission: Path,
    benchmark: Path,
    context: ArtifactReportContext,
    cohort: ScoringCohortProvenance,
) -> GradeReport:
    return pipeline.run_pipeline(
        submission,
        tier=1,
        benchmark_dir=benchmark,
        cohort_provenance=cohort,
        artifact_context=context,
    )


def _assert_report_schema(payload: dict[str, Any]) -> None:
    schema_path = ROOT / "schemas" / "report.schema.json"
    schema: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))
    environment_schema_path = ROOT / "schemas" / "environment-attestation.schema.json"
    schema["properties"]["environment_attestation"] = json.loads(
        environment_schema_path.read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_complete_local_pipeline_is_verified_but_never_official(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    benchmark, submission, context, cohort = _local_inputs(tmp_path)
    _patch_successful_stages(monkeypatch)

    report = _run_local(submission, benchmark, context, cohort)

    assert report.verification_complete is True
    assert report.scoring_completed is True
    assert report.visual_verification_performed is True
    assert report.schema_validation_performed is True
    assert report.eligible is False
    assert report.deck_passed is True
    assert report.campaign_contribution == 0.0
    assert report.disqualification_state is DisqualificationState.NON_OFFICIAL_LOCAL
    assert report.ineligibility_reasons == ["local_mode"]


def test_export_failure_never_yields_a_complete_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    benchmark, submission, context, cohort = _local_inputs(tmp_path)
    _patch_successful_stages(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "export_slides",
        lambda _submission, _output, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("renderer unavailable")
        ),
    )

    report = _run_local(submission, benchmark, context, cohort)

    assert report.verification_complete is False
    assert report.visual_verification_performed is False
    assert report.eligible is False
    assert report.deck_passed is False
    assert any(
        error.code == "slide_export_failed" and "renderer unavailable" in error.details
        for error in report.verification_errors
    )


def test_schema_skip_never_yields_a_reported_score(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    benchmark, submission, context, cohort = _local_inputs(tmp_path)
    _patch_successful_stages(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "validate_schema",
        lambda _path: SchemaValidationResult(
            valid=False,
            performed=False,
            violations=["schemas missing"],
        ),
    )

    report = _run_local(submission, benchmark, context, cohort)

    assert report.schema_valid is False
    assert report.schema_validation_performed is False
    assert report.scoring_completed is False
    assert report.fidelity_score is None
    assert any(
        error.code == "schema_validation_not_performed" for error in report.verification_errors
    )
    assert report.schema_violations[0].details == "schemas missing"


def test_local_schema_invalid_never_yields_a_reported_score(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    benchmark, submission, context, cohort = _local_inputs(tmp_path)
    _patch_successful_stages(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "validate_schema",
        lambda _path: SchemaValidationResult(
            valid=False,
            performed=True,
            violations=["ppt/slides/slide1.xml: invalid element"],
        ),
    )

    report = _run_local(submission, benchmark, context, cohort)

    assert report.schema_valid is False
    assert report.schema_validation_performed is True
    assert report.verification_complete is False
    assert report.scoring_completed is False
    assert report.fidelity_score is None
    assert report.deck_passed is False
    assert report.schema_violations[0].part == "ppt/slides/slide1.xml"
    assert report.schema_violations[0].details == "invalid element"


def test_hosted_schema_invalid_emits_schema_valid_diagnostic_without_stages_1_to_6(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    benchmark = _benchmark(tmp_path / "benchmark")
    submission = _submission(tmp_path / "resolved.pptx")
    environment_attestation = _environment_attestation()
    context = _context(submission, environment_attestation, grading_mode=GradingMode.HOSTED)
    cohort = _cohort(environment_attestation)

    def unexpected_stage(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Stages 1-6 must not run for a schema-invalid package")

    for name in (
        "environment_details",
        "export_slides",
        "compare_slides",
        "extract_deck_graph",
        "load_checklist",
        "evaluate_checklist",
    ):
        monkeypatch.setattr(pipeline, name, unexpected_stage)

    report = pipeline.run_resolved_pipeline(
        submission,
        tier=1,
        schema_result=SchemaValidationResult(
            performed=True,
            valid=False,
            violations=["ppt/slides/slide1.xml: invalid element"],
        ),
        artifact_context=context,
        benchmark_dir=benchmark,
        cohort_provenance=cohort,
    )

    assert report.grading_mode is GradingMode.HOSTED
    assert report.schema_validation_performed is True
    assert report.schema_valid is False
    assert report.visual_verification_performed is False
    assert report.verification_complete is False
    assert report.scoring_completed is False
    assert report.fidelity_score is None
    assert report.tier_scores == {"level_1": None, "level_2": None, "level_3": None}
    assert report.campaign_contribution == 0.0
    assert report.deck_passed is False
    assert report.eligible is False
    assert report.disqualification_state is DisqualificationState.COMPLETED_INELIGIBLE
    assert report.ineligibility_reasons == [
        "schema_validation_failed",
        "verification_incomplete",
    ]
    assert report.verification_errors[0].code == "schema_validation_failed"
    assert report.schema_violations[0].part == "ppt/slides/slide1.xml"
    assert report.slides == []
    assert report.deck_items == []
    _assert_report_schema(json.loads(report.to_json()))


def test_hosted_unperformed_schema_result_is_a_pre_report_failure(
    tmp_path: Path,
) -> None:
    benchmark = _benchmark(tmp_path / "benchmark")
    submission = _submission(tmp_path / "resolved.pptx")
    environment_attestation = _environment_attestation()
    context = _context(submission, environment_attestation, grading_mode=GradingMode.HOSTED)

    with pytest.raises(ValueError, match="performed Stage 0.5"):
        pipeline.run_resolved_pipeline(
            submission,
            tier=1,
            schema_result=SchemaValidationResult(performed=False, valid=False),
            artifact_context=context,
            benchmark_dir=benchmark,
            cohort_provenance=_cohort(environment_attestation),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("mce_resolved_package_sha256", _sha("0"), "artifact bytes"),
        ("canonical_package_hash_v1", _sha("0"), "canonical package hash"),
        ("mce_profile_sha256", _sha("0"), "artifact profile hashes"),
        ("gold_duplicate_check", GoldDuplicateCheck.BYTE_MATCH, "gold duplicate outcome"),
    ],
)
def test_hosted_context_tamper_fails_before_diagnostic_report(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    benchmark = _benchmark(tmp_path / "benchmark")
    submission = _submission(tmp_path / "resolved.pptx")
    environment_attestation = _environment_attestation()
    context = replace(
        _context(submission, environment_attestation, grading_mode=GradingMode.HOSTED),
        **cast("Any", {field: value}),
    )

    with pytest.raises(ValueError, match=message):
        pipeline.run_resolved_pipeline(
            submission,
            tier=1,
            schema_result=SchemaValidationResult(
                performed=True,
                valid=False,
                violations=["invalid"],
            ),
            artifact_context=context,
            benchmark_dir=benchmark,
            cohort_provenance=_cohort(environment_attestation),
        )


def test_environment_attestation_tamper_fails_before_artifact_parse(tmp_path: Path) -> None:
    benchmark = _benchmark(tmp_path / "benchmark")
    submission = _submission(tmp_path / "resolved.pptx")
    environment_attestation = _environment_attestation()
    context = replace(
        _context(submission, environment_attestation, grading_mode=GradingMode.HOSTED),
        environment_attestation=environment_attestation | {"unexpected": True},
    )

    with pytest.raises(ValueError, match="environment attestation payload"):
        pipeline.run_resolved_pipeline(
            submission,
            tier=1,
            schema_result=SchemaValidationResult(performed=True, valid=False),
            artifact_context=context,
            benchmark_dir=benchmark,
            cohort_provenance=_cohort(environment_attestation),
        )


def test_missing_benchmark_fails_before_emitting_a_report(tmp_path: Path) -> None:
    submission = _submission(tmp_path / "submission.pptx")
    environment_attestation = _environment_attestation()

    with pytest.raises(RuntimeError, match="benchmark data is unavailable"):
        pipeline.run_pipeline(
            submission,
            tier=1,
            benchmark_dir=tmp_path / "missing",
            cohort_provenance=_cohort(environment_attestation),
            artifact_context=_context(submission, environment_attestation),
        )


def test_quarantine_failure_short_circuits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    benchmark, submission, context, cohort = _local_inputs(tmp_path)
    monkeypatch.setattr(
        pipeline,
        "quarantine_check",
        lambda _path: QuarantineResult(passed=False, reason="macro"),
    )

    report = _run_local(submission, benchmark, context, cohort)

    assert report.eligible is False
    assert report.verification_errors == [StableError("quarantine_failed", details="macro")]


@pytest.mark.parametrize("tier", [0, 4])
def test_invalid_tier_rejected(tmp_path: Path, tier: int) -> None:
    with pytest.raises(ValueError, match="Unsupported tier"):
        pipeline.run_pipeline(tmp_path / "submission.pptx", tier=tier)


def test_invalid_output_format_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported output format"):
        pipeline.run_pipeline(tmp_path / "submission.pptx", tier=1, output_format="xml")


def test_extraction_failure_returns_ineligible_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    benchmark, submission, context, cohort = _local_inputs(tmp_path)
    _patch_successful_stages(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "extract_deck_graph",
        lambda _path: (_ for _ in ()).throw(ValueError("broken XML")),
    )

    report = _run_local(submission, benchmark, context, cohort)

    assert report.eligible is False
    assert report.verification_errors == [
        StableError("ooxml_extraction_failed", details="broken XML")
    ]
