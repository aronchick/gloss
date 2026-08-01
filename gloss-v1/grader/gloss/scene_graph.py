"""Normative, deterministic scene-graph extraction from MCE-resolved PPTX packages."""

from __future__ import annotations

import hashlib
import json
import posixpath
import unicodedata
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

import rfc8785
from lxml import etree

from gloss.mce import MC_NAMESPACE
from gloss.package_hash import sha256_file
from gloss.resources import resolve_normative_schema_file

PRESENTATION = "ppt/presentation.xml"
PRESENTATION_RELS = "ppt/_rels/presentation.xml.rels"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


class SceneGraphError(ValueError):
    """The package cannot be represented under the frozen scene-graph profile."""


@dataclass(frozen=True)
class Relationship:
    relationship_id: str
    relationship_type: str
    target: str

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.relationship_id,
            "type": self.relationship_type,
            "target_mode": "Internal",
            "target": f"/{self.target}",
        }


def canonical_scene_graph_bytes(scene_graph: dict[str, Any]) -> bytes:
    """Return the one fixture serialization frozen by the normative profile."""
    return rfc8785.dumps(scene_graph)


def extract_normative_scene_graph(
    resolved_package: Path,
    *,
    profile_path: Path | None = None,
    selected_slides: set[int] | None = None,
) -> dict[str, Any]:
    """Extract one schema-shaped graph from an already MCE-resolved package.

    The function deliberately does not run MCE preprocessing. Any remaining MCE
    element or attribute proves that the caller supplied the wrong package state
    and is rejected before structural evidence is emitted.
    """
    resolved_profile, profile = _load_profile(profile_path)
    parts = _read_parts(resolved_package)
    _assert_mce_resolved(parts)
    relationships = _relationship_graph(parts)
    presentation = _parse_xml(_required_part(parts, PRESENTATION), PRESENTATION)
    if presentation.tag != f"{{{P_NS}}}presentation":
        raise SceneGraphError(f"Unexpected presentation root: {presentation.tag!r}")
    slide_parts = _ordered_slide_parts(presentation, relationships)
    allowed_counts = profile["input_contract"]["allowed_slide_counts"]
    if len(slide_parts) not in allowed_counts:
        raise SceneGraphError(
            f"Scene-graph profile permits slide counts {allowed_counts}; found {len(slide_parts)}"
        )
    selected = set(range(1, len(slide_parts) + 1)) if selected_slides is None else selected_slides
    if not selected or any(number < 1 or number > len(slide_parts) for number in selected):
        raise SceneGraphError("Selected slide numbers are outside the resolved presentation")
    slide_size = _slide_size(presentation)
    slides = [
        _extract_slide(number, part, parts, relationships)
        for number, part in enumerate(slide_parts, 1)
        if number in selected
    ]
    return {
        "schema_version": "1.0",
        "profile_sha256": f"sha256:{sha256_file(resolved_profile)}",
        "mce_resolved_package_sha256": f"sha256:{sha256_file(resolved_package)}",
        "units": "EMU",
        "slide_size": slide_size,
        "slides": slides,
        "gold_ooxml_is_oracle": False,
    }


