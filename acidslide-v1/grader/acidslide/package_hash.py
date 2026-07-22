"""Normative AcidSlide v1 canonical OOXML package hashing."""

from __future__ import annotations

import hashlib
import json
import posixpath
import struct
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from lxml import etree

from acidslide.mce import load_understood_namespaces, preprocess_markup_compatibility
from acidslide.resources import resolve_normative_schema_file

CONTENT_TYPES = "[Content_Types].xml"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
RELATIONSHIPS_TYPE = "application/vnd.openxmlformats-package.relationships+xml"


class PackageHashError(ValueError):
    """The package cannot be hashed under the v1 fail-closed profile."""


class PackageHashProfileMismatchError(PackageHashError):
    """The active Stage 0.5 profiles do not match the scoring manifest."""


@dataclass(frozen=True)
class CanonicalPackageIdentity:
    """Digest plus the three normative profile identities that produced it."""

    canonical_package_sha256: str
    package_hash_profile_sha256: str
    mce_profile_sha256: str
    schema_root_map_sha256: str


@dataclass(frozen=True)
class GoldCopyDecision:
    """Result of comparing one submission with both published gold identities."""

    byte_sha256: str
    canonical_package_sha256: str
    byte_match: bool
    canonical_package_match: bool

    @property
    def reason(self) -> str | None:
        return "gold_artifact_copy" if self.byte_match or self.canonical_package_match else None


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 hex digest of ``path``."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_package_sha256(
    package_path: Path,
    profile_path: Path | None = None,
    *,
    mce_profile_path: Path | None = None,
    root_map_path: Path | None = None,
) -> str:
    """Hash uncompressed parts using the published v1 binary framing.

    ZIP entry order, compression, timestamps, comments, and other container
    metadata are excluded. Only the core-property element text explicitly
    enumerated by the profile is normalized.
    """
    return canonical_package_identity(
        package_path,
        profile_path,
        mce_profile_path=mce_profile_path,
        root_map_path=root_map_path,
    ).canonical_package_sha256


def canonical_package_identity(
    package_path: Path,
    profile_path: Path | None = None,
    *,
    mce_profile_path: Path | None = None,
    root_map_path: Path | None = None,
) -> CanonicalPackageIdentity:
    """Return the Stage 0.5-resolved package identity and profile hashes."""
    resolved_profile, profile = _load_profile(profile_path)
    resolved_mce = resolve_normative_schema_file("mce-profile-v1.json", mce_profile_path)
    resolved_root_map = resolve_normative_schema_file("schema-root-map-v1.json", root_map_path)
    understood_namespaces = load_understood_namespaces(resolved_mce)
    root_map = _load_root_map(resolved_root_map)
    domain = profile["framing"]["domain_separator_utf8"].encode("utf-8")
    hasher = hashlib.sha256(domain)
    try:
        with zipfile.ZipFile(package_path) as package:
            parts = _read_parts(package)
    except zipfile.BadZipFile as exc:
        raise PackageHashError("Invalid ZIP structure") from exc

    content_types = _parse_content_types(parts, profile)
    resolved_relationships = _validate_relationship_graph(parts, content_types, profile)
    volatile = profile["volatile_xml"]
    volatile_name = str(volatile["part_name"])
    for name in sorted(parts, key=lambda value: value.encode("utf-8")):
        content = parts[name]
        if name == volatile_name:
            content = _normalize_volatile_xml(content, volatile)
        elif name == CONTENT_TYPES:
            content = _canonicalize_content_types(content)
        elif content_types[name] == RELATIONSHIPS_TYPE:
            content = _canonicalize_relationships(
                content,
                resolved_relationships[name],
            )
        elif _is_xml_content_type(content_types[name]):
            content = _canonicalize_stage_0_5_xml(
                content,
                name,
                content_types[name],
                understood_namespaces,
                root_map,
            )
        name_bytes = name.encode("utf-8")
        hasher.update(struct.pack(">I", len(name_bytes)))
        hasher.update(name_bytes)
        hasher.update(struct.pack(">Q", len(content)))
        hasher.update(content)
    return CanonicalPackageIdentity(
        canonical_package_sha256=hasher.hexdigest(),
        package_hash_profile_sha256=sha256_file(resolved_profile),
        mce_profile_sha256=sha256_file(resolved_mce),
        schema_root_map_sha256=sha256_file(resolved_root_map),
    )


