"""Fresh-container grading runner."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import rfc8785

from gloss_service.config import Settings


class GradingError(RuntimeError):
    code = "grading_failed"
    retryable = False


class GradingTimeoutError(GradingError):
    code = "grading_timeout"
    retryable = True


class RendererCrashError(GradingError):
    code = "renderer_crash"
    retryable = True


@dataclass(frozen=True)
class GradeOutcome:
    report: dict[str, Any]
    provenance: dict[str, str]
    artifacts: tuple[ArtifactFile, ...] = ()


@dataclass(frozen=True)
class ScoringCohortBinding:
    scoring_cohort_id: str
    scoring_manifest_sha256: str
    grader_source_tree_sha256: str
    environment_attestation_sha256: str


@dataclass(frozen=True)
class HostedArtifactBinding:
    """Artifact-specific identities verified before the hosted grader is invoked."""

    prompt_variant: str
    generation_seed: str | None
    schema_validation_performed: bool
    schema_valid: bool
    schema_violations: tuple[str, ...]
    schema_bundle_sha256: str
    schema_root_map_sha256: str
    mce_profile_sha256: str
    canonical_package_hash_profile_sha256: str
    canonical_package_hash_v1: str
    gold_duplicate_check: str
    submission_sha256: str
    mce_resolved_package_sha256: str
    assistance_class: str
    generation_profile_sha256: str
    attested_metrics: dict[str, Any]
    attestation: dict[str, Any]
    submission_id: str
    campaign_id: str
    robustness_group_id: str | None
    campaign_slot: int
    submitter_id: str
    model_key: str
    model_revision_key: str


@dataclass(frozen=True)
class ReferenceControlBinding:
    """Exact gold identities supplied by a verified maintainer authorization."""

    control_authorization_sha256: str
    original_submission_sha256: str
    mce_resolved_package_sha256: str
    canonical_package_hash_profile_sha256: str
    canonical_package_hash_v1: str
    schema_bundle_sha256: str
    schema_root_map_sha256: str
    mce_profile_sha256: str


@dataclass(frozen=True)
class ArtifactFile:
    name: str
    path: Path
    size_bytes: int
    sha256: str
    content_type: str = "image/png"


@dataclass(frozen=True)
class CanaryGradeOutcome:
    """Exact comparison surfaces emitted by a reference-control regrade."""

    report: dict[str, Any]
    canonical_png_sha256s: tuple[str, ...]
    scene_graph_sha256: str


_GRADE_SCRIPT = """\
import json
import sys
from pathlib import Path
from gloss.models import (
    ArtifactReportContext,
    GoldDuplicateCheck,
    GradingMode,
    RunKind,
    SchemaValidationResult,
)
from gloss.pipeline import run_resolved_pipeline
from gloss.provenance import ScoringCohortProvenance
cohort = ScoringCohortProvenance(**json.loads(sys.argv[3]))
context_value = json.loads(sys.argv[4])
context_value['grading_mode'] = GradingMode(context_value['grading_mode'])
context_value['run_kind'] = RunKind(context_value['run_kind'])
context_value['gold_duplicate_check'] = GoldDuplicateCheck(
    context_value['gold_duplicate_check']
)
context = ArtifactReportContext(**context_value)
schema_result = SchemaValidationResult(**json.loads(sys.argv[5]))
print(run_resolved_pipeline(
    Path(sys.argv[1]),
    int(sys.argv[2]),
    schema_result=schema_result,
    artifact_context=context,
    artifact_dir=Path('/artifacts'),
    cohort_provenance=cohort,
).to_json())
"""


_CANARY_SCRIPT = """\
import hashlib
import json
import sys
from pathlib import Path
from gloss.export import export_slides
from gloss.models import (
    ArtifactReportContext,
    GoldDuplicateCheck,
    GradingMode,
    RunKind,
    SchemaValidationResult,
)
from gloss.pipeline import run_resolved_pipeline
from gloss.provenance import ScoringCohortProvenance
from gloss.scene_graph import canonical_scene_graph_bytes, extract_normative_scene_graph
cohort = ScoringCohortProvenance(**json.loads(sys.argv[3]))
context_value = json.loads(sys.argv[4])
context_value['grading_mode'] = GradingMode(context_value['grading_mode'])
context_value['run_kind'] = RunKind(context_value['run_kind'])
context_value['gold_duplicate_check'] = GoldDuplicateCheck(
    context_value['gold_duplicate_check']
)
context = ArtifactReportContext(**context_value)
schema_result = SchemaValidationResult(performed=True, valid=True, violations=[])
report = run_resolved_pipeline(
    Path(sys.argv[1]),
    int(sys.argv[2]),
    schema_result=schema_result,
    artifact_context=context,
    artifact_dir=Path('/work/diffs'),
    cohort_provenance=cohort,
)
exports = export_slides(Path(sys.argv[1]), Path('/work/canary-export'), expected_page_count=20)
png_hashes = [
    'sha256:' + hashlib.sha256(item.path.read_bytes()).hexdigest()
    for item in exports
]
scene_graph = extract_normative_scene_graph(Path(sys.argv[1]))
scene_hash = 'sha256:' + hashlib.sha256(canonical_scene_graph_bytes(scene_graph)).hexdigest()
payload = {
    'report': json.loads(report.to_json()),
    'canonical_png_sha256s': png_hashes,
    'scene_graph_sha256': scene_hash,
}
print('GLOSS_CANARY_RESULT=' + json.dumps(payload, sort_keys=True, separators=(',', ':')))
"""


class DockerGradingRunner:
    """Run each untrusted deck in a disposable, egress-free container and volume."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _image_hash(self) -> str:
        try:
            result = self._run(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    (
                        '{"id":{{json .Id}},"os":{{json .Os}},'
                        '"architecture":{{json .Architecture}},'
                        '"repo_digests":{{json .RepoDigests}}}'
                    ),
                    self.settings.grader_image,
                ]
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise RendererCrashError("Canonical grader image is unavailable") from exc
        try:
            identity = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RendererCrashError("Canonical grader image identity is malformed") from exc
        if not isinstance(identity, dict):
            raise RendererCrashError("Canonical grader image identity is malformed")
        image_id = identity.get("id")
        operating_system = identity.get("os")
        architecture = identity.get("architecture")
        repo_digests = identity.get("repo_digests")
        if repo_digests is None:
            repo_digests = []
        if (
            not isinstance(image_id, str)
            or not isinstance(operating_system, str)
            or not isinstance(architecture, str)
            or not isinstance(repo_digests, list)
            or not all(isinstance(value, str) and "@sha256:" in value for value in repo_digests)
        ):
            raise RendererCrashError("Canonical grader image identity is malformed")
        validated_repo_digests = cast(list[str], repo_digests)
        platform = f"{operating_system}/{architecture}"
        if platform != "linux/amd64":
            raise GradingError("Canonical grader image must use the frozen linux/amd64 platform")
        attested_platform = self.settings.environment_attestation.get("platform")
        if attested_platform is not None and attested_platform != platform:
            raise GradingError(
                "Canonical grader platform does not match the environment attestation"
            )
        expected = self.settings.grader_image_digest
        manifest_digests = {value.rsplit("@", 1)[1] for value in validated_repo_digests}
        if expected:
            if expected not in manifest_digests:
                raise GradingError(
                    "Canonical grader manifest RepoDigest does not match the configured digest"
                )
            return expected
        if len(manifest_digests) == 1:
            return manifest_digests.pop()
        if manifest_digests:
            raise GradingError("Canonical grader image has ambiguous manifest RepoDigests")
        return image_id

    def _attest_environment(
        self,
        image_hash: str,
        cohort_environment_sha256: str,
    ) -> tuple[dict[str, Any], str]:
        expected = self.settings.environment_attestation
        command = [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(self.settings.grader_pids_limit),
            "--memory",
            self.settings.grader_memory,
            "--cpus",
            self.settings.grader_cpus,
            "--user",
            f"{self.settings.grader_uid}:{self.settings.grader_uid}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--env",
            "HOME=/tmp",
            "--entrypoint",
            "gloss",
            self.settings.grader_image,
            "attest-environment",
            "--expected-json",
            json.dumps(expected, sort_keys=True, separators=(",", ":")),
            "--oci-image-digest",
            image_hash,
        ]
        try:
            result = self._run(command, timeout=120)
        except (subprocess.SubprocessError, OSError) as exc:
            detail = getattr(exc, "stderr", None) or getattr(exc, "stdout", None)
            message = str(detail or "runtime reconstruction failed")[-2000:]
            raise GradingError(f"Canonical environment attestation failed: {message}") from exc
        start = result.stdout.find("{")
        if start < 0:
            raise GradingError("Canonical environment attestation emitted no JSON envelope")
        try:
            envelope = json.loads(result.stdout[start:])
        except json.JSONDecodeError as exc:
            raise GradingError("Canonical environment attestation emitted invalid JSON") from exc
        if not isinstance(envelope, dict):
            raise GradingError("Canonical environment attestation envelope is malformed")
        payload = envelope.get("environment_attestation")
        claimed_sha256 = envelope.get("environment_attestation_sha256")
        if not isinstance(payload, dict) or not isinstance(claimed_sha256, str):
            raise GradingError("Canonical environment attestation envelope is malformed")
        actual_sha256 = f"sha256:{hashlib.sha256(rfc8785.dumps(payload)).hexdigest()}"
        if claimed_sha256 != actual_sha256:
            raise GradingError("Canonical environment attestation envelope hash is invalid")
        if payload != expected:
            raise GradingError(
                "Canonical environment attestation does not match the active release"
            )
        if actual_sha256 != self.settings.active_environment_attestation_sha256:
            raise GradingError("Canonical environment attestation does not match service state")
        if actual_sha256 != cohort_environment_sha256:
            raise GradingError(
                "Canonical environment attestation does not match the scoring cohort"
            )
        return cast(dict[str, Any], payload), actual_sha256

    def grade_reference_control(
        self,
        resolved_gold_path: Path,
        tier: int,
        cohort: ScoringCohortBinding,
        control: ReferenceControlBinding,
    ) -> CanaryGradeOutcome:
        """Regrade one signed gold control and emit all §9.6 comparison surfaces."""
        image_hash = self._image_hash()
        attested_image_hash = self.settings.environment_attestation.get("oci_image_digest")
        if attested_image_hash is not None and attested_image_hash != image_hash:
            raise GradingError("Canonical grader image does not match the environment attestation")
        runtime_attestation, _runtime_attestation_sha256 = self._attest_environment(
            image_hash,
            cohort.environment_attestation_sha256,
        )
        try:
            mounted_gold = resolved_gold_path.resolve(strict=True)
        except OSError as exc:
            raise GradingError("Resolved gold artifact is unavailable") from exc
        cohort_json = json.dumps(
            {
                "scoring_cohort_id": cohort.scoring_cohort_id,
                "scoring_manifest_sha256": cohort.scoring_manifest_sha256,
                "grader_source_tree_sha256": cohort.grader_source_tree_sha256,
                "environment_attestation_sha256": cohort.environment_attestation_sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        context_json = json.dumps(
            {
                "grading_mode": "hosted",
                "run_kind": "reference_control",
                "targeted_tier": tier,
                "prompt_variant": "canonical",
                "generation_seed": None,
                "grader_package_sha256": self.settings.active_grader_package_sha256,
                "oci_image_digest": image_hash,
                "prompt_bundle_sha256": self.settings.active_prompt_bundle_sha256,
                "scored_assertion_inventory_sha256": (
                    self.settings.active_scored_assertion_inventory_sha256
                ),
                "checklist_bundle_sha256": self.settings.active_checklist_bundle_sha256,
                "schema_bundle_sha256": control.schema_bundle_sha256,
                "schema_root_map_sha256": control.schema_root_map_sha256,
                "mce_profile_sha256": control.mce_profile_sha256,
                "asset_manifest_sha256": self.settings.asset_manifest_hash,
                "font_manifest_sha256": self.settings.font_bundle_hash,
                "canonical_package_hash_profile_sha256": (
                    control.canonical_package_hash_profile_sha256
                ),
                "canonical_package_hash_v1": control.canonical_package_hash_v1,
                "gold_duplicate_check": "byte_match",
                "submission_sha256": control.original_submission_sha256,
                "mce_resolved_package_sha256": control.mce_resolved_package_sha256,
                "gold_submission_sha256": control.original_submission_sha256,
                "gold_mce_resolved_package_sha256": control.mce_resolved_package_sha256,
                "gold_canonical_package_hash_v1": control.canonical_package_hash_v1,
                "environment_attestation": runtime_attestation,
                "assistance_class": None,
                "generation_profile_sha256": None,
                "attested_metrics": None,
                "attestation": None,
                "submission_id": None,
                "campaign_id": None,
                "robustness_group_id": None,
                "campaign_slot": None,
                "submitter_id": None,
                "model_key": None,
                "model_revision_key": None,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        command = [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(self.settings.grader_pids_limit),
            "--memory",
            self.settings.grader_memory,
            "--cpus",
            self.settings.grader_cpus,
            "--user",
            f"{self.settings.grader_uid}:{self.settings.grader_uid}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=768m",
            "--tmpfs",
            "/work:rw,noexec,nosuid,size=1536m",
            "--tmpfs",
            "/home/grader/.config:rw,noexec,nosuid,size=64m",
            "--env",
            "HOME=/tmp",
            "--mount",
            f"type=bind,source={mounted_gold},target=/input/gold.pptx,readonly",
            "--entrypoint",
            "python3",
            self.settings.grader_image,
            "-c",
            _CANARY_SCRIPT,
            "/input/gold.pptx",
            str(tier),
            cohort_json,
            context_json,
        ]
        try:
            result = self._run(command, timeout=self.settings.grader_timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise GradingTimeoutError("Reference control exceeded the grading limit") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "Reference control exited unexpectedly")[-2000:]
            raise RendererCrashError(detail) from exc
        marker = "GLOSS_CANARY_RESULT="
        output_line = next(
            (line for line in reversed(result.stdout.splitlines()) if line.startswith(marker)),
            None,
        )
        if output_line is None:
            raise RendererCrashError("Reference control did not emit a canary result")
        try:
            payload = json.loads(output_line[len(marker) :])
        except json.JSONDecodeError as exc:
            raise RendererCrashError("Reference control emitted invalid canary JSON") from exc
        if not isinstance(payload, dict):
            raise RendererCrashError("Reference control emitted a malformed canary result")
        report = payload.get("report")
        png_hashes = payload.get("canonical_png_sha256s")
        scene_hash = payload.get("scene_graph_sha256")
        if (
            not isinstance(report, dict)
            or not isinstance(png_hashes, list)
            or len(png_hashes) != 20
            or not all(isinstance(value, str) for value in png_hashes)
            or not isinstance(scene_hash, str)
        ):
            raise RendererCrashError("Reference control comparison surfaces are malformed")
        return CanaryGradeOutcome(
            report=cast(dict[str, Any], report),
            canonical_png_sha256s=tuple(cast(list[str], png_hashes)),
            scene_graph_sha256=scene_hash,
        )

    def grade(
        self,
        submission_path: Path,
        tier: int,
        submission_id: str,
        cohort: ScoringCohortBinding,
        artifact: HostedArtifactBinding,
    ) -> GradeOutcome:
        image_hash = self._image_hash()
        attested_image_hash = self.settings.environment_attestation.get("oci_image_digest")
        if attested_image_hash is not None and attested_image_hash != image_hash:
            raise GradingError("Canonical grader image does not match the environment attestation")
        runtime_attestation, runtime_attestation_sha256 = self._attest_environment(
            image_hash,
            cohort.environment_attestation_sha256,
        )
        if submission_id != artifact.submission_id:
            raise GradingError("Hosted artifact binding does not match the submission")
        token = uuid.UUID(submission_id).hex
        input_volume = f"gloss-input-{token}"
        artifact_volume = f"gloss-artifacts-{token}"
        staging_container = f"gloss-stage-{token}"
        export_container = f"gloss-export-{token}"
        grading_container = f"gloss-grade-{token}"
        artifact_dir = self.settings.storage_path / "artifacts" / submission_id
        try:
            self._run(["docker", "volume", "create", "--label", "app=gloss", input_volume])
            self._run(["docker", "volume", "create", "--label", "app=gloss", artifact_volume])
            self._run(
                [
                    "docker",
                    "create",
                    "--platform",
                    "linux/amd64",
                    "--name",
                    staging_container,
                    "--mount",
                    f"type=volume,source={input_volume},target=/input",
                    "--entrypoint",
                    "/bin/true",
                    self.settings.grader_image,
                ]
            )
            self._run(
                [
                    "docker",
                    "cp",
                    str(submission_path),
                    f"{staging_container}:/input/submission.pptx",
                ]
            )
            self._run(["docker", "rm", staging_container])
            # docker cp creates the volume entry as root while preserving the
            # source's restrictive mode. Grant only the frozen grader identity
            # access before the untrusted grading container is created.
            self._run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "--network",
                    "none",
                    "--user",
                    "0:0",
                    "--mount",
                    f"type=volume,source={input_volume},target=/input",
                    "--entrypoint",
                    "chown",
                    self.settings.grader_image,
                    f"{self.settings.grader_uid}:{self.settings.grader_uid}",
                    "/input/submission.pptx",
                ]
            )
            # A trusted prep container grants the non-root grader write access to its empty,
            # per-job artifact volume. The untrusted deck is never mounted in this step.
            self._run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "--network",
                    "none",
                    "--user",
                    "0:0",
                    "--mount",
                    f"type=volume,source={artifact_volume},target=/artifacts",
                    "--entrypoint",
                    "chown",
                    self.settings.grader_image,
                    f"{self.settings.grader_uid}:{self.settings.grader_uid}",
                    "/artifacts",
                ]
            )

            cohort_json = json.dumps(
                {
                    "scoring_cohort_id": cohort.scoring_cohort_id,
                    "scoring_manifest_sha256": cohort.scoring_manifest_sha256,
                    "grader_source_tree_sha256": cohort.grader_source_tree_sha256,
                    "environment_attestation_sha256": (cohort.environment_attestation_sha256),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            context_json = json.dumps(
                {
                    "grading_mode": "hosted",
                    "run_kind": "submission",
                    "targeted_tier": tier,
                    "prompt_variant": artifact.prompt_variant,
                    "generation_seed": artifact.generation_seed,
                    "grader_package_sha256": self.settings.active_grader_package_sha256,
                    "oci_image_digest": image_hash,
                    "prompt_bundle_sha256": self.settings.active_prompt_bundle_sha256,
                    "scored_assertion_inventory_sha256": (
                        self.settings.active_scored_assertion_inventory_sha256
                    ),
                    "checklist_bundle_sha256": self.settings.active_checklist_bundle_sha256,
                    "schema_bundle_sha256": artifact.schema_bundle_sha256,
                    "schema_root_map_sha256": artifact.schema_root_map_sha256,
                    "mce_profile_sha256": artifact.mce_profile_sha256,
                    "asset_manifest_sha256": self.settings.asset_manifest_hash,
                    "font_manifest_sha256": self.settings.font_bundle_hash,
                    "canonical_package_hash_profile_sha256": (
                        artifact.canonical_package_hash_profile_sha256
                    ),
                    "canonical_package_hash_v1": artifact.canonical_package_hash_v1,
                    "gold_duplicate_check": artifact.gold_duplicate_check,
                    "submission_sha256": artifact.submission_sha256,
                    "mce_resolved_package_sha256": artifact.mce_resolved_package_sha256,
                    "gold_submission_sha256": self.settings.active_gold_byte_sha256,
                    "gold_mce_resolved_package_sha256": (
                        self.settings.active_gold_mce_resolved_package_sha256
                    ),
                    "gold_canonical_package_hash_v1": (
                        self.settings.active_gold_canonical_package_sha256
                    ),
                    "environment_attestation": runtime_attestation,
                    "assistance_class": artifact.assistance_class,
                    "generation_profile_sha256": artifact.generation_profile_sha256,
                    "attested_metrics": artifact.attested_metrics,
                    "attestation": artifact.attestation,
                    "submission_id": artifact.submission_id,
                    "campaign_id": artifact.campaign_id,
                    "robustness_group_id": artifact.robustness_group_id,
                    "campaign_slot": artifact.campaign_slot,
                    "submitter_id": artifact.submitter_id,
                    "model_key": artifact.model_key,
                    "model_revision_key": artifact.model_revision_key,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            schema_result_json = json.dumps(
                {
                    "performed": artifact.schema_validation_performed,
                    "valid": artifact.schema_valid,
                    "violations": list(artifact.schema_violations),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            command = [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "--name",
                grading_container,
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                str(self.settings.grader_pids_limit),
                "--memory",
                self.settings.grader_memory,
                "--cpus",
                self.settings.grader_cpus,
                "--user",
                f"{self.settings.grader_uid}:{self.settings.grader_uid}",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=768m",
                "--tmpfs",
                "/home/grader/.config:rw,noexec,nosuid,size=64m",
                "--env",
                "HOME=/tmp",
                "--mount",
                f"type=volume,source={input_volume},target=/input,readonly",
                "--mount",
                f"type=volume,source={artifact_volume},target=/artifacts",
                "--entrypoint",
                "python3",
                self.settings.grader_image,
                "-c",
                _GRADE_SCRIPT,
                "/input/submission.pptx",
                str(tier),
                cohort_json,
                context_json,
                schema_result_json,
            ]
            try:
                result = self._run(command, timeout=self.settings.grader_timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                subprocess.run(
                    ["docker", "rm", "-f", grading_container],
                    check=False,
                    capture_output=True,
                    timeout=30,
                )
                raise GradingTimeoutError("Grading exceeded the 10-minute limit") from exc
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or exc.stdout or "Canonical grader exited unexpectedly")[
                    -2000:
                ]
                raise RendererCrashError(detail) from exc

            start = result.stdout.find("{")
            if start < 0:
                raise RendererCrashError("Canonical grader did not emit a JSON report")
            try:
                report = json.loads(result.stdout[start:])
            except json.JSONDecodeError as exc:
                raise RendererCrashError("Canonical grader emitted an invalid JSON report") from exc
            provenance_fields = {
                "docker_image_hash": image_hash,
                "oci_image_digest": image_hash,
                "platform": "linux/amd64",
                "libreoffice_version": str(
                    runtime_attestation.get("runtime_versions", {}).get(
                        "libreoffice", self.settings.libreoffice_version
                    )
                ),
                "font_bundle_hash": self.settings.font_bundle_hash,
                "font_manifest_sha256": self.settings.font_bundle_hash,
                "asset_manifest_hash": self.settings.asset_manifest_hash,
                "asset_manifest_sha256": self.settings.asset_manifest_hash,
                "scoring_manifest_sha256": cohort.scoring_manifest_sha256,
                "grader_source_tree_sha256": cohort.grader_source_tree_sha256,
                "grader_package_sha256": self.settings.active_grader_package_sha256,
                "prompt_bundle_sha256": self.settings.active_prompt_bundle_sha256,
                "scored_assertion_inventory_sha256": (
                    self.settings.active_scored_assertion_inventory_sha256
                ),
                "checklist_bundle_sha256": self.settings.active_checklist_bundle_sha256,
                "gold_submission_sha256": self.settings.active_gold_byte_sha256,
                "gold_mce_resolved_package_sha256": (
                    self.settings.active_gold_mce_resolved_package_sha256
                ),
                "gold_canonical_package_hash_v1": (
                    self.settings.active_gold_canonical_package_sha256
                ),
            }
            environment_hash = hashlib.sha256(
                json.dumps(provenance_fields, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            provenance_fields["environment_hash"] = f"sha256:{environment_hash}"
            provenance_fields["environment_attestation_sha256"] = runtime_attestation_sha256
            artifact_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
            self._run(
                [
                    "docker",
                    "create",
                    "--platform",
                    "linux/amd64",
                    "--name",
                    export_container,
                    "--mount",
                    f"type=volume,source={artifact_volume},target=/artifacts,readonly",
                    "--entrypoint",
                    "/bin/true",
                    self.settings.grader_image,
                ]
            )
            self._run(["docker", "cp", f"{export_container}:/artifacts/.", str(artifact_dir)])
            self._run(["docker", "rm", export_container])
            return GradeOutcome(
                report=report,
                provenance=provenance_fields,
                artifacts=self._collect_artifacts(artifact_dir),
            )
        finally:
            for container in (staging_container, export_container):
                subprocess.run(
                    ["docker", "rm", "-f", container],
                    check=False,
                    capture_output=True,
                    timeout=30,
                )
            for volume in (input_volume, artifact_volume):
                subprocess.run(
                    ["docker", "volume", "rm", "-f", volume],
                    check=False,
                    capture_output=True,
                    timeout=30,
                )

    def _collect_artifacts(self, directory: Path) -> tuple[ArtifactFile, ...]:
        artifacts: list[ArtifactFile] = []
        for path in directory.iterdir():
            if path.is_symlink() or not path.is_file():
                raise GradingError("Grader artifacts contained an unsafe filesystem entry")
            if not path.name.startswith("diff-slide-") or path.suffix.lower() != ".png":
                raise GradingError(f"Grader artifact had an unexpected name: {path.name}")
            size = path.stat().st_size
            if size > 50 * 1024 * 1024:
                raise GradingError(f"Grader artifact exceeds 50 MB: {path.name}")
            artifacts.append(
                ArtifactFile(
                    name=path.name,
                    path=path,
                    size_bytes=size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
        return tuple(sorted(artifacts, key=lambda artifact: artifact.name))


class InsecureTestRunner:
    """Deterministic runner available only when explicitly enabled outside production."""

    def __init__(self, settings: Settings) -> None:
        if settings.app_env == "production" or not settings.allow_insecure_test_runner:
            raise RuntimeError("The insecure test runner is disabled")
        self.settings = settings

    def grade(
        self,
        submission_path: Path,
        tier: int,
        submission_id: str,
        cohort: ScoringCohortBinding,
        artifact: HostedArtifactBinding,
    ) -> GradeOutcome:
        score = round(0.7 + tier * 0.05, 4)
        reported_score = score if artifact.schema_valid else None
        report: dict[str, Any] = {
            "benchmark_version": self.settings.active_benchmark_versions[0],
            "grader_version": "insecure-test-runner",
            "environment_hash": "test-only",
            "scoring_cohort_id": cohort.scoring_cohort_id,
            "scoring_manifest_sha256": cohort.scoring_manifest_sha256,
            "grader_source_tree_sha256": cohort.grader_source_tree_sha256,
            "environment_attestation_sha256": cohort.environment_attestation_sha256,
            "environment_attestation": self.settings.environment_attestation,
            "grader_package_sha256": self.settings.active_grader_package_sha256,
            "oci_image_digest": "insecure-test-runner",
            "platform": "test",
            "prompt_bundle_sha256": self.settings.active_prompt_bundle_sha256,
            "scored_assertion_inventory_sha256": (
                self.settings.active_scored_assertion_inventory_sha256
            ),
            "checklist_bundle_sha256": self.settings.active_checklist_bundle_sha256,
            "schema_bundle_sha256": artifact.schema_bundle_sha256,
            "schema_root_map_sha256": artifact.schema_root_map_sha256,
            "mce_profile_sha256": artifact.mce_profile_sha256,
            "asset_manifest_sha256": self.settings.asset_manifest_hash,
            "font_manifest_sha256": self.settings.font_bundle_hash,
            "grading_mode": "hosted",
            "run_kind": "submission",
            "canonical_package_hash_profile_sha256": (
                artifact.canonical_package_hash_profile_sha256
            ),
            "canonical_package_hash_v1": artifact.canonical_package_hash_v1,
            "gold_duplicate_check": artifact.gold_duplicate_check,
            "generation_seed": artifact.generation_seed,
            "submission_id": artifact.submission_id,
            "campaign_id": artifact.campaign_id,
            "robustness_group_id": artifact.robustness_group_id,
            "campaign_slot": artifact.campaign_slot,
            "submitter_id": artifact.submitter_id,
            "model_key": artifact.model_key,
            "model_revision_key": artifact.model_revision_key,
            "targeted_tier": tier,
            "prompt_variant": artifact.prompt_variant,
            "assistance_class": artifact.assistance_class,
            "generation_profile_sha256": artifact.generation_profile_sha256,
            "submission_sha256": artifact.submission_sha256,
            "mce_resolved_package_sha256": artifact.mce_resolved_package_sha256,
            "gold_submission_sha256": self.settings.active_gold_byte_sha256,
            "gold_mce_resolved_package_sha256": (
                self.settings.active_gold_mce_resolved_package_sha256
            ),
            "gold_canonical_package_hash_v1": (self.settings.active_gold_canonical_package_sha256),
            "attested_metrics": artifact.attested_metrics,
            "attestation": artifact.attestation,
            "submission": submission_path.name,
            "schema_validation_performed": artifact.schema_validation_performed,
            "schema_valid": artifact.schema_valid,
            "verification_complete": artifact.schema_valid,
            "scoring_completed": artifact.schema_valid,
            "repair_triggered": False,
            "grading_duration_seconds": 0.01,
            "fidelity_score": reported_score,
            "campaign_contribution": score if artifact.schema_valid else 0.0,
            "passed_items": tier * 10 if artifact.schema_valid else 0,
            "total_items": tier * 12 if artifact.schema_valid else 0,
            "deck_passed": False,
            "eligible": artifact.schema_valid,
            "tier_scores": (
                {f"level_{tier}": {"fidelity_score": score}}
                if artifact.schema_valid
                else {"level_1": None, "level_2": None, "level_3": None}
            ),
            "verified_metrics": {"submission_file_size_bytes": submission_path.stat().st_size},
            "anti_cheat_flags": [],
            "slides": [],
            "deck_items": [],
        }
        provenance = {
            "docker_image_hash": "insecure-test-runner",
            "oci_image_digest": "insecure-test-runner",
            "libreoffice_version": "test",
            "font_bundle_hash": "test",
            "font_manifest_sha256": self.settings.font_bundle_hash,
            "asset_manifest_hash": "test",
            "asset_manifest_sha256": self.settings.asset_manifest_hash,
            "environment_hash": "test-only",
            "scoring_manifest_sha256": cohort.scoring_manifest_sha256,
            "grader_source_tree_sha256": cohort.grader_source_tree_sha256,
            "environment_attestation_sha256": cohort.environment_attestation_sha256,
            "grader_package_sha256": self.settings.active_grader_package_sha256,
            "prompt_bundle_sha256": self.settings.active_prompt_bundle_sha256,
            "scored_assertion_inventory_sha256": (
                self.settings.active_scored_assertion_inventory_sha256
            ),
            "checklist_bundle_sha256": self.settings.active_checklist_bundle_sha256,
            "gold_submission_sha256": self.settings.active_gold_byte_sha256,
            "gold_mce_resolved_package_sha256": (
                self.settings.active_gold_mce_resolved_package_sha256
            ),
            "gold_canonical_package_hash_v1": (self.settings.active_gold_canonical_package_sha256),
        }
        return GradeOutcome(report, provenance)
