"""Hatch hook that makes wheels self-contained in source and sdist builds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Include benchmark and schema trees from either repository or sdist layout."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        project_root = Path(self.root)
        force_include: dict[str, str] = build_data["force_include"]
        for name in ("benchmark", "schemas"):
            sdist_source = project_root / "gloss" / "data" / name
            if sdist_source.is_dir():
                continue

            repository_source = project_root.parent / name
            if not repository_source.is_dir():
                msg = f"Required Gloss package data is missing: {name}"
                raise FileNotFoundError(msg)
            force_include[str(repository_source)] = f"gloss/data/{name}"

        # The source tree keeps the public release keyring beside benchmark/.
        # A frozen release wheel mirrors it beside the packaged benchmark so
        # local signature verification does not depend on repository layout.
        packaged_keyring = project_root / "gloss" / "data" / "RELEASE_KEYS.json"
        repository_keyring = project_root.parent / "RELEASE_KEYS.json"
        if not packaged_keyring.is_file() and repository_keyring.is_file():
            force_include[str(repository_keyring)] = "gloss/data/RELEASE_KEYS.json"
