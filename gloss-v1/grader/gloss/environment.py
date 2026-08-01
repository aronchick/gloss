"""Fingerprint the actual grading environment used for a report."""

from __future__ import annotations

import hashlib
import json
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath
from typing import Any

import rfc8785
from jsonschema import Draft202012Validator

from gloss import __version__
from gloss.export import EXPORT_HEIGHT, EXPORT_WIDTH, find_libreoffice
from gloss.profile_contract import environment_profile_hashes, load_render_profiles
from gloss.resources import resolve_normative_schema_file
from gloss.source_tree import build_grader_source_tree_manifest

_PROCESS_ENVIRONMENT_KEYS = (
    "FAKETIME",
    "FAKETIME_DONT_FAKE_MONOTONIC",
    "FAKETIME_NO_CACHE",
    "LD_PRELOAD",
    "TZ",
    "LANG",
    "LC_ALL",
)
_PREFIXED_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_DOCKER_DIGEST = re.compile(
    r"^FROM\s+(?P<image>\S+)@(?P<digest>sha256:[0-9a-f]{64})(?:\s+AS\s+(?P<stage>\S+))?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_DEFAULT_DOCKERFILE = Path("/opt/gloss/build/Dockerfile")
_DEFAULT_LOCKFILE = Path("/opt/gloss/grader/uv.lock")
_DEFAULT_GRADER_ROOT = Path("/opt/gloss/grader")


class EnvironmentAttestationError(ValueError):
    """The running grader cannot reproduce the frozen environment payload."""


def environment_details() -> dict[str, Any]:
    """Collect the renderer, runtime, and dependency versions that affect grading."""
    details: dict[str, Any] = {
        "grader_version": __version__,
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "locale": _locale_name(),
        "timezone": os.environ.get("TZ", "system-default"),
        "export_width": EXPORT_WIDTH,
        "export_height": EXPORT_HEIGHT,
        "dependencies": {
            package: _package_version(package)
            for package in ("lxml", "numpy", "Pillow", "scikit-image")
        },
        "libreoffice": _libreoffice_version(),
    }
    return details


def environment_hash(details: dict[str, Any] | None = None) -> str:
    """Return a SHA-256 identifier for the effective grading environment."""
    if details is None:
        details = environment_details()
    payload = json.dumps(details, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def environment_attestation_sha256(payload: dict[str, Any]) -> str:
    """Hash one schema-valid environment payload using the normative JCS rule."""
    return f"sha256:{hashlib.sha256(rfc8785.dumps(payload)).hexdigest()}"


def runtime_freeze_input(payload: dict[str, Any]) -> dict[str, str]:
    """Project one attestation into the separately validated manifest-builder input."""
    versions = payload.get("runtime_versions")
    fonts = payload.get("font_environment")
    binaries = payload.get("binary_inventory")
    if (
        not isinstance(versions, dict)
        or not isinstance(fonts, dict)
        or not isinstance(binaries, list)
    ):
        raise EnvironmentAttestationError("Environment attestation cannot form a runtime freeze")
    libfaketime = [
        record
        for record in binaries
        if isinstance(record, dict) and record.get("name") == "libfaketime"
    ]
    if len(libfaketime) != 1:
        raise EnvironmentAttestationError("Environment attestation has no unique libfaketime file")
    projection = {
        "platform": payload.get("platform"),
        "oci_image_digest": payload.get("oci_image_digest"),
        **{
            name: versions.get(name)
            for name in (
                "libreoffice",
                "poppler",
                "python",
                "pillow",
                "numpy",
                "scikit_image",
                "lxml",
                "grader",
                "libfaketime",
                "fontconfig",
            )
        },
        "libfaketime_library_sha256": libfaketime[0].get("sha256"),
        "fontconfig_config_sha256": fonts.get("fontconfig_config_sha256"),
        "environment_attestation_sha256": environment_attestation_sha256(payload),
    }
    if not all(isinstance(value, str) and value for value in projection.values()):
        raise EnvironmentAttestationError("Environment attestation runtime freeze is incomplete")
    return projection  # type: ignore[return-value]


def construct_environment_attestation_candidate(
    *,
    oci_image_digest: str,
    attested_at: str,
    canary_id: str,
    canary_input_path: Path,
    canary_report_path: Path,
    schema_path: Path | None = None,
    schema_dir: Path | None = None,
    font_manifest_path: Path = Path("/opt/gloss/benchmark/fonts/manifest.json"),
    dockerfile_path: Path = _DEFAULT_DOCKERFILE,
    grader_lockfile_path: Path = _DEFAULT_LOCKFILE,
    grader_root: Path = _DEFAULT_GRADER_ROOT,
    source_tree_profile_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Construct an honest, current-image candidate and its source-tree manifest.

    The result is not a frozen release identity. It becomes one only after the
    immutable OCI digest, source tree, canary, evidence, manifest, and release
    signatures are independently frozen. Every field emitted here is derived
    from supplied bytes or reconstructed inside the isolated linux/amd64 image.
    """
    _require_prefixed_sha256(oci_image_digest, "oci_image_digest")
    _require_utc_timestamp(attested_at)
    if not canary_id or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,127}", canary_id):
        raise EnvironmentAttestationError("canary_id is not a canonical v1 identifier")
    platform_name = _platform_name()
    if platform_name != "linux/amd64":
        raise EnvironmentAttestationError(
            f"Runtime platform is not the frozen linux/amd64 target: {platform_name}"
        )
    process_environment = {name: os.environ.get(name, "") for name in _PROCESS_ENVIRONMENT_KEYS}
    profiles = load_render_profiles(schema_dir)
    source_manifest = _build_source_tree_manifest(grader_root, source_tree_profile_path, schema_dir)
    source_sha256 = f"sha256:{hashlib.sha256(rfc8785.dumps(source_manifest)).hexdigest()}"
    expected_font_environment = {"fontconfig_file": os.environ.get("FONTCONFIG_FILE")}
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "attestation_id": "gloss-environment-attestation-v1",
        "canonicalization": "RFC8785-JCS",
        "attestation_state": "verified",
        "attested_at": attested_at,
        "platform": platform_name,
        "oci_image_digest": oci_image_digest,
        "build_inputs": _build_inputs(dockerfile_path, grader_lockfile_path),
        "runtime_versions": _runtime_versions(),
        "binary_inventory": _current_binary_inventory(),
        "font_environment": _font_environment(expected_font_environment, font_manifest_path),
        "process_environment": process_environment,
        "export_contract": profiles.export_contract(),
        "profile_hashes": environment_profile_hashes(schema_dir),
        "grader_source_tree_sha256": source_sha256,
        "canary": {
            "canary_id": canary_id,
            "input_sha256": _sha256_path(canary_input_path),
            "score_semantic_report_sha256": _sha256_path(canary_report_path),
        },
        "verification": {
            "architecture_verified": True,
            "binary_hashes_verified": True,
            "font_inventory_verified": True,
            "clock_fixture_verified": _clock_fixture_is_verified(),
            "network_disabled_verified": _network_is_disabled(),
        },
    }
    if not payload["verification"]["clock_fixture_verified"]:
        raise EnvironmentAttestationError("Runtime clock fixture is not frozen to the v1 reference")
    if not payload["verification"]["network_disabled_verified"]:
        raise EnvironmentAttestationError("Runtime network namespace is not isolated")
    resolved_schema = resolve_normative_schema_file(
        "environment-attestation.schema.json", schema_path or schema_dir
    )
    validator = _load_attestation_validator(resolved_schema)
    _validate_attestation(validator, payload, "Candidate environment attestation")
    return payload, source_manifest


def reconstruct_environment_attestation(
    expected: dict[str, Any],
    *,
    oci_image_digest: str,
    schema_path: Path | None = None,
    schema_dir: Path | None = None,
    font_manifest_path: Path = Path("/opt/gloss/benchmark/fonts/manifest.json"),
    dockerfile_path: Path = _DEFAULT_DOCKERFILE,
    grader_lockfile_path: Path = _DEFAULT_LOCKFILE,
    grader_root: Path = _DEFAULT_GRADER_ROOT,
    source_tree_profile_path: Path | None = None,
) -> dict[str, Any]:
    """Rebuild runtime-controlled attestation fields and require an exact match.

    Release-time identities that cannot be derived from inside an OCI filesystem
    remain in the signed expected payload. Platform, runtime build strings,
    executable bytes, Fontconfig state, font bytes, process inputs, and network
    isolation are reconstructed from the live grading container.
    """
    if not isinstance(expected, dict):
        raise EnvironmentAttestationError("Expected environment attestation must be an object")
    resolved_schema = resolve_normative_schema_file(
        "environment-attestation.schema.json", schema_path or schema_dir
    )
    validator = _load_attestation_validator(resolved_schema)
    _validate_attestation(validator, expected, "Expected environment attestation")
    if expected.get("oci_image_digest") != oci_image_digest:
        raise EnvironmentAttestationError(
            "Verified OCI image digest does not match the frozen environment attestation"
        )

    reconstructed = deepcopy(expected)
    reconstructed["platform"] = _platform_name()
    reconstructed["oci_image_digest"] = oci_image_digest
    reconstructed["build_inputs"] = _build_inputs(dockerfile_path, grader_lockfile_path)
    reconstructed["runtime_versions"] = _runtime_versions()
    reconstructed["binary_inventory"] = _binary_inventory(expected.get("binary_inventory"))
    reconstructed["font_environment"] = _font_environment(
        expected.get("font_environment"), font_manifest_path
    )
    reconstructed["process_environment"] = {
        name: os.environ.get(name, "") for name in _PROCESS_ENVIRONMENT_KEYS
    }
    reconstructed["export_contract"] = load_render_profiles(schema_dir).export_contract()
    reconstructed["profile_hashes"] = environment_profile_hashes(schema_dir)
    source_manifest = _build_source_tree_manifest(grader_root, source_tree_profile_path, schema_dir)
    reconstructed["grader_source_tree_sha256"] = (
        f"sha256:{hashlib.sha256(rfc8785.dumps(source_manifest)).hexdigest()}"
    )
    if reconstructed["platform"] != "linux/amd64":
        raise EnvironmentAttestationError(
            f"Runtime platform is not the frozen linux/amd64 target: {reconstructed['platform']}"
        )
    if not _network_is_disabled():
        raise EnvironmentAttestationError("Runtime network namespace is not isolated")
    if not _clock_fixture_is_verified():
        raise EnvironmentAttestationError("Runtime clock fixture is not frozen to the v1 reference")
    reconstructed["verification"] = {
        "architecture_verified": True,
        "binary_hashes_verified": True,
        "font_inventory_verified": True,
        "clock_fixture_verified": True,
        "network_disabled_verified": True,
    }
    _validate_attestation(validator, reconstructed, "Reconstructed environment attestation")
    if reconstructed != expected:
        changed = sorted(
            key
            for key in set(expected) | set(reconstructed)
            if expected.get(key) != reconstructed.get(key)
        )
        raise EnvironmentAttestationError(
            "Runtime environment attestation mismatch in: " + ", ".join(changed)
        )
    return reconstructed


def _load_attestation_validator(path: Path) -> Draft202012Validator:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise EnvironmentAttestationError(
            f"Environment attestation schema is unreadable or invalid: {path}"
        ) from exc
    return Draft202012Validator(schema)


def _validate_attestation(
    validator: Draft202012Validator,
    payload: dict[str, Any],
    label: str,
) -> None:
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    if errors:
        location = "/".join(str(value) for value in errors[0].absolute_path) or "<root>"
        raise EnvironmentAttestationError(f"{label} is invalid at {location}: {errors[0].message}")


def _platform_name() -> str:
    operating_system = platform.system().lower()
    machine = platform.machine().lower()
    architecture = "amd64" if machine in {"amd64", "x86_64"} else machine
    return f"{operating_system}/{architecture}"


def _runtime_versions() -> dict[str, str]:
    return {
        "libreoffice": _command_version([str(find_libreoffice()), "--version"]),
        "poppler": _command_version(["pdftoppm", "-v"]),
        "python": platform.python_version(),
        "pillow": _required_package_version("Pillow"),
        "numpy": _required_package_version("numpy"),
        "scikit_image": _required_package_version("scikit-image"),
        "lxml": _required_package_version("lxml"),
        "grader": __version__,
        "libfaketime": _command_version(["dpkg-query", "-W", "-f=${Version}", "libfaketime"]),
        "fontconfig": _command_version(["fc-list", "--version"]),
    }


def _current_binary_inventory() -> list[dict[str, str]]:
    paths = {
        "fontconfig": _required_executable("fc-list"),
        "libfaketime": _required_runtime_file(
            Path("/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1")
        ),
        "libreoffice": find_libreoffice().resolve(),
        "pdftoppm": _required_executable("pdftoppm"),
        "python": Path(sys.executable).resolve(),
    }
    return [
        {"name": name, "path": str(path), "sha256": _sha256_path(path)}
        for name, path in sorted(paths.items())
    ]


def _required_executable(name: str) -> Path:
    value = shutil.which(name)
    if not value:
        raise EnvironmentAttestationError(f"Required runtime executable is missing: {name}")
    path = Path(value).resolve()
    if not path.is_file():
        raise EnvironmentAttestationError(f"Required runtime executable is unavailable: {path}")
    return path


def _required_runtime_file(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise EnvironmentAttestationError(f"Required runtime file is unavailable: {path}")
    return resolved


def _build_inputs(dockerfile_path: Path, grader_lockfile_path: Path) -> dict[str, str]:
    try:
        dockerfile = dockerfile_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EnvironmentAttestationError(
            f"Attested Dockerfile is unreadable: {dockerfile_path}"
        ) from exc
    matches = list(_DOCKER_DIGEST.finditer(dockerfile))
    base_digests = [
        match.group("digest")
        for match in matches
        if match.group("image").lower().startswith("ubuntu:")
    ]
    uv_digests = [
        match.group("digest")
        for match in matches
        if match.group("stage") and match.group("stage").lower() == "uv"
    ]
    if len(base_digests) != 1 or len(uv_digests) != 1:
        raise EnvironmentAttestationError(
            "Dockerfile must contain exactly one digest-pinned Ubuntu base and uv stage"
        )
    return {
        "dockerfile_sha256": _sha256_path(dockerfile_path),
        "grader_lockfile_sha256": _sha256_path(grader_lockfile_path),
        "base_image_digest": base_digests[0],
        "uv_image_digest": uv_digests[0],
    }


def _build_source_tree_manifest(
    grader_root: Path,
    source_tree_profile_path: Path | None,
    schema_dir: Path | None,
) -> dict[str, Any]:
    profile = resolve_normative_schema_file(
        "grader-source-tree-profile-v1.json", source_tree_profile_path or schema_dir
    )
    try:
        return build_grader_source_tree_manifest(grader_root, profile)
    except (OSError, RuntimeError, ValueError) as exc:
        raise EnvironmentAttestationError(
            f"Grader source tree cannot be reconstructed: {grader_root}"
        ) from exc


def _clock_fixture_is_verified() -> bool:
    if os.environ.get("LD_PRELOAD") != "/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1":
        return False
    try:
        completed = subprocess.run(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
            capture_output=True,
            check=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.stdout.strip() == "2025-01-01T00:00:00Z"


def _require_prefixed_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or not _PREFIXED_SHA256.fullmatch(value):
        raise EnvironmentAttestationError(f"{name} is not a canonical prefixed SHA-256")


def _require_utc_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise EnvironmentAttestationError("attested_at is not an RFC 3339 timestamp") from exc
    if not value.endswith("Z") or parsed.tzinfo != UTC:
        raise EnvironmentAttestationError("attested_at must be serialized in UTC with Z")


def _required_package_version(package: str) -> str:
    value = _package_version(package)
    if value == "not-installed":
        raise EnvironmentAttestationError(f"Required scoring library is not installed: {package}")
    return value


def _command_version(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EnvironmentAttestationError(
            f"Required runtime version command failed: {command[0]}"
        ) from exc
    output = "\n".join(
        value.strip() for value in (completed.stdout, completed.stderr) if value.strip()
    )
    if not output:
        raise EnvironmentAttestationError(
            f"Required runtime version command returned no build ID: {command[0]}"
        )
    return output


def _binary_inventory(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise EnvironmentAttestationError("Frozen binary inventory is missing")
    inventory: list[dict[str, str]] = []
    identities: set[str] = set()
    for record in value:
        if not isinstance(record, dict):
            raise EnvironmentAttestationError("Frozen binary inventory is malformed")
        name = record.get("name")
        raw_path = record.get("path")
        if not isinstance(name, str) or not isinstance(raw_path, str):
            raise EnvironmentAttestationError("Frozen binary inventory is malformed")
        path = Path(raw_path)
        if not path.is_absolute() or not path.is_file():
            raise EnvironmentAttestationError(f"Attested executable is unavailable: {raw_path}")
        if name in identities:
            raise EnvironmentAttestationError(f"Duplicate attested executable name: {name}")
        identities.add(name)
        inventory.append({"name": name, "path": raw_path, "sha256": _sha256_path(path)})
    return sorted(inventory, key=lambda record: (record["name"], record["path"]))


def _font_environment(value: object, manifest_path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EnvironmentAttestationError("Frozen font environment is missing")
    configured_path = os.environ.get("FONTCONFIG_FILE")
    if not configured_path:
        raise EnvironmentAttestationError("FONTCONFIG_FILE is not set")
    fontconfig_file = Path(configured_path)
    if not fontconfig_file.is_absolute() or not fontconfig_file.is_file():
        raise EnvironmentAttestationError(
            f"Fontconfig configuration is unavailable: {configured_path}"
        )
    expected_fontconfig = value.get("fontconfig_file")
    if expected_fontconfig != configured_path:
        raise EnvironmentAttestationError(
            "FONTCONFIG_FILE does not match the frozen environment attestation"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise EnvironmentAttestationError(f"Font manifest is unreadable: {manifest_path}") from exc
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, list) or not files:
        raise EnvironmentAttestationError("Font manifest has no file inventory")
    expected_fonts: dict[str, str] = {}
    for record in files:
        if not isinstance(record, dict):
            raise EnvironmentAttestationError("Font manifest file inventory is malformed")
        local_path = record.get("local_path")
        sha256 = record.get("sha256")
        if not isinstance(local_path, str) or not isinstance(sha256, str):
            raise EnvironmentAttestationError("Font manifest file inventory is malformed")
        relative = PurePosixPath(local_path)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise EnvironmentAttestationError(f"Unsafe font manifest path: {local_path!r}")
        absolute = str((manifest_path.parent / Path(*relative.parts)).resolve())
        if absolute in expected_fonts:
            raise EnvironmentAttestationError(f"Duplicate font manifest path: {local_path}")
        expected_fonts[absolute] = sha256.removeprefix("sha256:")
    discovered = _discover_font_paths()
    if set(discovered) != set(expected_fonts):
        missing = sorted(set(expected_fonts) - set(discovered))
        extra = sorted(set(discovered) - set(expected_fonts))
        raise EnvironmentAttestationError(
            f"Fontconfig inventory mismatch: missing={missing} extra={extra}"
        )
    records: list[dict[str, str]] = []
    for raw_path in discovered:
        path = Path(raw_path)
        actual = _sha256_path(path)
        if actual.removeprefix("sha256:") != expected_fonts[raw_path]:
            raise EnvironmentAttestationError(f"Font file hash mismatch: {raw_path}")
        records.append({"path": raw_path, "sha256": actual})
    return {
        "fontconfig_file": configured_path,
        "fontconfig_config_sha256": _sha256_path(fontconfig_file),
        "font_manifest_sha256": _sha256_path(manifest_path),
        "discovered_fonts": records,
        "exact_manifest_match": True,
    }


def _discover_font_paths() -> list[str]:
    try:
        completed = subprocess.run(
            ["fc-list", "-f", "%{file}\\n"],
            capture_output=True,
            check=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EnvironmentAttestationError("Fontconfig inventory command failed") from exc
    paths = sorted(set(completed.stdout.splitlines()))
    if not paths or any(not Path(path).is_absolute() for path in paths):
        raise EnvironmentAttestationError("Fontconfig returned a malformed or empty inventory")
    return paths


def _network_is_disabled() -> bool:
    interface_root = Path("/sys/class/net")
    try:
        interfaces = {path.name for path in interface_root.iterdir()}
        states = {
            name: (interface_root / name / "operstate").read_text(encoding="utf-8").strip()
            for name in interfaces
            if (interface_root / name / "operstate").is_file()
        }
        ipv4_routes = (Path("/proc/net/route")).read_text(encoding="utf-8").splitlines()[1:]
        ipv6_routes = (Path("/proc/net/ipv6_route")).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EnvironmentAttestationError("Cannot inspect the runtime network namespace") from exc
    non_loopback_up = any(name != "lo" and state != "down" for name, state in states.items())
    non_loopback_ipv4_route = any(
        fields and fields[0] != "lo" for fields in (line.split() for line in ipv4_routes)
    )
    non_loopback_ipv6_route = any(
        fields and fields[-1] != "lo" for fields in (line.split() for line in ipv6_routes)
    )
    return (
        "lo" in interfaces
        and not non_loopback_up
        and not non_loopback_ipv4_route
        and not non_loopback_ipv6_route
    )


def _sha256_path(path: Path) -> str:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise EnvironmentAttestationError(f"Attested runtime file is unreadable: {path}") from exc
    return f"sha256:{digest}"


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not-installed"


def _libreoffice_version() -> str:
    try:
        executable = find_libreoffice()
    except RuntimeError:
        return "not-installed"

    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            check=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return completed.stdout.strip() or completed.stderr.strip() or "unknown"


def _locale_name() -> str:
    try:
        return locale.setlocale(locale.LC_ALL, None)
    except locale.Error:
        return sys.getdefaultencoding()