def detect_gold_copy(
    submission_path: Path,
    *,
    gold_byte_sha256: str,
    gold_canonical_package_sha256: str,
    expected_package_hash_profile_sha256: str,
    expected_mce_profile_sha256: str,
    expected_schema_root_map_sha256: str,
    profile_path: Path | None = None,
    mce_profile_path: Path | None = None,
    root_map_path: Path | None = None,
) -> GoldCopyDecision:
    """Reject an exact or repacked public-gold artifact before ranking."""
    byte_digest = sha256_file(submission_path)
    identity = canonical_package_identity(
        submission_path,
        profile_path,
        mce_profile_path=mce_profile_path,
        root_map_path=root_map_path,
    )
    expected_profiles = {
        "package-hash": _bare_sha256(expected_package_hash_profile_sha256),
        "MCE": _bare_sha256(expected_mce_profile_sha256),
        "schema/root-map": _bare_sha256(expected_schema_root_map_sha256),
    }
    actual_profiles = {
        "package-hash": identity.package_hash_profile_sha256,
        "MCE": identity.mce_profile_sha256,
        "schema/root-map": identity.schema_root_map_sha256,
    }
    mismatches = [
        name for name in expected_profiles if expected_profiles[name] != actual_profiles[name]
    ]
    if mismatches:
        raise PackageHashProfileMismatchError(
            f"Canonical package hash profile mismatch: {', '.join(mismatches)}"
        )
    package_digest = identity.canonical_package_sha256
    expected_byte = _bare_sha256(gold_byte_sha256)
    expected_package = _bare_sha256(gold_canonical_package_sha256)
    return GoldCopyDecision(
        byte_sha256=byte_digest,
        canonical_package_sha256=package_digest,
        byte_match=byte_digest == expected_byte,
        canonical_package_match=package_digest == expected_package,
    )


def _load_profile(explicit: Path | None) -> tuple[Path, dict[str, Any]]:
    path = resolve_normative_schema_file("canonical-package-hash-v1.json", explicit)
    profile: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("profile_id") != "acidslide-canonical-package-hash-v1":
        raise PackageHashError(f"Unsupported canonical package hash profile: {path}")
    return path, profile


def _read_parts(package: zipfile.ZipFile) -> dict[str, bytes]:
    parts: dict[str, bytes] = {}
    for info in package.infolist():
        if info.is_dir():
            continue
        name = info.filename
        _validate_part_name(name)
        if name in parts:
            raise PackageHashError(f"Duplicate ZIP part name: {name}")
        if info.flag_bits & 0x1:
            raise PackageHashError(f"Encrypted ZIP part is prohibited: {name}")
        parts[name] = package.read(info)
    if not parts:
        raise PackageHashError("Package contains no file parts")
    return parts


def _validate_part_name(name: str) -> None:
    if not name or "\\" in name or "\x00" in name or name.startswith("/"):
        raise PackageHashError(f"Unsafe ZIP part name: {name!r}")
    if unicodedata.normalize("NFC", name) != name:
        raise PackageHashError(f"Non-NFC ZIP part name: {name!r}")
    path = PurePosixPath(name)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise PackageHashError(f"Unsafe ZIP part name: {name!r}")


