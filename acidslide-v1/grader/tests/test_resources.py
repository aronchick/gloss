"""Tests for source, environment, and installed data lookup."""

from __future__ import annotations

import hashlib
import json
import locale
import platform
import subprocess
import sys
import zipfile
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import rfc8785
from click.testing import CliRunner
from jsonschema import Draft202012Validator
from lxml import etree
from test_models import _environment_attestation

from acidslide import environment
from acidslide import scene_graph as normative_scene_graph
from acidslide.cli import main
from acidslide.environment import environment_hash
from acidslide.resources import BenchmarkDataError, resolve_benchmark_dir, resolve_schema_dir
from acidslide.scene_graph import (
    Relationship,
    SceneGraphError,
    canonical_scene_graph_bytes,
    extract_normative_scene_graph,
    per_slide_scene_graphs,
)

if TYPE_CHECKING:
    from collections.abc import Callable


ROOT = Path(__file__).resolve().parents[2]
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _relationships(*records: tuple[str, str, str, str | None]) -> bytes:
    items = []
    for relationship_id, relationship_type, target, target_mode in records:
        mode = f' TargetMode="{target_mode}"' if target_mode is not None else ""
        items.append(
            f'<Relationship Id="{relationship_id}" Type="{relationship_type}" '
            f'Target="{target}"{mode}/>'
        )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NS}">{"".join(items)}</Relationships>'
    ).encode()


def _transform(*, x: int, y: int, width: int, height: int, rotation: int = 0) -> str:
    return (
        f'<a:xfrm rot="{rotation}"><a:off x="{x}" y="{y}"/>'
        f'<a:ext cx="{width}" cy="{height}"/></a:xfrm>'
    )


