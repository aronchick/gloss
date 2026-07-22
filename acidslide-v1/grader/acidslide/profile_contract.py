"""Load and hash the normative AcidSlide render/comparison profiles."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator

from acidslide.package_hash import sha256_file
from acidslide.resources import resolve_normative_schema_file

if TYPE_CHECKING:
    from pathlib import Path

TREE_DOMAIN = b"AcidSlide deterministic tree hash v1\x00"

_PROFILE_FILES = {
    "export": ("export-profile-v1.json", "export-profile.schema.json"),
    "png": ("png-profile-v1.json", "png-profile.schema.json"),
    "ssim": ("ssim-profile-v1.json", "ssim-profile.schema.json"),
}


class ProfileContractError(ValueError):
    """A normative profile is missing, invalid, or inconsistent."""


@dataclass(frozen=True)
class RenderProfiles:
    """Validated profile documents plus exact-byte content identities."""

    export: dict[str, Any]
    png: dict[str, Any]
    ssim: dict[str, Any]
    export_sha256: str
    png_sha256: str
    ssim_sha256: str

    @property
    def hashes(self) -> dict[str, str]:
        return {
            "export_profile_sha256": self.export_sha256,
            "png_profile_sha256": self.png_sha256,
            "ssim_profile_sha256": self.ssim_sha256,
        }

    def export_contract(self) -> dict[str, Any]:
        """Return the exact environment-attestation export contract projection."""
        return {
            "libreoffice_command": self.export["libreoffice_command"],
            "pdftoppm_command": self.png["pdftoppm_command"],
            "presentation_size_emu": self.export["presentation_size_emu"],
            "allowed_page_counts": self.export["allowed_page_counts"],
            "width_px": self.png["width_px"],
            "height_px": self.png["height_px"],
            "color_mode": self.png["color_mode"],
            "reference_datetime": self.export["reference_datetime"],
            "pdf_page_geometry": self.export["pdf_page_geometry"],
        }

    def scoring_export(self) -> dict[str, Any]:
        """Return the exact scoring-manifest export projection."""
        encoder = self.png["encoder"]
        return {
            "pipeline": self.export["pipeline"],
            "execution_wrapper": self.export["execution_wrapper"],
            "libreoffice_command": self.export["libreoffice_command"],
            "pdftoppm_command": self.png["pdftoppm_command"],
            "presentation_size_emu": self.export["presentation_size_emu"],
            "allowed_page_counts": self.export["allowed_page_counts"],
            "width_px": self.png["width_px"],
            "height_px": self.png["height_px"],
            "color_mode": self.png["color_mode"],
            "dimension_mismatch": "fail",
            "pdf_page_geometry": self.export["pdf_page_geometry"],
            "renderer_diagnostics": self.export["renderer_diagnostics"],
            "png_encoder": {
                "implementation": encoder["implementation"],
                "format": encoder["format"],
                "conversion": encoder["conversion"],
                "optimize": encoder["optimize"],
                "compress_level": encoder["compress_level"],
            },
        }

    def scoring_visual_comparison(self) -> dict[str, Any]:
        """Return the exact scoring-manifest SSIM projection."""
        fields = (
            "algorithm",
            "threshold",
            "dtype",
            "shape",
            "channel_axis",
            "data_range",
            "win_size",
            "gaussian_weights",
            "use_sample_covariance",
            "K1",
            "K2",
            "dimension_mismatch",
            "pixel_exact",
        )
        return {field: self.ssim[field] for field in fields}


def load_render_profiles(profile_dir: Path | None = None) -> RenderProfiles:
    """Load all three profiles and reject a missing or schema-invalid file."""
    documents: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for kind, (profile_name, schema_name) in _PROFILE_FILES.items():
        profile_path = resolve_normative_schema_file(profile_name, profile_dir)
        schema_path = resolve_normative_schema_file(schema_name, profile_dir)
        try:
            document = json.loads(profile_path.read_text(encoding="utf-8"))
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProfileContractError(
                f"Normative {kind} profile is unreadable: {profile_path}"
            ) from exc
        if not isinstance(document, dict):
            raise ProfileContractError(f"Normative {kind} profile must be an object")
        errors = sorted(
            Draft202012Validator(schema).iter_errors(document),
            key=lambda error: list(error.absolute_path),
        )
        if errors:
            location = "/".join(str(value) for value in errors[0].absolute_path) or "<root>"
            raise ProfileContractError(
                f"Normative {kind} profile is invalid at {location}: {errors[0].message}"
            )
        documents[kind] = document
        hashes[kind] = f"sha256:{sha256_file(profile_path)}"
    return RenderProfiles(
        export=documents["export"],
        png=documents["png"],
        ssim=documents["ssim"],
        export_sha256=hashes["export"],
        png_sha256=hashes["png"],
        ssim_sha256=hashes["ssim"],
    )


def deterministic_tree_sha256(path: Path) -> str:
    """Hash a release tree using the scoring-manifest v1 binary framing."""
    if not path.is_dir():
        raise FileNotFoundError(f"Required release tree is missing: {path}")
    files = sorted(
        (
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file()
            and candidate.name != ".DS_Store"
            and "__pycache__" not in candidate.parts
            and candidate.suffix != ".pyc"
        ),
        key=lambda candidate: candidate.relative_to(path).as_posix().encode("utf-8"),
    )
    if not files:
        raise ProfileContractError(f"Required release tree is empty: {path}")
    digest = hashlib.sha256(TREE_DOMAIN)
    for candidate in files:
        relative = candidate.relative_to(path).as_posix().encode("utf-8")
        digest.update(struct.pack(">I", len(relative)))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(candidate)))
    return f"sha256:{digest.hexdigest()}"


def environment_profile_hashes(schema_dir: Path | None = None) -> dict[str, str]:
    """Recompute every profile/tree hash carried by an environment attestation."""
    profiles = load_render_profiles(schema_dir)
    resolved_schema_dir = resolve_normative_schema_file("mce-profile-v1.json", schema_dir).parent
    return profiles.hashes | {
        "json_schema_bundle_sha256": deterministic_tree_sha256(resolved_schema_dir),
        "xsd_bundle_sha256": deterministic_tree_sha256(
            resolved_schema_dir / "ecma-376" / "xsd-transitional"
        ),
        "schema_root_map_sha256": _file_sha256(resolved_schema_dir / "schema-root-map-v1.json"),
        "mce_profile_sha256": _file_sha256(resolved_schema_dir / "mce-profile-v1.json"),
        "scene_graph_profile_sha256": _file_sha256(
            resolved_schema_dir / "scene-graph-profile-v1.json"
        ),
        "canonical_package_hash_profile_sha256": _file_sha256(
            resolved_schema_dir / "canonical-package-hash-v1.json"
        ),
    }


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Required normative profile is missing: {path}")
    return f"sha256:{sha256_file(path)}"
