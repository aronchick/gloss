"""Deterministic construction and verification of the frozen grader source tree."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tarfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import rfc8785

_MANIFEST_FIELDS = {
    "schema_version",
    "manifest_id",
    "source_tree_profile_sha256",
    "root",
    "entries",
}
_ENTRY_FIELDS = {"path", "byte_length", "sha256", "executable"}
_LOGICAL_ROOT = "gloss-v1/grader"


class GraderSourceTreeError(RuntimeError):
    """The grader source tree cannot be trusted under the frozen v1 profile."""


@dataclass(frozen=True)
class GraderSourceTreeIdentity:
    """Content identities proven by a source-tree reconstruction."""

    manifest_sha256: str
    profile_sha256: str
    entry_count: int


def build_grader_source_tree_manifest(root: Path, profile_path: Path) -> dict[str, Any]:
    """Build the self-hash-free manifest object for a directory without writing it."""
    profile_sha256 = _load_profile(profile_path)
    entries, directories = _entries_from_directory(root)
    if not entries:
        raise GraderSourceTreeError("grader source tree contains no files")
    _validate_directory_inventory(directories, {entry["path"] for entry in entries})
    return {
        "schema_version": "1.0",
        "manifest_id": "gloss-grader-source-tree-manifest-v1",
        "source_tree_profile_sha256": profile_sha256,
        "root": _LOGICAL_ROOT,
        "entries": entries,
    }


def verify_grader_source_tree(
    source: Path,
    manifest_path: Path,
    profile_path: Path,
) -> GraderSourceTreeIdentity:
    """Reconstruct a directory or release tar and require exact manifest equality."""
    profile_sha256 = _load_profile(profile_path)
    manifest_bytes, manifest = _load_manifest(manifest_path)
    if manifest.get("source_tree_profile_sha256") != profile_sha256:
        raise GraderSourceTreeError("grader source-tree manifest is bound to another profile")
    expected_entries = _validate_manifest_entries(manifest.get("entries"))
    expected_by_path = {entry["path"]: entry for entry in expected_entries}

    if source.is_dir():
        actual_entries, directories = _entries_from_directory(source)
        _validate_directory_inventory(directories, set(expected_by_path))
    elif source.is_file():
        actual_entries = _entries_from_tar(source, expected_by_path)
    else:
        raise GraderSourceTreeError(f"grader source tree is unavailable: {source}")
    if actual_entries != expected_entries:
        raise GraderSourceTreeError("grader source tree does not match its frozen manifest")
    return GraderSourceTreeIdentity(
        manifest_sha256=f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}",
        profile_sha256=profile_sha256,
        entry_count=len(actual_entries),
    )


def _load_profile(path: Path) -> str:
    try:
        raw = path.read_bytes()
        profile = json.loads(raw)
    except OSError as exc:
        raise GraderSourceTreeError(f"grader source-tree profile is unavailable: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GraderSourceTreeError("grader source-tree profile is not valid JSON") from exc
    if not isinstance(profile, dict):
        raise GraderSourceTreeError("grader source-tree profile must be an object")
    if (
        profile.get("schema_version") != "1.0"
        or profile.get("profile_id") != "gloss-grader-source-tree-v1"
        or profile.get("root") != _LOGICAL_ROOT
        or profile.get("manifest_canonicalization") != "RFC8785-JCS"
        or profile.get("manifest_digest") != "SHA-256-lowercase-hex-prefixed"
        or profile.get("path_order") != "ascending-Unicode-code-point"
    ):
        raise GraderSourceTreeError("grader source-tree profile identity is unsupported")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _load_manifest(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
        manifest = json.loads(raw)
    except OSError as exc:
        raise GraderSourceTreeError(f"grader source-tree manifest is unavailable: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GraderSourceTreeError("grader source-tree manifest is not valid JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS:
        raise GraderSourceTreeError("grader source-tree manifest has missing or unsupported fields")
    if (
        manifest.get("schema_version") != "1.0"
        or manifest.get("manifest_id") != "gloss-grader-source-tree-manifest-v1"
        or manifest.get("root") != _LOGICAL_ROOT
    ):
        raise GraderSourceTreeError("grader source-tree manifest identity is unsupported")
    try:
        canonical = rfc8785.dumps(manifest)
    except rfc8785.CanonicalizationError as exc:
        raise GraderSourceTreeError("grader source-tree manifest cannot be canonicalized") from exc
    if raw != canonical:
        raise GraderSourceTreeError("grader source-tree manifest is not RFC 8785 canonical JSON")
    return raw, manifest


def _validate_manifest_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise GraderSourceTreeError("grader source-tree manifest has no entries")
    entries: list[dict[str, Any]] = []
    paths: list[str] = []
    casefolded: set[str] = set()
    for raw_entry in value:
        if not isinstance(raw_entry, dict) or set(raw_entry) != _ENTRY_FIELDS:
            raise GraderSourceTreeError("grader source-tree entry has invalid fields")
        path = _validate_relative_path(raw_entry.get("path"))
        byte_length = raw_entry.get("byte_length")
        digest = raw_entry.get("sha256")
        executable = raw_entry.get("executable")
        if not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length < 0:
            raise GraderSourceTreeError(f"grader source-tree byte length is invalid: {path}")
        if (
            not isinstance(digest, str)
            or len(digest) != 71
            or not digest.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in digest[7:])
        ):
            raise GraderSourceTreeError(f"grader source-tree digest is invalid: {path}")
        if not isinstance(executable, bool):
            raise GraderSourceTreeError(f"grader source-tree executable flag is invalid: {path}")
        folded = path.casefold()
        if folded in casefolded:
            raise GraderSourceTreeError(f"grader source-tree path collision: {path}")
        casefolded.add(folded)
        paths.append(path)
        entries.append(dict(raw_entry))
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise GraderSourceTreeError("grader source-tree entries are not uniquely code-point sorted")
    return entries


def _entries_from_directory(root: Path) -> tuple[list[dict[str, Any]], set[str]]:
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise GraderSourceTreeError(f"grader source root is unavailable: {root}") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise GraderSourceTreeError("grader source root must be a real directory")
    entries: list[dict[str, Any]] = []
    directories: set[str] = set()

    def visit(directory: Path, relative_parent: PurePosixPath) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise GraderSourceTreeError(
                f"grader source directory is unreadable: {directory}"
            ) from exc
        for child in children:
            relative = relative_parent / child.name
            path = _validate_relative_path(relative.as_posix())
            try:
                metadata = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise GraderSourceTreeError(f"grader source entry is unreadable: {path}") from exc
            if stat.S_ISLNK(metadata.st_mode):
                raise GraderSourceTreeError(f"grader source symlink is prohibited: {path}")
            if stat.S_ISDIR(metadata.st_mode):
                directories.add(path)
                visit(Path(child.path), relative)
            elif stat.S_ISREG(metadata.st_mode):
                entries.append(_file_entry(Path(child.path), path, metadata))
            else:
                raise GraderSourceTreeError(f"grader source special file is prohibited: {path}")

    visit(root, PurePosixPath())
    entries.sort(key=lambda entry: entry["path"])
    _validate_actual_paths(entries)
    return entries, directories


def _file_entry(path: Path, relative: str, initial: os.stat_result) -> dict[str, Any]:
    if initial.st_nlink != 1:
        raise GraderSourceTreeError(f"grader source hard link is prohibited: {relative}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise GraderSourceTreeError(f"grader source file is unreadable: {relative}") from exc
    digest = hashlib.sha256()
    byte_length = 0
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise GraderSourceTreeError(f"grader source file changed type: {relative}")
        while block := os.read(descriptor, 1024 * 1024):
            byte_length += len(block)
            digest.update(block)
        final = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        opened.st_dev != initial.st_dev
        or opened.st_ino != initial.st_ino
        or final.st_size != byte_length
        or final.st_mtime_ns != opened.st_mtime_ns
    ):
        raise GraderSourceTreeError(f"grader source file changed during hashing: {relative}")
    return {
        "path": relative,
        "byte_length": byte_length,
        "sha256": f"sha256:{digest.hexdigest()}",
        "executable": bool(opened.st_mode & 0o111),
    }


def _entries_from_tar(
    archive: Path, expected_by_path: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    directories: set[str] = set()
    root_prefix = f"{_LOGICAL_ROOT}/"
    try:
        with tarfile.open(archive, mode="r:*") as package:
            for member in package:
                member_name = _validate_archive_path(member.name)
                if member_name == _LOGICAL_ROOT and member.isdir():
                    continue
                if not member_name.startswith(root_prefix):
                    raise GraderSourceTreeError(
                        f"grader archive entry is outside its root: {member_name}"
                    )
                relative = _validate_relative_path(member_name[len(root_prefix) :])
                if member.issym() or member.islnk():
                    raise GraderSourceTreeError(f"grader archive link is prohibited: {relative}")
                if member.isdir():
                    directories.add(relative)
                    continue
                if not member.isfile():
                    raise GraderSourceTreeError(
                        f"grader archive special entry is prohibited: {relative}"
                    )
                expected = expected_by_path.get(relative)
                if expected is None:
                    raise GraderSourceTreeError(
                        f"grader archive contains an extra file: {relative}"
                    )
                if member.size != expected["byte_length"]:
                    raise GraderSourceTreeError(f"grader archive file length mismatch: {relative}")
                stream = package.extractfile(member)
                if stream is None:
                    raise GraderSourceTreeError(f"grader archive file is unreadable: {relative}")
                digest = hashlib.sha256()
                byte_length = 0
                while block := stream.read(1024 * 1024):
                    byte_length += len(block)
                    digest.update(block)
                entries.append(
                    {
                        "path": relative,
                        "byte_length": byte_length,
                        "sha256": f"sha256:{digest.hexdigest()}",
                        "executable": bool(member.mode & 0o111),
                    }
                )
    except (OSError, tarfile.TarError) as exc:
        raise GraderSourceTreeError("grader source archive is not a valid tar") from exc
    entries.sort(key=lambda entry: entry["path"])
    _validate_actual_paths(entries)
    _validate_directory_inventory(directories, set(expected_by_path))
    return entries


def _validate_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise GraderSourceTreeError("grader source path must be a nonempty string")
    if unicodedata.normalize("NFC", value) != value:
        raise GraderSourceTreeError(f"grader source path is not NFC: {value!r}")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise GraderSourceTreeError("grader source path is not UTF-8 encodable") from exc
    if (
        value.startswith("/")
        or "\\" in value
        or "\0" in value
        or "//" in value
        or any(segment in {"", ".", ".."} for segment in value.split("/"))
    ):
        raise GraderSourceTreeError(f"grader source path is unsafe: {value!r}")
    return value


def _validate_archive_path(value: str) -> str:
    path = _validate_relative_path(value.rstrip("/"))
    if value.endswith("//"):
        raise GraderSourceTreeError(f"grader archive path is unsafe: {value!r}")
    return path


def _validate_actual_paths(entries: list[dict[str, Any]]) -> None:
    paths = [entry["path"] for entry in entries]
    if len(paths) != len(set(paths)) or len(paths) != len({path.casefold() for path in paths}):
        raise GraderSourceTreeError("grader source contains duplicate or case-fold-colliding paths")


def _validate_directory_inventory(directories: set[str], file_paths: set[str]) -> None:
    for directory in directories:
        prefix = f"{directory}/"
        if not any(path.startswith(prefix) for path in file_paths):
            raise GraderSourceTreeError(
                f"grader source contains an unmanifested empty directory: {directory}"
            )