def _normalize_volatile_xml(content: bytes, profile: dict[str, Any]) -> bytes:
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
        huge_tree=False,
        remove_blank_text=False,
    )
    try:
        root = etree.fromstring(content, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise PackageHashError("docProps/core.xml is not well-formed XML") from exc
    expected_root = profile["required_root_qname"]
    if root.tag != expected_root:
        raise PackageHashError(
            f"docProps/core.xml root is {root.tag!r}; expected {expected_root!r}"
        )
    for qname in profile["strip_text_qnames"]:
        for element in root.iter(qname):
            if len(element):
                raise PackageHashError(f"Volatile core property unexpectedly has children: {qname}")
            element.text = ""
    strip_attributes = set(profile.get("strip_attribute_qnames", []))
    for element in root.iter():
        for attribute in list(element.attrib):
            if attribute in strip_attributes:
                del element.attrib[attribute]
    return etree.tostring(root, method="c14n", exclusive=False, with_comments=False)


def _parse_content_types(parts: dict[str, bytes], profile: dict[str, Any]) -> dict[str, str]:
    content = parts.get(CONTENT_TYPES)
    if content is None:
        raise PackageHashError(f"Required OPC control part is missing: {CONTENT_TYPES}")
    root = _parse_xml(content, CONTENT_TYPES)
    if root.tag != f"{{{CONTENT_TYPES_NS}}}Types":
        raise PackageHashError(f"Unexpected {CONTENT_TYPES} root: {root.tag!r}")
    defaults: dict[str, str] = {}
    overrides: dict[str, str] = {}
    for child in root:
        local = etree.QName(child).localname
        if local == "Default" and child.tag == f"{{{CONTENT_TYPES_NS}}}Default":
            extension = child.get("Extension", "").lower()
            value = child.get("ContentType", "")
            if not extension or not value or extension in defaults:
                raise PackageHashError("Duplicate or malformed Default content type")
            defaults[extension] = value
        elif local == "Override" and child.tag == f"{{{CONTENT_TYPES_NS}}}Override":
            part_name = child.get("PartName", "")
            value = child.get("ContentType", "")
            if not part_name.startswith("/") or not value:
                raise PackageHashError("Malformed Override content type")
            normalized = part_name[1:]
            _validate_part_name(normalized)
            if normalized in overrides:
                raise PackageHashError(f"Duplicate Override content type: {part_name}")
            overrides[normalized] = value
        else:
            raise PackageHashError(f"Unexpected element in {CONTENT_TYPES}: {child.tag!r}")

    accepted = set(profile["content_type_policy"]["accepted"])
    result = {CONTENT_TYPES: "application/vnd.openxmlformats-package.content-types+xml"}
    for name in parts:
        if name == CONTENT_TYPES:
            continue
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        content_type = overrides.get(name, defaults.get(extension))
        if content_type is None:
            raise PackageHashError(f"No content type is declared for part: {name}")
        if content_type not in accepted:
            raise PackageHashError(f"Unknown or prohibited content type for {name}: {content_type}")
        result[name] = content_type
    for name in overrides:
        if name not in parts:
            raise PackageHashError(f"Content type override names a missing part: {name}")
    return result


def _validate_relationship_graph(
    parts: dict[str, bytes],
    content_types: dict[str, str],
    profile: dict[str, Any],
) -> dict[str, list[tuple[str, str, str]]]:
    relationships: dict[str, list[tuple[str, str, str]]] = {}
    targets_by_source: dict[str, set[str]] = {}
    office_document_type = profile["reachability_policy"]["office_document_relationship_type"]
    office_document_targets: list[str] = []
    for name, content_type in content_types.items():
        if content_type != RELATIONSHIPS_TYPE:
            continue
        source = _source_for_relationship_part(name)
        records = _relationship_records(parts[name], name, source, parts)
        relationships[name] = records
        targets_by_source[source] = {target for _, _, target in records}
        if source == "":
            office_document_targets.extend(
                target
                for _, relationship_type, target in records
                if relationship_type == office_document_type
            )
    if "_rels/.rels" not in relationships:
        raise PackageHashError("Required root relationship part is missing: _rels/.rels")
    if len(office_document_targets) != 1:
        raise PackageHashError("Root relationships must contain exactly one officeDocument target")

    reachable = {CONTENT_TYPES, "_rels/.rels"}
    pending = [""]
    visited_sources: set[str] = set()
    while pending:
        source = pending.pop()
        if source in visited_sources:
            continue
        visited_sources.add(source)
        relationship_part = _relationship_part_for_source(source)
        if relationship_part in parts:
            reachable.add(relationship_part)
        for target in targets_by_source.get(source, set()):
            if target not in reachable:
                reachable.add(target)
                pending.append(target)
    orphaned = sorted(set(parts) - reachable)
    if orphaned:
        raise PackageHashError(f"Orphan OPC part(s): {', '.join(orphaned)}")
    return relationships


def _relationship_records(
    content: bytes,
    part_name: str,
    source: str,
    parts: dict[str, bytes],
) -> list[tuple[str, str, str]]:
    root = _parse_xml(content, part_name)
    if root.tag != f"{{{RELATIONSHIPS_NS}}}Relationships":
        raise PackageHashError(f"Unexpected relationship root in {part_name}: {root.tag!r}")
    records: list[tuple[str, str, str]] = []
    identifiers: set[str] = set()
    for child in root:
        if child.tag != f"{{{RELATIONSHIPS_NS}}}Relationship":
            raise PackageHashError(f"Unexpected relationship element in {part_name}: {child.tag!r}")
        identifier = child.get("Id", "")
        relationship_type = child.get("Type", "")
        target = child.get("Target", "")
        if not identifier or not relationship_type or not target or identifier in identifiers:
            raise PackageHashError(f"Malformed or duplicate relationship in {part_name}")
        identifiers.add(identifier)
        if child.get("TargetMode", "Internal") != "Internal":
            raise PackageHashError(f"External relationship target is prohibited in {part_name}")
        resolved = _resolve_relationship_target(source, target)
        if resolved not in parts:
            raise PackageHashError(f"Relationship target does not exist: {part_name} -> {resolved}")
        records.append((identifier, relationship_type, resolved))
    return sorted(records, key=lambda record: record[0].encode("utf-8"))


def _source_for_relationship_part(name: str) -> str:
    if name == "_rels/.rels":
        return ""
    marker = "/_rels/"
    if marker not in name or not name.endswith(".rels"):
        raise PackageHashError(f"Invalid OPC relationship part name: {name}")
    directory, filename = name.split(marker, 1)
    return f"{directory}/{filename[:-5]}"


def _relationship_part_for_source(source: str) -> str:
    if not source:
        return "_rels/.rels"
    directory, _, filename = source.rpartition("/")
    prefix = f"{directory}/" if directory else ""
    return f"{prefix}_rels/{filename}.rels"


def _resolve_relationship_target(source: str, target: str) -> str:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise PackageHashError(f"Unsupported OPC relationship target URI: {target!r}")
    decoded = unquote(parsed.path)
    if "\\" in decoded or "\x00" in decoded:
        raise PackageHashError(f"Unsafe OPC relationship target: {target!r}")
    base = posixpath.dirname(source)
    resolved = posixpath.normpath(posixpath.join(base, decoded.lstrip("/")))
    _validate_part_name(resolved)
    return resolved


def _canonicalize_content_types(content: bytes) -> bytes:
    root = _parse_xml(content, CONTENT_TYPES)
    children = list(root)
    children.sort(
        key=lambda child: (
            etree.QName(child).localname,
            child.get("Extension", "").encode("utf-8"),
            child.get("PartName", "").encode("utf-8"),
        )
    )
    root[:] = children
    return etree.tostring(root, method="c14n", exclusive=False, with_comments=False)


def _canonicalize_relationships(
    content: bytes,
    records: list[tuple[str, str, str]],
) -> bytes:
    root = _parse_xml(content, "relationship part")
    root.clear()
    for identifier, relationship_type, target in records:
        child = etree.SubElement(root, f"{{{RELATIONSHIPS_NS}}}Relationship")
        child.set("Id", identifier)
        child.set("Type", relationship_type)
        child.set("Target", f"/{target}")
    return etree.tostring(root, method="c14n", exclusive=False, with_comments=False)


def _canonicalize_stage_0_5_xml(
    content: bytes,
    name: str,
    content_type: str,
    understood_namespaces: set[str],
    root_map: set[tuple[str, str]],
) -> bytes:
    root = _parse_xml(content, name)
    if name.startswith("ppt/") and name.endswith(".xml") and "/_rels/" not in name:
        preprocess_markup_compatibility(root, understood_namespaces)
        key = (content_type, str(root.tag))
        if key not in root_map:
            raise PackageHashError(
                f"Unmapped Stage 0.5 XML part {name}: content_type={content_type!r}, "
                f"root={str(root.tag)!r}"
            )
    return etree.tostring(root, method="c14n", exclusive=False, with_comments=False)


def _parse_xml(content: bytes, name: str) -> etree._Element:
    if b"<!DOCTYPE" in content.upper():
        raise PackageHashError(f"DTD is prohibited in XML part: {name}")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
        huge_tree=False,
        remove_blank_text=False,
    )
    try:
        return etree.fromstring(content, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise PackageHashError(f"XML part is not well formed: {name}") from exc


def _is_xml_content_type(content_type: str) -> bool:
    return content_type.endswith("+xml") or content_type in {"application/xml", "text/xml"}


def _load_root_map(path: Path) -> set[tuple[str, str]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("mapping_id") != "acidslide-schema-root-map-v1":
        raise PackageHashError(f"Unsupported schema/root mapping: {path}")
    keys = {(entry["content_type"], entry["root_qname"]) for entry in document["entries"]}
    if len(keys) != len(document["entries"]):
        raise PackageHashError(f"Duplicate entries in schema/root mapping: {path}")
    return keys


def _bare_sha256(value: str) -> str:
    bare = value.removeprefix("sha256:")
    if len(bare) != 64 or any(character not in "0123456789abcdef" for character in bare):
        raise ValueError(f"Invalid SHA-256 digest: {value!r}")
    return bare
