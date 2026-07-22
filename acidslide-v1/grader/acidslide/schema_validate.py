"""Stage 0.5: fail-closed ECMA-376 Transitional XSD validation."""

from __future__ import annotations

import json
import zipfile
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

from lxml import etree

from acidslide.mce import (
    MCEProfileError,
    load_understood_namespaces,
    preprocess_markup_compatibility,
)
from acidslide.models import SchemaValidationResult
from acidslide.resources import resolve_normative_schema_file, resolve_schema_dir

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

CONTENT_TYPES_PART = "[Content_Types].xml"
CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"
PRESENTATION_NAMESPACE = "http://schemas.openxmlformats.org/presentationml/2006/main"
DEFAULT_CONTENT_TYPE = f"{{{CONTENT_TYPES_NAMESPACE}}}Default"
OVERRIDE_CONTENT_TYPE = f"{{{CONTENT_TYPES_NAMESPACE}}}Override"
SLIDE_SIZE = (12192000, 6858000)


def _hardened_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
        huge_tree=False,
    )


@lru_cache(maxsize=32)
def _load_xsd(xsd_path: str) -> etree.XMLSchema:
    """Load and cache an XSD schema, surfacing configuration failures."""
    doc = etree.parse(xsd_path, parser=_hardened_parser())
    return etree.XMLSchema(doc)


def validate_schema(
    pptx_path: Path,
    schema_dir: Path | None = None,
    *,
    mce_profile_path: Path | None = None,
    root_map_path: Path | None = None,
) -> SchemaValidationResult:
    """Validate every relevant PresentationML XML part under the frozen profiles.

    A relevant part with no exact ``(content type, root QName)`` mapping makes
    validation incomplete. No namespace-only fallback or silent skip is
    permitted in an official run.
    """
    configuration_errors: list[str] = []
    violations: list[str] = []
    try:
        resolved_schema_dir = resolve_schema_dir(schema_dir)
        resolved_mce_profile = resolve_normative_schema_file(
            "mce-profile-v1.json", mce_profile_path
        )
        resolved_root_map = resolve_normative_schema_file("schema-root-map-v1.json", root_map_path)
        understood_namespaces = load_understood_namespaces(resolved_mce_profile)
        root_map = _load_root_map(resolved_root_map)
    except (FileNotFoundError, MCEProfileError, OSError, ValueError, json.JSONDecodeError) as exc:
        return SchemaValidationResult(valid=False, performed=False, violations=[str(exc)])

    relevant_parts = 0
    validated_parts = 0
    try:
        with zipfile.ZipFile(pptx_path, "r") as package:
            try:
                defaults, overrides = _content_types(package)
            except (KeyError, ValueError, etree.XMLSyntaxError) as exc:
                return SchemaValidationResult(
                    valid=False,
                    performed=False,
                    violations=[f"Invalid [Content_Types].xml: {exc}"],
                )

            parser = _hardened_parser()
            for name in package.namelist():
                if not _is_relevant_part(name):
                    continue
                relevant_parts += 1
                try:
                    original_bytes = package.read(name)
                    tree = etree.fromstring(original_bytes, parser=parser)
                    evidence: list[dict[str, str]] = []
                    preprocess_markup_compatibility(
                        tree,
                        understood_namespaces,
                        preserved_evidence=evidence,
                    )
                except etree.XMLSyntaxError as exc:
                    violations.append(f"{name}: XML syntax error — {exc}")
                    continue
                except MCEProfileError as exc:
                    violations.append(f"{name}: MCE preprocessing error — {exc}")
                    continue

                content_type = _content_type_for(name, defaults, overrides)
                if content_type is None:
                    violations.append(f"{name}: no package content type is declared")
                    continue
                key = (content_type, str(tree.tag))
                xsd_file = root_map.get(key)
                if xsd_file is None:
                    violations.append(
                        f"{name}: unmapped relevant XML part: content_type={content_type!r}, "
                        f"root={str(tree.tag)!r}"
                    )
                    continue

                xsd_path = resolved_schema_dir / xsd_file
                if not xsd_path.is_file():
                    configuration_errors.append(f"Required XSD is missing: {xsd_path}")
                    continue
                try:
                    schema = _load_xsd(str(xsd_path))
                except (OSError, etree.Error) as exc:
                    configuration_errors.append(f"Could not load {xsd_path.name}: {exc}")
                    continue

                validated_parts += 1
                if not schema.validate(tree):
                    for error in cast("Iterable[Any]", schema.error_log):
                        violations.append(f"{name}:{error.line}: {error.message}")
                if name == "ppt/presentation.xml":
                    violations.extend(_presentation_semantic_violations(tree))
    except zipfile.BadZipFile:
        violations.append("Invalid ZIP structure")
    except (OSError, etree.Error) as exc:
        violations.append(f"Schema validation error: {exc}")

    if relevant_parts == 0:
        configuration_errors.append("No relevant PresentationML XML parts were found")
    if validated_parts != relevant_parts:
        configuration_errors.append(
            f"Schema validation incomplete: validated {validated_parts} of {relevant_parts} "
            "relevant XML parts"
        )

    performed = (
        relevant_parts > 0 and validated_parts == relevant_parts and not configuration_errors
    )
    return SchemaValidationResult(
        valid=performed and not violations,
        performed=performed,
        violations=[*configuration_errors, *violations],
    )