def _scene_parts() -> dict[str, bytes]:
    slide_ids = "".join(
        f'<p:sldId id="{255 + number}" r:id="rId{number}"/>' for number in range(1, 6)
    )
    presentation = (
        f'<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}">'
        f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        '<p:sldSz cx="12192000" cy="6858000"/>'
        "</p:presentation>"
    ).encode()
    presentation_relationships = _relationships(
        *[
            (
                f"rId{number}",
                f"{R_NS}/slide",
                f"slides/slide{number}.xml",
                None,
            )
            for number in range(1, 6)
        ]
    )
    rich_nodes = f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Rich placeholder" hidden="1">
          <a:hlinkClick r:id="rIdLink"/>
        </p:cNvPr><p:cNvSpPr/><p:nvPr><p:ph type="title" idx="0"/></p:nvPr></p:nvSpPr>
        <p:spPr>{_transform(x=100, y=200, width=3000, height=1400, rotation=90000)}
          <a:solidFill><a:srgbClr val="336699"><a:alpha val="50000"/></a:srgbClr></a:solidFill>
          <a:ln w="12700"><a:prstDash val="dash"/></a:ln>
          <a:effectLst><a:outerShdw/></a:effectLst><a:prstGeom prst="roundRect"/>
        </p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p>
          <a:pPr lvl="1" rtl="1" algn="ctr" marL="100" indent="-20">
            <a:lnSpc><a:spcPct val="120000"/></a:lnSpc>
            <a:buChar char="&#8226;"/><a:tabLst><a:tab pos="400" algn="l"/></a:tabLst>
          </a:pPr>
          <a:r><a:rPr lang="en-US" rtl="0" sz="2400" b="1" i="0">
            <a:latin typeface="Aptos"/>
          </a:rPr><a:t>Resolved</a:t></a:r><a:br/>
          <a:fld id="{{field-1}}" type="datetime"><a:rPr lang="en-US"/><a:t>July 18</a:t></a:fld>
        </a:p></p:txBody>
      </p:sp>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="3" name="Field"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>{_transform(x=4000, y=200, width=1000, height=500)}</p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p>
          <a:fld id="{{field-2}}" type="slidenum"><a:rPr/><a:t>1</a:t></a:fld>
        </a:p></p:txBody>
      </p:sp>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="4" name="Plain shape"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>{_transform(x=5200, y=200, width=1000, height=500)}<a:noFill/></p:spPr>
      </p:sp>
      <p:pic>
        <p:nvPicPr><p:cNvPr id="5" name="Picture"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
        <p:blipFill><a:blip r:embed="rIdImage"/>
          <a:srcRect l="100" t="200" r="300" b="400"/>
        </p:blipFill>
        <p:spPr>{_transform(x=100, y=1800, width=2000, height=1200)}
          <a:prstGeom prst="ellipse"/>
        </p:spPr>
      </p:pic>
      <p:graphicFrame>
        <p:nvGraphicFramePr><p:cNvPr id="6" name="Table"/>
          <p:cNvGraphicFramePr/><p:nvPr/>
        </p:nvGraphicFramePr>
        <p:xfrm><a:off x="2200" y="1800"/><a:ext cx="2000" cy="1200"/></p:xfrm>
        <a:graphic><a:graphicData><a:tbl><a:tblGrid>
          <a:gridCol w="1000"/><a:gridCol w="1000"/>
        </a:tblGrid>
          <a:tr h="600"/><a:tr h="600"/>
        </a:tbl></a:graphicData></a:graphic>
      </p:graphicFrame>
      <p:graphicFrame>
        <p:nvGraphicFramePr><p:cNvPr id="7" name="Chart"/>
          <p:cNvGraphicFramePr/><p:nvPr/>
        </p:nvGraphicFramePr>
        <p:xfrm><a:off x="4300" y="1800"/><a:ext cx="2000" cy="1200"/></p:xfrm>
        <a:graphic><a:graphicData><c:chart r:id="rIdChart"/></a:graphicData></a:graphic>
      </p:graphicFrame>
      <p:graphicFrame>
        <p:nvGraphicFramePr><p:cNvPr id="8" name="Other graphic"/>
          <p:cNvGraphicFramePr/><p:nvPr/>
        </p:nvGraphicFramePr>
        <p:xfrm><a:off x="6400" y="1800"/><a:ext cx="500" cy="500"/></p:xfrm>
        <a:graphic><a:graphicData/></a:graphic>
      </p:graphicFrame>
      <p:grpSp>
        <p:nvGrpSpPr><p:cNvPr id="9" name="Group"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
        <p:grpSpPr>{_transform(x=100, y=3200, width=3000, height=1200)}</p:grpSpPr>
        <p:sp>
          <p:nvSpPr><p:cNvPr id="10" name="Nested text"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
          <p:spPr>{_transform(x=0, y=0, width=1000, height=400)}</p:spPr>
          <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Nested</a:t></a:r></a:p></p:txBody>
        </p:sp>
      </p:grpSp>
      <p:cxnSp>
        <p:nvCxnSpPr><p:cNvPr id="11" name="Connector"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
        <p:spPr>{_transform(x=3300, y=3300, width=1200, height=10)}<a:ln w="100"/></p:spPr>
      </p:cxnSp>
    """

    def slide_xml(nodes: str) -> bytes:
        return (
            f'<p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:c="{C_NS}">'
            f"<p:cSld><p:spTree>{nodes}</p:spTree></p:cSld></p:sld>"
        ).encode()

    layout_type = f"{R_NS}/slideLayout"
    master_type = f"{R_NS}/slideMaster"
    parts: dict[str, bytes] = {
        "ppt/presentation.xml": presentation,
        "ppt/_rels/presentation.xml.rels": presentation_relationships,
        "ppt/slideLayouts/slideLayout1.xml": f'<p:sldLayout xmlns:p="{P_NS}"/>'.encode(),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _relationships(
            ("rIdMaster", master_type, "../slideMasters/slideMaster1.xml", None)
        ),
        "ppt/slideMasters/slideMaster1.xml": f'<p:sldMaster xmlns:p="{P_NS}"/>'.encode(),
        "ppt/slides/slide1.xml": slide_xml(rich_nodes),
        "ppt/media/image1.png": b"synthetic-image-payload",
        "ppt/charts/chart1.xml": (
            f'<c:chartSpace xmlns:c="{C_NS}"><c:chart><c:plotArea><c:barChart>'
            '<c:ser><c:cat><c:strRef><c:strCache><c:pt idx="0"/></c:strCache></c:strRef></c:cat>'
            '<c:val><c:numRef><c:numCache><c:pt idx="0"/><c:pt idx="1"/>'
            "</c:numCache></c:numRef></c:val>"
            "</c:ser></c:barChart></c:plotArea></c:chart></c:chartSpace>"
        ).encode(),
    }
    for number in range(1, 6):
        if number > 1:
            parts[f"ppt/slides/slide{number}.xml"] = slide_xml("")
        records: list[tuple[str, str, str, str | None]] = [
            ("rIdLayout", layout_type, "../slideLayouts/slideLayout1.xml", None)
        ]
        if number == 1:
            records.extend(
                [
                    ("rIdImage", f"{R_NS}/image", "../media/image1.png", None),
                    ("rIdChart", f"{R_NS}/chart", "../charts/chart1.xml", None),
                    ("rIdLink", f"{R_NS}/hyperlink", "slide2.xml", None),
                ]
            )
        parts[f"ppt/slides/_rels/slide{number}.xml.rels"] = _relationships(*records)
    return parts


def _write_scene_package(path: Path, parts: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as package:
        for name, payload in sorted(parts.items()):
            package.writestr(name, payload)
    return path


def _mutated_scene_package(
    path: Path,
    mutate: Callable[[dict[str, bytes]], None] | None = None,
) -> Path:
    parts = _scene_parts()
    if mutate is not None:
        mutate(parts)
    return _write_scene_package(path, parts)


def _benchmark(path: Path) -> Path:
    (path / "checklist").mkdir(parents=True)
    (path / "tiers").mkdir()
    return path


def test_explicit_benchmark_path_is_authoritative(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(BenchmarkDataError, match=str(missing)):
        resolve_benchmark_dir(missing)


def test_environment_benchmark_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configured = _benchmark(tmp_path / "benchmark")
    monkeypatch.setenv("ACIDSLIDE_BENCHMARK_DIR", str(configured))

    assert resolve_benchmark_dir() == configured.resolve()


def test_explicit_schema_path(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    (schema_dir / "pml.xsd").write_text("schema", encoding="utf-8")

    assert resolve_schema_dir(schema_dir) == schema_dir.resolve()


def test_environment_hash_is_stable_and_sensitive() -> None:
    first = environment_hash({"python": "3.12", "renderer": "7.6"})
    second = environment_hash({"renderer": "7.6", "python": "3.12"})
    changed = environment_hash({"python": "3.12", "renderer": "7.7"})

    assert first == second
    assert len(first) == 64
    assert first != changed


def test_environment_details_include_renderer_and_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(environment, "_libreoffice_version", lambda: "LibreOffice test")

    details = environment.environment_details()

    assert details["libreoffice"] == "LibreOffice test"
    assert details["export_width"] == 1920
    assert details["export_height"] == 1080
    assert details["dependencies"]["lxml"] != "not-installed"


def test_runtime_environment_attestation_reconstructs_binary_and_font_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    expected = _environment_attestation()
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    binaries: list[dict[str, str]] = []
    for name, filename in (
        ("fontconfig", "fc-list"),
        ("libfaketime", "libfaketime"),
        ("libreoffice", "libreoffice"),
        ("pdftoppm", "pdftoppm"),
        ("python", "python"),
    ):
        path = binary_dir / filename
        path.write_bytes(f"{filename}-executable".encode())
        binaries.append(
            {
                "name": name,
                "path": str(path),
                "sha256": f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}",
            }
        )
    expected["binary_inventory"] = binaries

    fontconfig = tmp_path / "fonts.conf"
    fontconfig.write_text("<fontconfig/>", encoding="utf-8")
    font_root = tmp_path / "fonts"
    font_file = font_root / "files" / "Test.ttf"
    font_file.parent.mkdir(parents=True)
    font_file.write_bytes(b"font-bytes")
    font_sha256 = hashlib.sha256(font_file.read_bytes()).hexdigest()
    manifest = font_root / "manifest.json"
    manifest.write_text(
        json.dumps({"files": [{"local_path": "files/Test.ttf", "sha256": font_sha256}]}),
        encoding="utf-8",
    )
    expected["font_environment"] = {
        "fontconfig_file": str(fontconfig),
        "fontconfig_config_sha256": (
            f"sha256:{hashlib.sha256(fontconfig.read_bytes()).hexdigest()}"
        ),
        "font_manifest_sha256": f"sha256:{hashlib.sha256(manifest.read_bytes()).hexdigest()}",
        "discovered_fonts": [{"path": str(font_file), "sha256": f"sha256:{font_sha256}"}],
        "exact_manifest_match": True,
    }
    for name, value in expected["process_environment"].items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("FONTCONFIG_FILE", str(fontconfig))
    monkeypatch.setattr(environment, "_platform_name", lambda: "linux/amd64")
    monkeypatch.setattr(environment, "_runtime_versions", lambda: expected["runtime_versions"])
    monkeypatch.setattr(environment, "_discover_font_paths", lambda: [str(font_file)])
    monkeypatch.setattr(environment, "_network_is_disabled", lambda: True)
    monkeypatch.setattr(environment, "_clock_fixture_is_verified", lambda: True)
    monkeypatch.setattr(environment, "_build_inputs", lambda *_args: expected["build_inputs"])
    monkeypatch.setattr(
        environment,
        "environment_profile_hashes",
        lambda *_args: expected["profile_hashes"],
    )
    source_manifest = {"candidate": "source-tree"}
    expected["grader_source_tree_sha256"] = (
        f"sha256:{hashlib.sha256(rfc8785.dumps(source_manifest)).hexdigest()}"
    )
    monkeypatch.setattr(
        environment,
        "_build_source_tree_manifest",
        lambda *_args: source_manifest,
    )

    reconstructed = environment.reconstruct_environment_attestation(
        expected,
        oci_image_digest=expected["oci_image_digest"],
        schema_path=ROOT / "schemas" / "environment-attestation.schema.json",
        font_manifest_path=manifest,
    )

    assert reconstructed == expected
    assert environment.environment_attestation_sha256(reconstructed).startswith("sha256:")

    (binary_dir / "python").write_bytes(b"tampered")
    with pytest.raises(environment.EnvironmentAttestationError, match="binary_inventory"):
        environment.reconstruct_environment_attestation(
            expected,
            oci_image_digest=expected["oci_image_digest"],
            schema_path=ROOT / "schemas" / "environment-attestation.schema.json",
            font_manifest_path=manifest,
        )


def test_attest_environment_cli_emits_hashed_jcs_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    expected = {"runtime": "verified"}
    monkeypatch.setattr(
        environment,
        "reconstruct_environment_attestation",
        lambda value, **_kwargs: value,
    )

    result = CliRunner().invoke(
        main,
        [
            "attest-environment",
            "--expected-json",
            json.dumps(expected),
            "--oci-image-digest",
            f"sha256:{'a' * 64}",
            "--font-manifest",
            str(manifest),
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["environment_attestation"] == expected
    assert envelope["environment_attestation_sha256"] == (
        f"sha256:{hashlib.sha256(rfc8785.dumps(expected)).hexdigest()}"
    )
    assert result.output.strip().encode() == rfc8785.dumps(envelope)


def test_environment_attestation_runtime_command_and_binary_guards(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    required_package_version = environment._required_package_version
    command_version = environment._command_version
    assert len(environment.environment_hash()) == 64
    invalid_expected: Any = []
    with pytest.raises(environment.EnvironmentAttestationError, match="must be an object"):
        environment.reconstruct_environment_attestation(
            invalid_expected,
            oci_image_digest=f"sha256:{'a' * 64}",
        )
    expected = _environment_attestation()
    with pytest.raises(environment.EnvironmentAttestationError, match="OCI image digest"):
        environment.reconstruct_environment_attestation(
            expected,
            oci_image_digest=f"sha256:{'f' * 64}",
            schema_path=ROOT / "schemas" / "environment-attestation.schema.json",
        )

    invalid_schema = tmp_path / "invalid-schema.json"
    invalid_schema.write_text("{", encoding="utf-8")
    with pytest.raises(environment.EnvironmentAttestationError, match="schema is unreadable"):
        environment._load_attestation_validator(invalid_schema)
    validator = environment._load_attestation_validator(
        ROOT / "schemas" / "environment-attestation.schema.json"
    )
    with pytest.raises(environment.EnvironmentAttestationError, match="is invalid"):
        environment._validate_attestation(validator, {}, "Test attestation")

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    assert environment._platform_name() == "linux/amd64"
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    assert environment._platform_name() == "linux/arm64"

    monkeypatch.setattr(environment, "find_libreoffice", lambda: Path("/usr/bin/libreoffice"))
    monkeypatch.setattr(environment, "_command_version", lambda _command: "build-1")
    monkeypatch.setattr(environment, "_required_package_version", lambda package: f"{package}-1")
    versions = environment._runtime_versions()
    assert versions["libreoffice"] == "build-1"
    assert versions["pillow"] == "Pillow-1"

    monkeypatch.setattr(environment, "_package_version", lambda _package: "not-installed")
    with pytest.raises(environment.EnvironmentAttestationError, match="not installed"):
        required_package_version("missing")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "stdout\n", "stderr\n"),
    )
    assert command_version(["tool"]) == "stdout\nstderr"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    with pytest.raises(environment.EnvironmentAttestationError, match="no build ID"):
        command_version(["tool"])
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")),
    )
    with pytest.raises(environment.EnvironmentAttestationError, match="command failed"):
        command_version(["tool"])

    executable = tmp_path / "tool"
    executable.write_bytes(b"tool")
    with pytest.raises(environment.EnvironmentAttestationError, match="inventory is missing"):
        environment._binary_inventory(None)
    with pytest.raises(environment.EnvironmentAttestationError, match="inventory is malformed"):
        environment._binary_inventory([None])
    with pytest.raises(environment.EnvironmentAttestationError, match="inventory is malformed"):
        environment._binary_inventory([{"name": 1, "path": str(executable)}])
    with pytest.raises(environment.EnvironmentAttestationError, match="is unavailable"):
        environment._binary_inventory([{"name": "tool", "path": "relative/tool"}])
    duplicate = {"name": "tool", "path": str(executable), "sha256": "ignored"}
    with pytest.raises(environment.EnvironmentAttestationError, match="Duplicate attested"):
        environment._binary_inventory([duplicate, duplicate])
    with pytest.raises(environment.EnvironmentAttestationError, match="is unreadable"):
        environment._sha256_path(tmp_path)

    monkeypatch.setattr(
        environment,
        "version",
        lambda _package: (_ for _ in ()).throw(PackageNotFoundError),
    )
    assert environment._package_version("missing") == "not-installed"


def test_environment_attestation_font_and_process_guards(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    discover_font_paths = environment._discover_font_paths
    manifest = tmp_path / "manifest.json"
    fontconfig = tmp_path / "fonts.conf"
    fontconfig.write_text("config", encoding="utf-8")
    value = {"fontconfig_file": str(fontconfig)}
    with pytest.raises(environment.EnvironmentAttestationError, match="environment is missing"):
        environment._font_environment(None, manifest)
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)
    with pytest.raises(environment.EnvironmentAttestationError, match="FONTCONFIG_FILE is not set"):
        environment._font_environment(value, manifest)
    monkeypatch.setenv("FONTCONFIG_FILE", "relative.conf")
    with pytest.raises(
        environment.EnvironmentAttestationError, match="configuration is unavailable"
    ):
        environment._font_environment(value, manifest)
    monkeypatch.setenv("FONTCONFIG_FILE", str(fontconfig))
    with pytest.raises(environment.EnvironmentAttestationError, match="does not match"):
        environment._font_environment({"fontconfig_file": "/wrong"}, manifest)
    with pytest.raises(environment.EnvironmentAttestationError, match="manifest is unreadable"):
        environment._font_environment(value, manifest)

    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(environment.EnvironmentAttestationError, match="no file inventory"):
        environment._font_environment(value, manifest)
    manifest.write_text(json.dumps({"files": [None]}), encoding="utf-8")
    with pytest.raises(environment.EnvironmentAttestationError, match="inventory is malformed"):
        environment._font_environment(value, manifest)
    manifest.write_text(
        json.dumps({"files": [{"local_path": 1, "sha256": "bad"}]}), encoding="utf-8"
    )
    with pytest.raises(environment.EnvironmentAttestationError, match="inventory is malformed"):
        environment._font_environment(value, manifest)
    manifest.write_text(
        json.dumps({"files": [{"local_path": "../font.ttf", "sha256": "bad"}]}),
        encoding="utf-8",
    )
    with pytest.raises(environment.EnvironmentAttestationError, match="Unsafe font manifest path"):
        environment._font_environment(value, manifest)

    font = tmp_path / "font.ttf"
    font.write_bytes(b"font")
    font_sha = hashlib.sha256(font.read_bytes()).hexdigest()
    record = {"local_path": "font.ttf", "sha256": font_sha}
    manifest.write_text(json.dumps({"files": [record, record]}), encoding="utf-8")
    with pytest.raises(environment.EnvironmentAttestationError, match="Duplicate font manifest"):
        environment._font_environment(value, manifest)
    manifest.write_text(json.dumps({"files": [record]}), encoding="utf-8")
    monkeypatch.setattr(environment, "_discover_font_paths", lambda: [])
    with pytest.raises(environment.EnvironmentAttestationError, match="inventory mismatch"):
        environment._font_environment(value, manifest)
    monkeypatch.setattr(environment, "_discover_font_paths", lambda: [str(font)])
    manifest.write_text(
        json.dumps({"files": [{"local_path": "font.ttf", "sha256": "0" * 64}]}),
        encoding="utf-8",
    )
    with pytest.raises(environment.EnvironmentAttestationError, match="Font file hash mismatch"):
        environment._font_environment(value, manifest)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, f"{font}\n{font}\n", ""),
    )
    assert discover_font_paths() == [str(font)]
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "relative-font\n", ""),
    )
    with pytest.raises(environment.EnvironmentAttestationError, match="malformed or empty"):
        discover_font_paths()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fc-list missing")),
    )
    with pytest.raises(environment.EnvironmentAttestationError, match="inventory command failed"):
        discover_font_paths()

    monkeypatch.setattr(
        environment,
        "find_libreoffice",
        lambda: (_ for _ in ()).throw(RuntimeError("missing")),
    )
    assert environment._libreoffice_version() == "not-installed"
    monkeypatch.setattr(environment, "find_libreoffice", lambda: Path("/usr/bin/libreoffice"))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("failed")),
    )
    assert environment._libreoffice_version() == "unavailable"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", "build-stderr"),
    )
    assert environment._libreoffice_version() == "build-stderr"
    monkeypatch.setattr(
        locale,
        "setlocale",
        lambda *_args: (_ for _ in ()).throw(locale.Error("bad locale")),
    )
    assert environment._locale_name() == sys.getdefaultencoding()


def test_libreoffice_version_handles_missing_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        environment,
        "find_libreoffice",
        lambda: (_ for _ in ()).throw(RuntimeError("missing")),
    )

    assert environment._libreoffice_version() == "not-installed"


def test_normative_scene_graph_is_schema_valid_rich_and_deterministic(tmp_path: Path) -> None:
    package = _mutated_scene_package(tmp_path / "resolved.pptx")
    schema = json.loads((ROOT / "schemas" / "scene-graph.schema.json").read_text())
    validator = Draft202012Validator(schema)

    first = extract_normative_scene_graph(package)
    second = extract_normative_scene_graph(package)
    encoded = canonical_scene_graph_bytes(first)

    validator.validate(first)
    assert encoded == canonical_scene_graph_bytes(second)
    assert encoded == rfc8785.dumps(json.loads(encoded))
    assert [slide["slide"] for slide in first["slides"]] == [1, 2, 3, 4, 5]
    assert first["slide_size"] == {"width": 12192000, "height": 6858000}
    assert first["profile_sha256"].startswith("sha256:")
    assert first["mce_resolved_package_sha256"].startswith("sha256:")

    slide = first["slides"][0]
    assert slide["part_name"] == "/ppt/slides/slide1.xml"
    assert slide["layout_part"] == "/ppt/slideLayouts/slideLayout1.xml"
    assert slide["master_part"] == "/ppt/slideMasters/slideMaster1.xml"
    assert [relationship["id"] for relationship in slide["relationships"]] == [
        "rIdChart",
        "rIdImage",
        "rIdLayout",
        "rIdLink",
    ]

    nodes = slide["nodes"]
    assert [node["node_id"] for node in nodes] == [f"s1:n{index}" for index in range(9)]
    assert [node["z_index"] for node in nodes] == list(range(9))
    assert [node["kind"] for node in nodes] == [
        "placeholder",
        "field",
        "shape",
        "picture",
        "table",
        "chart",
        "graphic_frame",
        "group",
        "connector",
    ]
    placeholder = nodes[0]
    assert placeholder["bbox"] == {"x": 100, "y": 200, "width": 3000, "height": 1400}
    assert placeholder["rotation_degrees"] == "1.5"
    assert placeholder["hidden"] is True
    assert placeholder["text_runs"][0] == {
        "text": "Resolved",
        "language": "en-US",
        "rtl": False,
        "font_family": "Aptos",
        "font_size_pt": "24",
        "bold": True,
        "italic": False,
    }
    properties = placeholder["native_properties"]
    assert properties["subtype"] == "title"
    assert properties["field_types"] == ["datetime"]
    assert properties["fill"] == {
        "kind": "solidFill",
        "color": {"kind": "srgbClr", "value": "336699"},
        "alpha": "50000",
    }
    assert properties["opacity"] == "0.5"
    assert properties["stroke"] == {"present": True, "width_emu": 12700, "dash": "dash"}
    assert properties["shadow"] is True
    assert properties["hyperlink_targets"] == ["/ppt/slides/slide2.xml"]
    paragraph = properties["paragraph_properties"][0]
    assert paragraph["bullet"] == {"kind": "buChar", "value": "•"}
    assert paragraph["line_spacing"] == {"kind": "spcPct", "value": 120000}
    assert paragraph["tab_stops"] == [{"position": 400, "alignment": "l"}]

    picture = nodes[3]
    assert picture["asset_sha256"].startswith("sha256:")
    assert picture["native_properties"]["crop"] == {"l": 100, "t": 200, "r": 300, "b": 400}
    assert picture["native_properties"]["crop_to_shape"] is True
    assert nodes[4]["native_properties"]["table_dimensions"] == {"rows": 2, "columns": 2}
    assert nodes[5]["native_properties"]["chart_type"] == "barChart"
    assert nodes[5]["native_properties"]["chart_data_summary"] == {
        "series_count": 1,
        "category_point_count": 1,
        "value_point_count": 2,
    }
    group_child = nodes[7]["children"][0]
    assert group_child["node_id"] == "s1:n7.0"
    assert group_child["native_properties"]["parent_group_path"] == ["s1:n7"]

    split = per_slide_scene_graphs(first)
    assert list(split) == [1, 2, 3, 4, 5]
    for number, fixture in split.items():
        validator.validate(fixture)
        assert fixture["slides"][0]["slide"] == number

    selected = extract_normative_scene_graph(package, selected_slides={2, 4})
    assert [slide_record["slide"] for slide_record in selected["slides"]] == [2, 4]


def test_scene_graph_cli_writes_jcs_deck_and_per_slide_outputs(tmp_path: Path) -> None:
    package = _mutated_scene_package(tmp_path / "resolved.pptx")
    output = tmp_path / "deck.json"
    slides_dir = tmp_path / "slides"

    result = CliRunner().invoke(
        main,
        [
            "scene-graph",
            str(package),
            "--output",
            str(output),
            "--slides-dir",
            str(slides_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Scene graph written" in result.output
    deck = json.loads(output.read_bytes())
    assert output.read_bytes() == rfc8785.dumps(deck)
    fixtures = sorted(slides_dir.glob("slide-*.json"))
    assert [path.name for path in fixtures] == [
        f"slide-{number:02d}.json" for number in range(1, 6)
    ]
    for path in fixtures:
        payload = json.loads(path.read_bytes())
        assert path.read_bytes() == rfc8785.dumps(payload)
        assert len(payload["slides"]) == 1

    stdout = CliRunner().invoke(main, ["scene-graph", str(package)])
    assert stdout.exit_code == 0
    assert json.loads(stdout.output)["slides"][0]["slide"] == 1


def _insert_unresolved_mce(parts: dict[str, bytes]) -> None:
    slide = parts["ppt/slides/slide1.xml"]
    slide = slide.replace(b"<p:sld ", f'<p:sld xmlns:mc="{MC_NS}" '.encode(), 1)
    parts["ppt/slides/slide1.xml"] = slide.replace(
        b"<p:cSld>", b"<mc:AlternateContent/><p:cSld>", 1
    )


def _external_relationship(parts: dict[str, bytes]) -> None:
    parts["ppt/slides/_rels/slide1.xml.rels"] = parts["ppt/slides/_rels/slide1.xml.rels"].replace(
        b'Target="../media/image1.png"',
        b'Target="https://example.test/image.png" TargetMode="External"',
    )


def _dangling_relationship(parts: dict[str, bytes]) -> None:
    del parts["ppt/media/image1.png"]


def _missing_layout(parts: dict[str, bytes]) -> None:
    parts["ppt/slides/_rels/slide1.xml.rels"] = parts["ppt/slides/_rels/slide1.xml.rels"].replace(
        b'/slideLayout"', b'/notSlideLayout"'
    )


def _missing_master(parts: dict[str, bytes]) -> None:
    parts["ppt/slideLayouts/_rels/slideLayout1.xml.rels"] = _relationships()


def _duplicate_relationship_id(parts: dict[str, bytes]) -> None:
    parts["ppt/slides/_rels/slide1.xml.rels"] = parts["ppt/slides/_rels/slide1.xml.rels"].replace(
        b'Id="rIdChart"', b'Id="rIdImage"'
    )


def _malformed_slide(parts: dict[str, bytes]) -> None:
    parts["ppt/slides/slide1.xml"] = b"<p:sld"


def _unexpected_presentation_root(parts: dict[str, bytes]) -> None:
    parts["ppt/presentation.xml"] = parts["ppt/presentation.xml"].replace(
        b"presentation", b"notPresentation"
    )


def _unsupported_slide_count(parts: dict[str, bytes]) -> None:
    parts["ppt/presentation.xml"] = parts["ppt/presentation.xml"].replace(
        b'<p:sldId id="260" r:id="rId5"/>', b""
    )


def _unresolved_mce_attribute(parts: dict[str, bytes]) -> None:
    slide = parts["ppt/slides/slide1.xml"]
    slide = slide.replace(b"<p:sld ", f'<p:sld xmlns:mc="{MC_NS}" '.encode(), 1)
    parts["ppt/slides/slide1.xml"] = slide.replace(
        b"<p:cSld>", b'<p:cSld mc:Ignorable="future">', 1
    )


def _unexpected_relationship_root(parts: dict[str, bytes]) -> None:
    parts["ppt/slides/_rels/slide1.xml.rels"] = parts["ppt/slides/_rels/slide1.xml.rels"].replace(
        b"Relationships", b"NotRelationships"
    )


def _unexpected_relationship_child(parts: dict[str, bytes]) -> None:
    parts["ppt/slides/_rels/slide1.xml.rels"] = parts["ppt/slides/_rels/slide1.xml.rels"].replace(
        b"Relationship Id=", b"NotRelationship Id=", 1
    )


def _malformed_relationship_type(parts: dict[str, bytes]) -> None:
    parts["ppt/slides/_rels/slide1.xml.rels"] = parts["ppt/slides/_rels/slide1.xml.rels"].replace(
        f'Type="{R_NS}/slideLayout"'.encode(), b'Type="slideLayout"', 1
    )


def _unexpected_slide_root(parts: dict[str, bytes]) -> None:
    parts["ppt/slides/slide1.xml"] = parts["ppt/slides/slide1.xml"].replace(b"p:sld", b"p:notSlide")


def _missing_shape_tree(parts: dict[str, bytes]) -> None:
    parts["ppt/slides/slide1.xml"] = parts["ppt/slides/slide1.xml"].replace(
        b"p:spTree", b"p:notShapeTree"
    )


def _chart_without_type(parts: dict[str, bytes]) -> None:
    parts["ppt/charts/chart1.xml"] = parts["ppt/charts/chart1.xml"].replace(b"barChart", b"barPlot")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (_insert_unresolved_mce, "Unresolved MCE element"),
        (_unresolved_mce_attribute, "Unresolved MCE attribute"),
        (_external_relationship, "External relationship is prohibited"),
        (_dangling_relationship, "Dangling relationship target"),
        (_missing_layout, "exactly one slideLayout relationship"),
        (_missing_master, "exactly one slideMaster relationship"),
        (_duplicate_relationship_id, "Duplicate or missing relationship ID"),
        (_malformed_slide, "Malformed XML part"),
        (_unexpected_presentation_root, "Unexpected presentation root"),
        (_unsupported_slide_count, "permits slide counts"),
        (_unexpected_relationship_root, "Unexpected relationship root"),
        (_unexpected_relationship_child, "Unexpected relationship element"),
        (_malformed_relationship_type, "Malformed relationship type"),
        (_unexpected_slide_root, "Unexpected slide root"),
        (_missing_shape_tree, "Slide has no"),
        (_chart_without_type, "no supported chart type"),
    ],
)
def test_scene_graph_rejects_non_normative_packages(
    tmp_path: Path,
    mutation: Callable[[dict[str, bytes]], None],
    message: str,
) -> None:
    package = _mutated_scene_package(tmp_path / "rejected.pptx", mutation)

    with pytest.raises(SceneGraphError, match=message):
        extract_normative_scene_graph(package)


def test_scene_graph_rejects_malformed_zip_invalid_selection_and_bad_profile(
    tmp_path: Path,
) -> None:
    malformed = tmp_path / "malformed.pptx"
    malformed.write_bytes(b"not-a-zip")
    with pytest.raises(SceneGraphError, match="not a readable ZIP"):
        extract_normative_scene_graph(malformed)

    package = _mutated_scene_package(tmp_path / "resolved.pptx")
    with pytest.raises(SceneGraphError, match="outside the resolved presentation"):
        extract_normative_scene_graph(package, selected_slides={0})

    profile = tmp_path / "profile.json"
    profile.write_text('{"profile_id":"invented"}', encoding="utf-8")
    with pytest.raises(SceneGraphError, match="Unsupported scene-graph profile"):
        extract_normative_scene_graph(package, profile_path=profile)

    profile.write_text("{", encoding="utf-8")
    with pytest.raises(SceneGraphError, match="profile is unreadable"):
        extract_normative_scene_graph(package, profile_path=profile)


def test_per_slide_scene_graph_rejects_malformed_records() -> None:
    with pytest.raises(SceneGraphError, match="no slide array"):
        per_slide_scene_graphs({})
    with pytest.raises(SceneGraphError, match="malformed slide record"):
        per_slide_scene_graphs({"slides": [None]})
    with pytest.raises(SceneGraphError, match="duplicate slide 1"):
        per_slide_scene_graphs({"slides": [{"slide": 1}, {"slide": 1}]})


def test_scene_graph_zip_and_part_name_guards(tmp_path: Path) -> None:
    empty = tmp_path / "empty.pptx"
    with zipfile.ZipFile(empty, "w"):
        pass
    with pytest.raises(SceneGraphError, match="contains no parts"):
        normative_scene_graph._read_parts(empty)

    directory_then_part = tmp_path / "directory.pptx"
    with zipfile.ZipFile(directory_then_part, "w") as package:
        package.writestr("directory/", b"")
        package.writestr("part.xml", b"<root/>")
    assert normative_scene_graph._read_parts(directory_then_part) == {"part.xml": b"<root/>"}

    duplicate = tmp_path / "duplicate.pptx"
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        zipfile.ZipFile(duplicate, "w") as package,
    ):
        package.writestr("part.xml", b"one")
        package.writestr("part.xml", b"two")
    with pytest.raises(SceneGraphError, match="Duplicate ZIP part name"):
        normative_scene_graph._read_parts(duplicate)

    for unsafe in ("", "/absolute.xml", "back\\slash.xml", "a/../b.xml"):
        with pytest.raises(SceneGraphError, match="Unsafe OPC part name"):
            normative_scene_graph._validate_part_name(unsafe)
    with pytest.raises(SceneGraphError, match="Non-NFC OPC part name"):
        normative_scene_graph._validate_part_name("e\N{COMBINING ACUTE ACCENT}.xml")
    with pytest.raises(SceneGraphError, match="Required OPC part is missing"):
        normative_scene_graph._required_part({}, "missing.xml")


def test_scene_graph_relationship_and_order_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    rels = _relationships(("rId1", f"{R_NS}/officeDocument", "doc.xml", None))
    assert normative_scene_graph._source_for_relationship_part("_rels/.rels") == ""
    with pytest.raises(SceneGraphError, match="Malformed relationship part name"):
        normative_scene_graph._source_for_relationship_part("wrong/place.rels")
    with pytest.raises(SceneGraphError, match="Unsupported OPC relationship target URI"):
        normative_scene_graph._resolve_relationship_target("source.xml", "https://example.test")
    with pytest.raises(SceneGraphError, match="Invalid percent encoding"):
        normative_scene_graph._resolve_relationship_target("source.xml", "%FF")

    parts = {
        "first.rels": rels,
        "second.rels": rels,
        "doc.xml": b"<root/>",
        normative_scene_graph.PRESENTATION_RELS: rels,
    }
    monkeypatch.setattr(normative_scene_graph, "_source_for_relationship_part", lambda _name: "")
    with pytest.raises(SceneGraphError, match="More than one relationship part"):
        normative_scene_graph._relationship_graph(parts)

    presentation = etree.fromstring(f'<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}"/>'.encode())
    with pytest.raises(SceneGraphError, match="no ordered slide IDs"):
        normative_scene_graph._ordered_slide_parts(presentation, {})

    presentation = etree.fromstring(
        (
            f'<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}"><p:sldIdLst>'
            '<p:sldId id="1" r:id="missing"/></p:sldIdLst></p:presentation>'
        ).encode()
    )
    with pytest.raises(SceneGraphError, match="has no slide relationship"):
        normative_scene_graph._ordered_slide_parts(presentation, {})

    duplicate = etree.fromstring(
        (
            f'<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}"><p:sldIdLst>'
            '<p:sldId id="1" r:id="one"/><p:sldId id="2" r:id="two"/>'
            "</p:sldIdLst></p:presentation>"
        ).encode()
    )
    relationship_graph = {
        normative_scene_graph.PRESENTATION: [
            Relationship("one", f"{R_NS}/slide", "ppt/slides/slide1.xml"),
            Relationship("two", f"{R_NS}/slide", "ppt/slides/slide1.xml"),
        ]
    }
    with pytest.raises(SceneGraphError, match="references a slide part twice"):
        normative_scene_graph._ordered_slide_parts(duplicate, relationship_graph)
    with pytest.raises(SceneGraphError, match="no p:sldSz"):
        normative_scene_graph._slide_size(duplicate)


def test_scene_graph_node_and_scalar_guards() -> None:
    empty = etree.fromstring(f'<p:sp xmlns:p="{P_NS}" xmlns:a="{A_NS}"/>'.encode())
    assert normative_scene_graph._subtype("picture", empty, None, None) == "embedded-raster"
    assert normative_scene_graph._property_container(empty) is None
    assert normative_scene_graph._xfrm(empty) is None
    assert normative_scene_graph._bbox(empty) == {"x": 0, "y": 0, "width": 0, "height": 0}
    assert normative_scene_graph._fill(None) == {
        "kind": "inherited",
        "color": None,
        "alpha": None,
    }

    no_transform = etree.fromstring(
        f'<p:sp xmlns:p="{P_NS}" xmlns:a="{A_NS}"><p:spPr/></p:sp>'.encode()
    )
    assert normative_scene_graph._xfrm(no_transform) is None
    incomplete_transform = etree.fromstring(
        (
            f'<p:sp xmlns:p="{P_NS}" xmlns:a="{A_NS}"><p:spPr><a:xfrm>'
            '<a:off x="0" y="0"/></a:xfrm></p:spPr></p:sp>'
        ).encode()
    )
    assert normative_scene_graph._bbox(incomplete_transform) == {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0,
    }

    two_assets = etree.fromstring(
        (
            f'<p:pic xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">'
            '<a:blip r:embed="one"/><a:blip r:embed="two"/></p:pic>'
        ).encode()
    )
    with pytest.raises(SceneGraphError, match="more than one embedded asset"):
        normative_scene_graph._asset_hash(two_assets, {}, {})
    one_asset = etree.fromstring(
        (
            f'<p:pic xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">'
            '<a:blip r:embed="missing"/></p:pic>'
        ).encode()
    )
    with pytest.raises(SceneGraphError, match="asset relationship is missing"):
        normative_scene_graph._asset_hash(one_asset, {}, {})
    chart = etree.fromstring(f'<c:chart xmlns:c="{C_NS}" xmlns:r="{R_NS}"/>'.encode())
    with pytest.raises(SceneGraphError, match="Node relationship is missing"):
        normative_scene_graph._bound_relationship(chart, {})

    hyperlinks = etree.fromstring(
        (
            f'<p:sp xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">'
            '<a:hlinkClick/><a:hlinkClick r:id="missing"/></p:sp>'
        ).encode()
    )
    with pytest.raises(SceneGraphError, match="Hyperlink relationship is missing"):
        normative_scene_graph._hyperlinks(hyperlinks, {})

    integer = etree.fromstring(b"<value/>")
    with pytest.raises(SceneGraphError, match="Required integer attribute is missing"):
        normative_scene_graph._required_integer(integer, "value")
    integer.set("value", "not-an-int")
    with pytest.raises(SceneGraphError, match="Invalid integer attribute"):
        normative_scene_graph._required_integer(integer, "value")
    integer.set("value", "-1")
    with pytest.raises(SceneGraphError, match="below 0"):
        normative_scene_graph._required_integer(integer, "value", minimum=0)
    assert normative_scene_graph._optional_integer(None) is None
    with pytest.raises(SceneGraphError, match="Invalid integer value"):
        normative_scene_graph._optional_integer("not-an-int")
    with pytest.raises(SceneGraphError, match="Invalid exact decimal input"):
        normative_scene_graph._decimal_ratio("not-a-decimal", 100)
    with pytest.raises(SceneGraphError, match="Invalid OOXML boolean value"):
        normative_scene_graph._boolean("maybe")
