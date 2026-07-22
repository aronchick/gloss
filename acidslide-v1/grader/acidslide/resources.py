"""Locate benchmark and schema data in source, Docker, and installed packages."""

from __future__ import annotations

import os
from pathlib import Path


class BenchmarkDataError(RuntimeError):
    """Raised when the grader cannot locate a usable benchmark package."""


def resolve_benchmark_dir(explicit: Path | None = None) -> Path:
    """Return the benchmark data directory, or raise with actionable context."""
    candidates = _candidates(
        explicit=explicit,
        environment_variable="ACIDSLIDE_BENCHMARK_DIR",
        packaged_name="benchmark",
        source_name="benchmark",
    )
    for candidate in candidates:
        if _is_benchmark_dir(candidate):
            return candidate.resolve()

    searched = ", ".join(str(path) for path in candidates)
    msg = (
        "AcidSlide benchmark data is unavailable. Expected checklist/ and tiers/ "
        f"under one of: {searched}"
    )
    raise BenchmarkDataError(msg)


def resolve_schema_dir(explicit: Path | None = None) -> Path:
    """Return the ECMA-376 Transitional XSD directory."""
    candidates = _candidates(
        explicit=explicit,
        environment_variable="ACIDSLIDE_SCHEMA_DIR",
        packaged_name="schemas/ecma-376/xsd-transitional",
        source_name="schemas/ecma-376/xsd-transitional",
    )
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "pml.xsd").is_file():
            return candidate.resolve()

    searched = ", ".join(str(path) for path in candidates)
    msg = f"ECMA-376 XSD schemas are unavailable; searched: {searched}"
    raise FileNotFoundError(msg)


def resolve_normative_schema_file(name: str, explicit: Path | None = None) -> Path:
    """Return one content-addressed normative schema/profile file.

    ``name`` is deliberately restricted to a basename so callers cannot turn
    package-data lookup into arbitrary path traversal.
    """
    if Path(name).name != name:
        raise ValueError(f"Normative schema name must be a basename: {name!r}")
    candidates = _candidates(
        explicit=explicit,
        environment_variable="ACIDSLIDE_SCHEMA_PROFILE_DIR",
        packaged_name="schemas",
        source_name="schemas",
    )
    for candidate in candidates:
        path = candidate if explicit is not None and candidate.is_file() else candidate / name
        if path.is_file():
            return path.resolve()

    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        f"Normative schema/profile {name!r} is unavailable; searched: {searched}"
    )


def _candidates(
    *,
    explicit: Path | None,
    environment_variable: str,
    packaged_name: str,
    source_name: str,
) -> list[Path]:
    if explicit is not None:
        return [explicit.expanduser()]

    configured = os.environ.get(environment_variable)
    if configured:
        return [Path(configured).expanduser()]

    package_dir = Path(__file__).resolve().parent
    return _deduplicate(
        [
            package_dir / "data" / packaged_name,
            package_dir.parents[1] / source_name,
            Path("/opt/acidslide") / source_name,
        ]
    )


def _is_benchmark_dir(path: Path) -> bool:
    return path.is_dir() and (path / "checklist").is_dir() and (path / "tiers").is_dir()


def _deduplicate(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.absolute())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique
