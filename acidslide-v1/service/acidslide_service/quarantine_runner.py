"""Disposable quarantine runner implementations."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from acidslide_service.config import Settings
from acidslide_service.quarantine_handoff import QuarantineJobBinding


class QuarantineRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuarantineRunResult:
    envelope: dict[str, Any]
    resolved_path: Path | None
    job_dir: Path

    def cleanup(self) -> None:
        shutil.rmtree(self.job_dir, ignore_errors=True)


class QuarantineRunner(Protocol):
    def assert_ready(self) -> None: ...

    def inspect(
        self,
        *,
        original_path: Path,
        binding: QuarantineJobBinding,
    ) -> QuarantineRunResult: ...


def _job_files(settings: Settings, submission_id: str) -> tuple[Path, Path, Path, Path, Path]:
    token = uuid.uuid4().hex
    (settings.storage_path / "staging").mkdir(parents=True, exist_ok=True, mode=0o700)
    job_dir = settings.storage_path / "quarantine-jobs" / f"{submission_id}-{token}"
    job_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    binding_path = job_dir / "binding.json"
    resolved_path = job_dir / "resolved.pptx"
    verdict_path = job_dir / "verdict.json"
    key_path = settings.storage_path / "staging" / f"quarantine-key-{token}"
    return job_dir, binding_path, resolved_path, verdict_path, key_path


def _binding_dict(binding: QuarantineJobBinding) -> dict[str, Any]:
    return {
        "campaign_id": binding.campaign_id,
        "campaign_slot": binding.campaign_slot,
        "original": binding.original.as_dict(),
        "resolved_object_version": binding.resolved_object_version,
        "submission_id": binding.submission_id,
        "tier": binding.tier,
    }


def _job_environment(settings: Settings) -> dict[str, str]:
    return {
        # The quarantine image is derived from the canonical grader image, whose
        # renderer clock is intentionally frozen for deterministic scoring. A
        # signed quarantine verdict is a live, short-lived security credential,
        # so it must use the host wall clock instead of inheriting libfaketime.
        "LD_PRELOAD": "",
        "FAKETIME": "",
        "FAKETIME_DONT_FAKE_MONOTONIC": "",
        "FAKETIME_NO_CACHE": "",
        "ACIDSLIDE_APP_ENV": "quarantine",
        "ACIDSLIDE_MAX_UPLOAD_BYTES": str(settings.max_upload_bytes),
        "ACIDSLIDE_MAX_UNCOMPRESSED_BYTES": str(settings.max_uncompressed_bytes),
        "ACIDSLIDE_MAX_ZIP_ENTRIES": str(settings.max_zip_entries),
        "ACIDSLIDE_MAX_DECOMPRESSION_RATIO": str(settings.max_decompression_ratio),
        "ACIDSLIDE_QUARANTINE_VERDICT_TTL_SECONDS": str(settings.quarantine_verdict_ttl_seconds),
    }


class InsecureInProcessQuarantineRunner:
    """Fast test runner; production settings reject this mode."""

    def __init__(self, settings: Settings) -> None:
        if settings.app_env == "production" or not settings.allow_insecure_quarantine_runner:
            raise RuntimeError("The insecure quarantine runner is disabled")
        self.settings = settings

    def assert_ready(self) -> None:
        return None

    def inspect(
        self,
        *,
        original_path: Path,
        binding: QuarantineJobBinding,
    ) -> QuarantineRunResult:
        from acidslide_service.quarantine_job import execute_quarantine_job

        job_dir, _binding_path, resolved_path, _verdict_path, _key_path = _job_files(
            self.settings, binding.submission_id
        )
        envelope = execute_quarantine_job(
            original_path=original_path,
            resolved_path=resolved_path,
            binding=binding,
            settings=self.settings,
            private_key_value=self.settings.quarantine_signing_private_key,
            key_id=self.settings.quarantine_signing_key_id,
        )
        return QuarantineRunResult(
            envelope=envelope,
            resolved_path=resolved_path if resolved_path.exists() else None,
            job_dir=job_dir,
        )


class LocalSubprocessQuarantineRunner:
    """Development runner proving ZIP/XML parsing is outside the API process."""

    def __init__(self, settings: Settings) -> None:
        if settings.app_env == "production" or not settings.allow_insecure_quarantine_runner:
            raise RuntimeError("The local quarantine runner is disabled")
        self.settings = settings

    def assert_ready(self) -> None:
        return None

    def inspect(
        self,
        *,
        original_path: Path,
        binding: QuarantineJobBinding,
    ) -> QuarantineRunResult:
        job_dir, binding_path, resolved_path, verdict_path, key_path = _job_files(
            self.settings, binding.submission_id
        )
        try:
            binding_path.write_text(json.dumps(_binding_dict(binding)), encoding="utf-8")
            key_path.write_text(self.settings.quarantine_signing_private_key, encoding="ascii")
            os.chmod(binding_path, 0o600)
            os.chmod(key_path, 0o600)
            environment = os.environ.copy()
            environment.update(_job_environment(self.settings))
            grader_path = Path(__file__).resolve().parents[2] / "grader"
            existing = environment.get("PYTHONPATH", "")
            environment["PYTHONPATH"] = os.pathsep.join(
                value for value in (str(grader_path), existing) if value
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "acidslide_service.quarantine_job",
                    "--input",
                    str(original_path),
                    "--resolved",
                    str(resolved_path),
                    "--binding",
                    str(binding_path),
                    "--verdict",
                    str(verdict_path),
                    "--private-key",
                    str(key_path),
                    "--key-id",
                    self.settings.quarantine_signing_key_id,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.settings.quarantine_timeout_seconds,
                env=environment,
            )
            envelope = json.loads(verdict_path.read_text(encoding="utf-8"))
            return QuarantineRunResult(
                envelope=envelope,
                resolved_path=resolved_path if resolved_path.exists() else None,
                job_dir=job_dir,
            )
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise QuarantineRunnerError("Local quarantine process failed") from exc
        finally:
            key_path.unlink(missing_ok=True)


class DockerQuarantineRunner:
    """Production Stage 0/0.5 runner: fresh, constrained, and egress-free."""

    def __init__(self, settings: Settings) -> None:
        if settings.app_env == "production" and not settings.quarantine_image_digest:
            raise RuntimeError("The production quarantine image digest is not pinned")
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
                    self.settings.quarantine_image,
                ]
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise QuarantineRunnerError("Quarantine image is unavailable") from exc
        try:
            identity = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise QuarantineRunnerError("Quarantine image identity is malformed") from exc
        if not isinstance(identity, dict):
            raise QuarantineRunnerError("Quarantine image identity is malformed")
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
            raise QuarantineRunnerError("Quarantine image identity is malformed")
        if f"{operating_system}/{architecture}" != "linux/amd64":
            raise QuarantineRunnerError("Quarantine image must use the frozen linux/amd64 platform")
        manifest_digests = {
            value.rsplit("@", 1)[1] for value in repo_digests if isinstance(value, str)
        }
        expected = self.settings.quarantine_image_digest
        if expected:
            if expected not in manifest_digests:
                raise QuarantineRunnerError(
                    "Quarantine image manifest RepoDigest does not match configuration"
                )
            return expected
        if len(manifest_digests) == 1:
            return manifest_digests.pop()
        if manifest_digests:
            raise QuarantineRunnerError("Quarantine image has ambiguous manifest RepoDigests")
        return image_id

    def assert_ready(self) -> None:
        self._image_hash()

    def inspect(
        self,
        *,
        original_path: Path,
        binding: QuarantineJobBinding,
    ) -> QuarantineRunResult:
        self._image_hash()
        job_dir, binding_path, resolved_path, verdict_path, key_path = _job_files(
            self.settings, binding.submission_id
        )
        container_name = f"acidslide-quarantine-{uuid.UUID(binding.submission_id).hex}"
        try:
            binding_path.write_text(json.dumps(_binding_dict(binding)), encoding="utf-8")
            key_path.write_text(self.settings.quarantine_signing_private_key, encoding="ascii")
            os.chmod(binding_path, 0o600)
            os.chmod(key_path, 0o600)
            command = [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "--name",
                container_name,
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                str(self.settings.quarantine_pids_limit),
                "--memory",
                self.settings.quarantine_memory,
                "--cpus",
                self.settings.quarantine_cpus,
                "--user",
                f"{self.settings.quarantine_uid}:{self.settings.quarantine_uid}",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=128m",
                "--mount",
                f"type=bind,source={original_path},target=/input/original.pptx,readonly",
                "--mount",
                f"type=bind,source={job_dir},target=/output",
                "--mount",
                f"type=bind,source={key_path},target=/run/secrets/quarantine-key,readonly",
            ]
            for name, value in _job_environment(self.settings).items():
                command.extend(["--env", f"{name}={value}"])
            command.extend(
                [
                    "--entrypoint",
                    "python3",
                    self.settings.quarantine_image,
                    "-m",
                    "acidslide_service.quarantine_job",
                    "--input",
                    "/input/original.pptx",
                    "--resolved",
                    "/output/resolved.pptx",
                    "--binding",
                    "/output/binding.json",
                    "--verdict",
                    "/output/verdict.json",
                    "--private-key",
                    "/run/secrets/quarantine-key",
                    "--key-id",
                    self.settings.quarantine_signing_key_id,
                ]
            )
            self._run(command, timeout=self.settings.quarantine_timeout_seconds)
            envelope = json.loads(verdict_path.read_text(encoding="utf-8"))
            return QuarantineRunResult(
                envelope=envelope,
                resolved_path=resolved_path if resolved_path.exists() else None,
                job_dir=job_dir,
            )
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                check=False,
                capture_output=True,
                timeout=30,
            )
            shutil.rmtree(job_dir, ignore_errors=True)
            raise QuarantineRunnerError("Disposable quarantine container failed") from exc
        finally:
            key_path.unlink(missing_ok=True)