def per_slide_scene_graphs(deck_graph: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Split a deck graph into independently schema-valid per-slide documents."""
    slides = deck_graph.get("slides")
    if not isinstance(slides, list):
        raise SceneGraphError("Scene graph has no slide array")
    result: dict[int, dict[str, Any]] = {}
    for slide in slides:
        if not isinstance(slide, dict) or not isinstance(slide.get("slide"), int):
            raise SceneGraphError("Scene graph contains a malformed slide record")
        number = int(slide["slide"])
        if number in result:
            raise SceneGraphError(f"Scene graph contains duplicate slide {number}")
        result[number] = dict(deck_graph) | {"slides": [slide]}
    return result


def _load_profile(explicit: Path | None) -> tuple[Path, dict[str, Any]]:
    path = resolve_normative_schema_file("scene-graph-profile-v1.json", explicit)
    try:
        profile: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SceneGraphError(f"Scene-graph profile is unreadable: {path}") from exc
    if profile.get("profile_id") != "gloss-scene-graph-profile-v1":
        raise SceneGraphError(f"Unsupported scene-graph profile: {path}")
    return path, profile


def _read_parts(package_path: Path) -> dict[str, bytes]:
    parts: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(package_path) as package:
            for info in package.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                _validate_part_name(name)
                if name in parts:
                    raise SceneGraphError(f"Duplicate ZIP part name: {name}")
                if info.flag_bits & 0x1:
                    raise SceneGraphError(f"Encrypted ZIP part is prohibited: {name}")
                parts[name] = package.read(info)
    except (OSError, zipfile.BadZipFile) as exc:
        raise SceneGraphError("Resolved package is not a readable ZIP archive") from exc
    if not parts:
        raise SceneGraphError("Resolved package contains no parts")
    return parts


def _validate_part_name(name: str) -> None:
    if not name or name.startswith("/") or "\\" in name or "\x00" in name:
        raise SceneGraphError(f"Unsafe OPC part name: {name!r}")
    if unicodedata.normalize("NFC", name) != name:
        raise SceneGraphError(f"Non-NFC OPC part name: {name!r}")
    if any(part in {"", ".", ".."} for part in PurePosixPath(name).parts):
        raise SceneGraphError(f"Unsafe OPC part name: {name!r}")


def _required_part(parts: dict[str, bytes], name: str) -> bytes:
    try:
        return parts[name]
    except KeyError as exc:
        raise SceneGraphError(f"Required OPC part is missing: /{name}") from exc


def _parse_xml(content: bytes, part_name: str) -> etree._Element:
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
        raise SceneGraphError(f"Malformed XML part: /{part_name}") from exc


def _assert_mce_resolved(parts: dict[str, bytes]) -> None:
    for name in sorted(parts):
        if not name.startswith("ppt/") or not name.endswith(".xml"):
            continue
        root = _parse_xml(parts[name], name)
        for element in root.iter():
            if _namespace(str(element.tag)) == MC_NAMESPACE:
                raise SceneGraphError(f"Unresolved MCE element remains in /{name}: {element.tag}")
            for attribute in element.attrib:
                if _namespace(str(attribute)) == MC_NAMESPACE:
                    raise SceneGraphError(
                        f"Unresolved MCE attribute remains in /{name}: {attribute!r}"
                    )


def _relationship_graph(parts: dict[str, bytes]) -> dict[str, list[Relationship]]:
    graph: dict[str, list[Relationship]] = {}
    for rels_name in sorted(name for name in parts if name.endswith(".rels")):
        source = _source_for_relationship_part(rels_name)
        if source in graph:
            raise SceneGraphError(f"More than one relationship part exists for /{source}")
        root = _parse_xml(parts[rels_name], rels_name)
        if root.tag != f"{{{REL_NS}}}Relationships":
            raise SceneGraphError(f"Unexpected relationship root in /{rels_name}")
        records: list[Relationship] = []
        identifiers: set[str] = set()
        for child in root:
            if child.tag != f"{{{REL_NS}}}Relationship":
                raise SceneGraphError(f"Unexpected relationship element in /{rels_name}")
            relationship_id = child.get("Id", "")
            relationship_type = child.get("Type", "")
            target = child.get("Target", "")
            if not relationship_id or relationship_id in identifiers:
                raise SceneGraphError(f"Duplicate or missing relationship ID in /{rels_name}")
            if not relationship_type or not urlsplit(relationship_type).scheme:
                raise SceneGraphError(f"Malformed relationship type in /{rels_name}")
            if child.get("TargetMode", "Internal") != "Internal":
                raise SceneGraphError(f"External relationship is prohibited in /{rels_name}")
            resolved_target = _resolve_relationship_target(source, target)
            if resolved_target not in parts:
                raise SceneGraphError(
                    f"Dangling relationship target: /{rels_name} -> /{resolved_target}"
                )
            identifiers.add(relationship_id)
            records.append(Relationship(relationship_id, relationship_type, resolved_target))
        graph[source] = sorted(records, key=lambda item: item.relationship_id)
    _required_part(parts, PRESENTATION_RELS)
    return graph


def _source_for_relationship_part(name: str) -> str:
    if name == "_rels/.rels":
        return ""
    directory, filename = posixpath.split(name)
    if posixpath.basename(directory) != "_rels" or not filename.endswith(".rels"):
        raise SceneGraphError(f"Malformed relationship part name: /{name}")
    source_directory = posixpath.dirname(directory)
    source_name = filename[: -len(".rels")]
    source = posixpath.join(source_directory, source_name)
    _validate_part_name(source)
    return source


def _resolve_relationship_target(source: str, target: str) -> str:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not parsed.path:
        raise SceneGraphError(f"Unsupported OPC relationship target URI: {target!r}")
    try:
        decoded = unquote(parsed.path, errors="strict")
    except UnicodeDecodeError as exc:
        raise SceneGraphError(
            f"Invalid percent encoding in relationship target: {target!r}"
        ) from exc
    candidate = (
        posixpath.normpath(decoded.lstrip("/"))
        if decoded.startswith("/")
        else posixpath.normpath(posixpath.join(posixpath.dirname(source), decoded))
    )
    _validate_part_name(candidate)
    return candidate


def _ordered_slide_parts(
    presentation: etree._Element,
    relationship_graph: dict[str, list[Relationship]],
) -> list[str]:
    by_id = {item.relationship_id: item for item in relationship_graph.get(PRESENTATION, [])}
    slide_parts: list[str] = []
    seen: set[str] = set()
    for slide_id in presentation.iter(f"{{{P_NS}}}sldId"):
        relationship_id = slide_id.get(f"{{{R_NS}}}id", "")
        relationship = by_id.get(relationship_id)
        if relationship is None or not relationship.relationship_type.endswith("/slide"):
            raise SceneGraphError(
                f"Presentation slide ID has no slide relationship: {relationship_id!r}"
            )
        if relationship.target in seen:
            raise SceneGraphError(
                f"Presentation references a slide part twice: /{relationship.target}"
            )
        seen.add(relationship.target)
        slide_parts.append(relationship.target)
    if not slide_parts:
        raise SceneGraphError("Presentation contains no ordered slide IDs")
    return slide_parts


def _slide_size(presentation: etree._Element) -> dict[str, int]:
    size = presentation.find(f"{{{P_NS}}}sldSz")
    if size is None:
        raise SceneGraphError("Presentation has no p:sldSz")
    width = _required_integer(size, "cx", minimum=1)
    height = _required_integer(size, "cy", minimum=1)
    return {"width": width, "height": height}


def _extract_slide(
    slide_number: int,
    part_name: str,
    parts: dict[str, bytes],
    relationship_graph: dict[str, list[Relationship]],
) -> dict[str, Any]:
    slide = _parse_xml(_required_part(parts, part_name), part_name)
    if slide.tag != f"{{{P_NS}}}sld":
        raise SceneGraphError(f"Unexpected slide root in /{part_name}: {slide.tag!r}")
    slide_relationships = relationship_graph.get(part_name, [])
    layout = _one_relationship(slide_relationships, "/slideLayout", part_name)
    layout_relationships = relationship_graph.get(layout.target, [])
    master = _one_relationship(layout_relationships, "/slideMaster", layout.target)
    common = slide.find(f"{{{P_NS}}}cSld")
    shape_tree = common.find(f"{{{P_NS}}}spTree") if common is not None else None
    if shape_tree is None:
        raise SceneGraphError(f"Slide has no p:cSld/p:spTree: /{part_name}")
    relationship_by_id = {item.relationship_id: item for item in slide_relationships}
    nodes = _extract_nodes(
        shape_tree,
        slide_number,
        part_name,
        relationship_by_id,
        parts,
        parent_ids=(),
        structural_prefix=(),
        locator_prefix="/p:sld/p:cSld/p:spTree",
    )
    return {
        "slide": slide_number,
        "part_name": f"/{part_name}",
        "layout_part": f"/{layout.target}",
        "master_part": f"/{master.target}",
        "nodes": nodes,
        "relationships": [item.as_dict() for item in slide_relationships],
    }


def _one_relationship(relationships: list[Relationship], suffix: str, source: str) -> Relationship:
    matches = [item for item in relationships if item.relationship_type.endswith(suffix)]
    if len(matches) != 1:
        raise SceneGraphError(
            f"/{source} must have exactly one {suffix.removeprefix('/')} relationship"
        )
    return matches[0]


def _extract_nodes(
    shape_tree: etree._Element,
    slide_number: int,
    source_part: str,
    relationships: dict[str, Relationship],
    parts: dict[str, bytes],
    *,
    parent_ids: tuple[str, ...],
    structural_prefix: tuple[int, ...],
    locator_prefix: str,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    occurrences: dict[str, int] = {}
    supported = {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}
    for child in shape_tree:
        local_name = etree.QName(child).localname
        if local_name not in supported:
            continue
        occurrences[local_name] = occurrences.get(local_name, 0) + 1
        structural_path = structural_prefix + (len(nodes),)
        node_id = f"s{slide_number}:n" + ".".join(str(value) for value in structural_path)
        locator = f"{locator_prefix}/p:{local_name}[{occurrences[local_name]}]"
        nodes.append(
            _extract_node(
                child,
                node_id,
                len(nodes),
                slide_number,
                source_part,
                locator,
                relationships,
                parts,
                parent_ids=parent_ids,
                structural_path=structural_path,
            )
        )
    return nodes


def _extract_node(
    element: etree._Element,
    node_id: str,
    z_index: int,
    slide_number: int,
    source_part: str,
    locator: str,
    relationships: dict[str, Relationship],
    parts: dict[str, bytes],
    *,
    parent_ids: tuple[str, ...],
    structural_path: tuple[int, ...],
) -> dict[str, Any]:
    source_xml_kind = etree.QName(element).localname
    text_runs = _text_runs(element)
    placeholder_type, placeholder_index = _placeholder(element)
    field_types = sorted(
        {field.get("type", "") for field in element.iter(f"{{{A_NS}}}fld") if field.get("type")}
    )
    table_dimensions = _table_dimensions(element)
    chart_type, chart_summary = _chart_properties(element, relationships, parts)
    asset_sha256 = _asset_hash(element, relationships, parts)
    kind = _node_kind(
        source_xml_kind,
        element,
        text_runs,
        placeholder_type,
        field_types,
        table_dimensions,
        chart_type,
    )
    property_container = _property_container(element)
    fill = _fill(property_container)
    children: list[dict[str, Any]] = []
    if source_xml_kind == "grpSp":
        children = _extract_nodes(
            element,
            slide_number,
            source_part,
            relationships,
            parts,
            parent_ids=parent_ids + (node_id,),
            structural_prefix=structural_path,
            locator_prefix=locator,
        )
    native_properties: dict[str, Any] = {
        "source_xml_kind": source_xml_kind,
        "subtype": _subtype(
            kind,
            element,
            placeholder_type,
            chart_type,
        ),
        "parent_group_path": list(parent_ids),
        "name": _nonvisual_name(element),
        "placeholder_type": placeholder_type,
        "placeholder_index": placeholder_index,
        "table_dimensions": table_dimensions,
        "chart_type": chart_type,
        "chart_data_summary": chart_summary,
        "field_type": field_types[0] if len(field_types) == 1 else None,
        "field_types": field_types,
        "paragraph_properties": _paragraph_properties(element),
        "fill": fill,
        "stroke": _stroke(property_container),
        "opacity": _opacity(fill),
        "shadow": _has_shadow(property_container),
        "crop": _crop(element),
        "crop_to_shape": _crop_to_shape(element),
        "hyperlink_targets": _hyperlinks(element, relationships),
    }
    return {
        "node_id": node_id,
        "kind": kind,
        "source_part": f"/{source_part}",
        "source_locator": locator,
        "z_index": z_index,
        "bbox": _bbox(element),
        "rotation_degrees": _rotation(element),
        "hidden": _hidden(element),
        "text_runs": text_runs,
        "asset_sha256": asset_sha256,
        "native_properties": native_properties,
        "children": children,
    }


def _node_kind(
    source_xml_kind: str,
    element: etree._Element,
    text_runs: list[dict[str, Any]],
    placeholder_type: str | None,
    field_types: list[str],
    table_dimensions: dict[str, int] | None,
    chart_type: str | None,
) -> str:
    if source_xml_kind == "grpSp":
        return "group"
    if source_xml_kind == "cxnSp":
        return "connector"
    if table_dimensions is not None:
        return "table"
    if chart_type is not None:
        return "chart"
    if source_xml_kind == "pic" or any(
        etree.QName(child).localname == "blipFill" for child in element
    ):
        return "picture"
    if placeholder_type is not None:
        return "placeholder"
    if field_types:
        return "field"
    if text_runs:
        return "text"
    if source_xml_kind == "sp":
        return "shape"
    return "graphic_frame"


def _subtype(
    kind: str,
    element: etree._Element,
    placeholder_type: str | None,
    chart_type: str | None,
) -> str | None:
    if placeholder_type is not None:
        return placeholder_type
    if chart_type is not None:
        return chart_type
    geometry = element.find(f".//{{{A_NS}}}prstGeom")
    if geometry is not None and geometry.get("prst"):
        return str(geometry.get("prst"))
    if kind == "picture":
        return "embedded-raster"
    return None


def _property_container(element: etree._Element) -> etree._Element | None:
    for child in element:
        if etree.QName(child).localname in {"spPr", "grpSpPr", "xfrm"}:
            return child
    return None


def _xfrm(element: etree._Element) -> etree._Element | None:
    container = _property_container(element)
    if container is None:
        return None
    if etree.QName(container).localname == "xfrm":
        return container
    for child in container:
        if etree.QName(child).localname == "xfrm":
            return child
    return None


def _bbox(element: etree._Element) -> dict[str, int]:
    transform = _xfrm(element)
    if transform is None:
        return {"x": 0, "y": 0, "width": 0, "height": 0}
    offset = transform.find(f"{{{A_NS}}}off")
    extent = transform.find(f"{{{A_NS}}}ext")
    if offset is None or extent is None:
        return {"x": 0, "y": 0, "width": 0, "height": 0}
    return {
        "x": _required_integer(offset, "x"),
        "y": _required_integer(offset, "y"),
        "width": _required_integer(extent, "cx", minimum=0),
        "height": _required_integer(extent, "cy", minimum=0),
    }


def _rotation(element: etree._Element) -> str:
    transform = _xfrm(element)
    raw = transform.get("rot", "0") if transform is not None else "0"
    return _decimal_ratio(raw, 60_000)


def _hidden(element: etree._Element) -> bool:
    nonvisual = next(
        (child for child in element.iter() if etree.QName(child).localname == "cNvPr"),
        None,
    )
    return _boolean(nonvisual.get("hidden")) is True if nonvisual is not None else False


def _nonvisual_name(element: etree._Element) -> str:
    nonvisual = next(
        (child for child in element.iter() if etree.QName(child).localname == "cNvPr"),
        None,
    )
    return str(nonvisual.get("name", "")) if nonvisual is not None else ""


def _placeholder(element: etree._Element) -> tuple[str | None, int | None]:
    placeholder = next(iter(element.iter(f"{{{P_NS}}}ph")), None)
    if placeholder is None:
        return None, None
    placeholder_type = str(placeholder.get("type", "body"))
    raw_index = placeholder.get("idx")
    return placeholder_type, int(raw_index) if raw_index is not None else None


def _text_runs(element: etree._Element) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for paragraph in element.iter(f"{{{A_NS}}}p"):
        paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
        paragraph_rtl = (
            _boolean(paragraph_properties.get("rtl")) if paragraph_properties is not None else False
        )
        for child in paragraph:
            local_name = etree.QName(child).localname
            if local_name not in {"r", "fld", "br"}:
                continue
            run_properties = child.find(f"{{{A_NS}}}rPr")
            text_element = child.find(f"{{{A_NS}}}t")
            text = (
                "\n"
                if local_name == "br"
                else (text_element.text or "" if text_element is not None else "")
            )
            latin = run_properties.find(f"{{{A_NS}}}latin") if run_properties is not None else None
            size = run_properties.get("sz") if run_properties is not None else None
            rtl_value = (
                _boolean(run_properties.get("rtl"))
                if run_properties is not None and run_properties.get("rtl") is not None
                else paragraph_rtl
            )
            runs.append(
                {
                    "text": text,
                    "language": run_properties.get("lang") if run_properties is not None else None,
                    "rtl": bool(rtl_value),
                    "font_family": latin.get("typeface") if latin is not None else None,
                    "font_size_pt": _decimal_ratio(size, 100) if size is not None else None,
                    "bold": _boolean(run_properties.get("b"))
                    if run_properties is not None
                    else None,
                    "italic": _boolean(run_properties.get("i"))
                    if run_properties is not None
                    else None,
                }
            )
    return runs


def _paragraph_properties(element: etree._Element) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for paragraph in element.iter(f"{{{A_NS}}}p"):
        properties = paragraph.find(f"{{{A_NS}}}pPr")
        bullet: dict[str, Any] | None = None
        line_spacing: dict[str, Any] | None = None
        if properties is not None:
            for child in properties:
                local_name = etree.QName(child).localname
                if local_name in {"buNone", "buChar", "buAutoNum", "buBlip"}:
                    bullet = {
                        "kind": local_name,
                        "value": child.get("char") or child.get("type"),
                    }
                if local_name == "lnSpc" and len(child):
                    spacing = child[0]
                    line_spacing = {
                        "kind": etree.QName(spacing).localname,
                        "value": _optional_integer(spacing.get("val")),
                    }
        records.append(
            {
                "level": _optional_integer(properties.get("lvl"))
                if properties is not None
                else None,
                "rtl": bool(_boolean(properties.get("rtl"))) if properties is not None else False,
                "alignment": properties.get("algn") if properties is not None else None,
                "margin_left": _optional_integer(properties.get("marL"))
                if properties is not None
                else None,
                "indent": _optional_integer(properties.get("indent"))
                if properties is not None
                else None,
                "tab_stops": [
                    {
                        "position": _required_integer(tab, "pos"),
                        "alignment": tab.get("algn"),
                    }
                    for tab in properties.findall(f".//{{{A_NS}}}tab")
                ]
                if properties is not None
                else [],
                "bullet": bullet,
                "line_spacing": line_spacing,
            }
        )
    return records


def _table_dimensions(element: etree._Element) -> dict[str, int] | None:
    table = element.find(f".//{{{A_NS}}}tbl")
    if table is None:
        return None
    rows = table.findall(f"{{{A_NS}}}tr")
    grid = table.find(f"{{{A_NS}}}tblGrid")
    columns = grid.findall(f"{{{A_NS}}}gridCol") if grid is not None else []
    return {"rows": len(rows), "columns": len(columns)}


def _chart_properties(
    element: etree._Element,
    relationships: dict[str, Relationship],
    parts: dict[str, bytes],
) -> tuple[str | None, dict[str, int] | None]:
    chart = element.find(f".//{{{C_NS}}}chart")
    if chart is None:
        return None, None
    relationship = _bound_relationship(chart, relationships)
    chart_root = _parse_xml(_required_part(parts, relationship.target), relationship.target)
    plot_area = chart_root.find(f".//{{{C_NS}}}plotArea")
    chart_types = (
        sorted(
            {
                etree.QName(child).localname
                for child in plot_area
                if etree.QName(child).localname.endswith("Chart")
            }
        )
        if plot_area is not None
        else []
    )
    if not chart_types:
        raise SceneGraphError(
            f"Chart relationship has no supported chart type: /{relationship.target}"
        )
    return "+".join(chart_types), {
        "series_count": len(chart_root.findall(f".//{{{C_NS}}}ser")),
        "category_point_count": len(chart_root.findall(f".//{{{C_NS}}}cat//{{{C_NS}}}pt")),
        "value_point_count": len(chart_root.findall(f".//{{{C_NS}}}val//{{{C_NS}}}pt")),
    }


def _asset_hash(
    element: etree._Element,
    relationships: dict[str, Relationship],
    parts: dict[str, bytes],
) -> str | None:
    relationship_ids = {
        blip.get(f"{{{R_NS}}}embed", "")
        for blip in element.iter(f"{{{A_NS}}}blip")
        if blip.get(f"{{{R_NS}}}embed")
    }
    if not relationship_ids:
        return None
    if len(relationship_ids) != 1:
        raise SceneGraphError("One scene node references more than one embedded asset")
    relationship_id = relationship_ids.pop()
    relationship = relationships.get(relationship_id)
    if relationship is None:
        raise SceneGraphError(f"Embedded asset relationship is missing: {relationship_id}")
    return f"sha256:{hashlib.sha256(_required_part(parts, relationship.target)).hexdigest()}"


def _bound_relationship(
    element: etree._Element,
    relationships: dict[str, Relationship],
) -> Relationship:
    relationship_id = element.get(f"{{{R_NS}}}id", "")
    relationship = relationships.get(relationship_id)
    if relationship is None:
        raise SceneGraphError(f"Node relationship is missing: {relationship_id!r}")
    return relationship


def _fill(container: etree._Element | None) -> dict[str, Any]:
    if container is None:
        return {"kind": "inherited", "color": None, "alpha": None}
    for child in container:
        local_name = etree.QName(child).localname
        if local_name not in {"solidFill", "gradFill", "pattFill", "noFill", "blipFill"}:
            continue
        color = next(
            (
                {
                    "kind": etree.QName(item).localname,
                    "value": next(iter(item.attrib.values()), None),
                }
                for item in child
                if etree.QName(item).localname
                in {"srgbClr", "schemeClr", "scrgbClr", "prstClr", "sysClr"}
            ),
            None,
        )
        alpha = next(
            (item.get("val") for item in child.iter(f"{{{A_NS}}}alpha") if item.get("val")),
            None,
        )
        return {"kind": local_name, "color": color, "alpha": alpha}
    return {"kind": "inherited", "color": None, "alpha": None}


def _opacity(fill: dict[str, Any]) -> str:
    alpha = fill.get("alpha")
    return _decimal_ratio(str(alpha), 100_000) if alpha is not None else "1"


def _stroke(container: etree._Element | None) -> dict[str, Any]:
    line = container.find(f"{{{A_NS}}}ln") if container is not None else None
    if line is None:
        return {"present": False, "width_emu": None, "dash": None}
    dash = line.find(f"{{{A_NS}}}prstDash")
    return {
        "present": line.find(f"{{{A_NS}}}noFill") is None,
        "width_emu": _optional_integer(line.get("w")),
        "dash": dash.get("val") if dash is not None else None,
    }


def _has_shadow(container: etree._Element | None) -> bool:
    return container is not None and any(
        etree.QName(child).localname in {"outerShdw", "innerShdw"} for child in container.iter()
    )


def _crop(element: etree._Element) -> dict[str, int] | None:
    source = element.find(f".//{{{A_NS}}}srcRect")
    if source is None:
        return None
    return {name: _optional_integer(source.get(name)) or 0 for name in ("l", "t", "r", "b")}


def _crop_to_shape(element: etree._Element) -> bool:
    geometry = element.find(f".//{{{A_NS}}}prstGeom")
    return geometry is not None and geometry.get("prst", "rect") != "rect"


def _hyperlinks(
    element: etree._Element,
    relationships: dict[str, Relationship],
) -> list[str]:
    targets: set[str] = set()
    for hyperlink in element.iter(f"{{{A_NS}}}hlinkClick"):
        relationship_id = hyperlink.get(f"{{{R_NS}}}id")
        if relationship_id is None:
            continue
        relationship = relationships.get(relationship_id)
        if relationship is None:
            raise SceneGraphError(f"Hyperlink relationship is missing: {relationship_id}")
        targets.add(f"/{relationship.target}")
    return sorted(targets)


def _required_integer(
    element: etree._Element,
    attribute: str,
    *,
    minimum: int | None = None,
) -> int:
    raw = element.get(attribute)
    if raw is None:
        raise SceneGraphError(f"Required integer attribute is missing: {attribute}")
    try:
        value = int(raw)
    except ValueError as exc:
        raise SceneGraphError(f"Invalid integer attribute {attribute}: {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise SceneGraphError(f"Integer attribute {attribute} is below {minimum}: {value}")
    return value


def _optional_integer(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise SceneGraphError(f"Invalid integer value: {raw!r}") from exc


def _decimal_ratio(raw: str, denominator: int) -> str:
    try:
        value = Decimal(raw) / Decimal(denominator)
    except Exception as exc:
        raise SceneGraphError(f"Invalid exact decimal input: {raw!r}") from exc
    rendered = format(value, "f").rstrip("0").rstrip(".")
    return rendered if rendered not in {"", "-0"} else "0"


def _boolean(raw: str | None) -> bool | None:
    if raw is None:
        return None
    if raw in {"1", "true", "on"}:
        return True
    if raw in {"0", "false", "off"}:
        return False
    raise SceneGraphError(f"Invalid OOXML boolean value: {raw!r}")


def _namespace(qname: str) -> str:
    return qname[1 : qname.index("}")] if qname.startswith("{") else ""
