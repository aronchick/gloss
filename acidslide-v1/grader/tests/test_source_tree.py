"""Tests for deterministic grader source-tree reconstruction."""

from __future__ import annotations

import json
import os
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import pytest
import rfc8785

from acidslide.source_tree import (
    GraderSourceTreeError,
    build_grader_source_tree_manifest,
    verify_grader_source_tree,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "schemas" / "grader-source-tree-profile-v1.json"


def _source(path: Path) -> Path:
    (path / "acidslide").mkdir(parents=True)
    (path / "acidslide" / "__init__.py").write_text('"""AcidSlide."""\n', encoding="utf-8")
    script = path / "hatch_build.py"
    script.write_text("print('build')\n", encoding="utf-8")
    script.chmod(0o755)
    return path


def _manifest(source: Path, path: Path) -> tuple[Path, dict[str, Any]]:
    manifest = build_grader_source_tree_manifest(source, PROFILE)
    path.write_bytes(rfc8785.dumps(cast("Any", manifest)))
    return path, manifest


def test_directory_manifest_is_deterministic_and_verifies(tmp_path: Path) -> None:
    source = _source(tmp_path / "grader")
    manifest_path, first = _manifest(source, tmp_path / "manifest.json")

    identity = verify_grader_source_tree(source, manifest_path, PROFILE)

    assert build_grader_source_tree_manifest(source, PROFILE) == first
    assert [entry["path"] for entry in first["entries"]] == [
        "acidslide/__init__.py",
        "hatch_build.py",
    ]
    assert first["entries"][1]["executable"] is True
    assert identity.entry_count == 2
    assert identity.manifest_sha256.startswith("sha256:")
    assert identity.profile_sha256.startswith("sha256:")


@pytest.mark.parametrize("mutation", ["content", "missing", "extra", "mode"])
def test_directory_mutations_fail_closed(tmp_path: Path, mutation: str) -> None:
    source = _source(tmp_path / "grader")
    manifest_path, _ = _manifest(source, tmp_path / "manifest.json")
    target = source / "hatch_build.py"
    if mutation == "content":
        target.write_text("tampered\n", encoding="utf-8")
    elif mutation == "missing":
        target.unlink()
    elif mutation == "extra":
        (source / "unexpected.txt").write_text("extra", encoding="utf-8")
    else:
        target.chmod(0o644)

    with pytest.raises(GraderSourceTreeError, match="does not match"):
        verify_grader_source_tree(source, manifest_path, PROFILE)


def test_directory_rejects_links_non_nfc_and_empty_directories(tmp_path: Path) -> None:
    source = _source(tmp_path / "grader")
    (source / "link.py").symlink_to(source / "hatch_build.py")
    with pytest.raises(GraderSourceTreeError, match="symlink"):
        build_grader_source_tree_manifest(source, PROFILE)
    (source / "link.py").unlink()

    hard_link = source / "hard.py"
    os.link(source / "hatch_build.py", hard_link)
    with pytest.raises(GraderSourceTreeError, match="hard link"):
        build_grader_source_tree_manifest(source, PROFILE)
    hard_link.unlink()

    non_nfc = source / "e\u0301.py"
    non_nfc.write_text("pass\n", encoding="utf-8")
    with pytest.raises(GraderSourceTreeError, match="not NFC"):
        build_grader_source_tree_manifest(source, PROFILE)
    non_nfc.unlink()

    (source / "empty").mkdir()
    with pytest.raises(GraderSourceTreeError, match="empty directory"):
        build_grader_source_tree_manifest(source, PROFILE)


def test_manifest_shape_order_collision_and_canonicalization_fail_closed(tmp_path: Path) -> None:
    source = _source(tmp_path / "grader")
    manifest_path, manifest = _manifest(source, tmp_path / "manifest.json")
    reversed_manifest = dict(manifest)
    reversed_manifest["entries"] = list(reversed(manifest["entries"]))
    manifest_path.write_bytes(rfc8785.dumps(cast("Any", reversed_manifest)))
    with pytest.raises(GraderSourceTreeError, match="code-point sorted"):
        verify_grader_source_tree(source, manifest_path, PROFILE)

    collision = dict(manifest)
    duplicate = dict(manifest["entries"][0])
    duplicate["path"] = duplicate["path"].upper()
    collision["entries"] = sorted([*manifest["entries"], duplicate], key=lambda item: item["path"])
    manifest_path.write_bytes(rfc8785.dumps(cast("Any", collision)))
    with pytest.raises(GraderSourceTreeError, match="path collision"):
        verify_grader_source_tree(source, manifest_path, PROFILE)

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with pytest.raises(GraderSourceTreeError, match="not RFC 8785"):
        verify_grader_source_tree(source, manifest_path, PROFILE)


def test_profile_identity_and_manifest_profile_binding_fail_closed(tmp_path: Path) -> None:
    source = _source(tmp_path / "grader")
    manifest_path, manifest = _manifest(source, tmp_path / "manifest.json")
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["profile_id"] = "wrong"
    wrong_profile = tmp_path / "profile.json"
    wrong_profile.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(GraderSourceTreeError, match="profile identity"):
        verify_grader_source_tree(source, manifest_path, wrong_profile)

    manifest["source_tree_profile_sha256"] = f"sha256:{'0' * 64}"
    manifest_path.write_bytes(rfc8785.dumps(cast("Any", manifest)))
    with pytest.raises(GraderSourceTreeError, match="bound to another profile"):
        verify_grader_source_tree(source, manifest_path, PROFILE)


def test_release_tar_reconstructs_the_same_manifest(tmp_path: Path) -> None:
    source = _source(tmp_path / "grader")
    manifest_path, _ = _manifest(source, tmp_path / "manifest.json")
    archive = tmp_path / "grader-source-tree.tar"
    with tarfile.open(archive, "w") as package:
        package.add(source, arcname="acidslide-v1/grader", recursive=True)

    identity = verify_grader_source_tree(archive, manifest_path, PROFILE)

    assert identity.entry_count == 2


@pytest.mark.parametrize("kind", ["outside", "link", "extra"])
def test_release_tar_unsafe_or_extra_members_fail_closed(tmp_path: Path, kind: str) -> None:
    source = _source(tmp_path / "grader")
    manifest_path, _ = _manifest(source, tmp_path / "manifest.json")
    archive = tmp_path / "grader-source-tree.tar"
    with tarfile.open(archive, "w") as package:
        package.add(source, arcname="acidslide-v1/grader", recursive=True)
        member = tarfile.TarInfo(
            "outside.txt"
            if kind == "outside"
            else f"acidslide-v1/grader/{'link.py' if kind == 'link' else 'extra.py'}"
        )
        if kind == "link":
            member.type = tarfile.SYMTYPE
            member.linkname = "hatch_build.py"
            package.addfile(member)
        else:
            payload = b"extra"
            member.size = len(payload)
            package.addfile(member, BytesIO(payload))

    expected = "outside its root" if kind == "outside" else "link|extra file"
    with pytest.raises(GraderSourceTreeError, match=expected):
        verify_grader_source_tree(archive, manifest_path, PROFILE)