def _load_root_map(path: Path) -> dict[tuple[str, str], str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("mapping_id") != "acidslide-schema-root-map-v1":
        raise ValueError(f"Unsupported schema/root mapping: {path}")
    mapping: dict[tuple[str, str], str] = {}
    for entry in document.get("entries", []):
        key = (entry["content_type"], entry["root_qname"])
        if key in mapping:
            raise ValueError(f"Duplicate schema/root mapping entry: {key}")
        mapping[key] = entry["xsd"]
    if not mapping:
        raise ValueError(f"Schema/root mapping has no entries: {path}")
    return mapping


def _content_types(package: zipfile.ZipFile) -> tuple[dict[str, str], dict[str, str]]:
    root = etree.fromstring(package.read(CONTENT_TYPES_PART), parser=_hardened_parser())
    if str(root.tag) != f"{{{CONTENT_TYPES_NAMESPACE}}}Types":
        raise ValueError(f"unexpected root {root.tag!r}")
    defaults: dict[str, str] = {}
    overrides: dict[str, str] = {}
    for child in root:
        if child.tag == DEFAULT_CONTENT_TYPE:
            extension = child.get("Extension")
            content_type = child.get("ContentType")
            if not extension or not content_type or extension in defaults:
                raise ValueError("duplicate or malformed Default content type")
            defaults[extension.lower()] = content_type
        elif child.tag == OVERRIDE_CONTENT_TYPE:
            part_name = child.get("PartName")
            content_type = child.get("ContentType")
            if not part_name or not part_name.startswith("/") or not content_type:
                raise ValueError("malformed Override content type")
            normalized = part_name[1:]
            if normalized in overrides:
                raise ValueError(f"duplicate Override content type for {normalized}")
            overrides[normalized] = content_type
        else:
            raise ValueError(f"unexpected child {child.tag!r}")
    return defaults, overrides


def _content_type_for(name: str, defaults: dict[str, str], overrides: dict[str, str]) -> str | None:
    if name in overrides:
        return overrides[name]
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return defaults.get(extension)


def _is_relevant_part(name: str) -> bool:
    return name.startswith("ppt/") and name.endswith(".xml") and "/_rels/" not in name


def _presentation_semantic_violations(tree: etree._Element) -> list[str]:
    """Enforce v1 presentation invariants that ECMA-376 leaves variable."""
    slide_sizes = tree.findall(f"{{{PRESENTATION_NAMESPACE}}}sldSz")
    if len(slide_sizes) != 1:
        return [f"ppt/presentation.xml: expected exactly one p:sldSz; found {len(slide_sizes)}"]
    slide_size = slide_sizes[0]
    try:
        actual = (int(slide_size.get("cx", "")), int(slide_size.get("cy", "")))
    except ValueError:
        return ["ppt/presentation.xml: p:sldSz cx/cy must be integer EMU values"]
    if actual != SLIDE_SIZE:
        return [
            "ppt/presentation.xml: p:sldSz must be exactly "
            f"cx={SLIDE_SIZE[0]}, cy={SLIDE_SIZE[1]} EMU; found cx={actual[0]}, cy={actual[1]}"
        ]
    return []
