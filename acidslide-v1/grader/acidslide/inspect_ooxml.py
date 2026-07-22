"""Stage 3: OOXML structural extraction — builds scene graph from .pptx XML."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lxml import etree

from acidslide.mce import preprocess_markup_compatibility

if TYPE_CHECKING:
    from pathlib import Path

# OOXML namespaces
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _hardened_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
        huge_tree=False,
    )


@dataclass
class TextRun:
    text: str
    font_family: str = ""
    font_size: int = 0  # in hundredths of a point
    bold: bool = False
    italic: bool = False


@dataclass
class SceneObject:
    """A single object in the slide scene graph."""

    obj_type: str  # shape, picture, table, chart, group, connector, placeholder
    name: str = ""
    z_index: int = 0
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, cx, cy in EMUs
    rotation: int = 0  # in 60,000ths of a degree
    text_runs: list[TextRun] = field(default_factory=list)
    placeholder_type: str = ""  # title, body, subtitle, slidenum, date, footer, etc.
    placeholder_idx: int | None = None
    is_table: bool = False
    table_rows: int = 0
    table_cols: int = 0
    is_chart: bool = False
    is_picture: bool = False
    chart_type: str = ""
    field_type: str = ""  # slidenum, datetime, etc.
    asset_hash: str = ""
    fill_type: str = ""  # solid, gradient, pattern, none
    has_shadow: bool = False
    opacity: float = 1.0
    children: list[SceneObject] = field(default_factory=list)
    parent_group_path: str = ""
    layout_ref: str = ""
    master_ref: str = ""

    def __post_init__(self) -> None:
        if self.obj_type == "picture":
            self.is_picture = True


@dataclass
class SlideGraph:
    """Scene graph for a single slide."""

    slide_number: int
    layout_name: str = ""
    master_name: str = ""
    layout_ref: str = ""
    objects: list[SceneObject] = field(default_factory=list)

    @property
    def object_count(self) -> int:
        return self._count_recursive(self.objects)

    def _count_recursive(self, objs: list[SceneObject]) -> int:
        count = len(objs)
        for obj in objs:
            count += self._count_recursive(obj.children)
        return count


@dataclass
class DeckGraph:
    """Scene graph for the entire deck."""

    slides: list[SlideGraph] = field(default_factory=list)
    master_names: list[str] = field(default_factory=list)
    layout_names: list[str] = field(default_factory=list)
    media_hashes: dict[str, str] = field(default_factory=dict)
    all_fonts: set[str] = field(default_factory=set)  # all typeface refs across the package
    notes_slides: set[int] = field(default_factory=set)
    comment_slides: set[int] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output / fixture comparison."""
        return {
            "slide_count": len(self.slides),
            "master_names": self.master_names,
            "layout_names": self.layout_names,
            "media_hashes": self.media_hashes,
            "notes_slides": sorted(self.notes_slides),
            "comment_slides": sorted(self.comment_slides),
            "slides": [
                {
                    "slide_number": s.slide_number,
                    "layout_name": s.layout_name,
                    "master_name": s.master_name,
                    "object_count": s.object_count,
                    "objects": [_obj_to_dict(o) for o in s.objects],
                }
                for s in self.slides
            ],
        }


def extract_deck_graph(pptx_path: Path) -> DeckGraph:
    """Extract the full scene graph from a .pptx file."""
    deck = DeckGraph()
    parser = _hardened_parser()

    with zipfile.ZipFile(pptx_path, "r") as zf:
        # Extract media hashes
        deck.media_hashes = _extract_media_hashes(zf)

        # Parse presentation.xml for slide order and master/layout info
        slide_parts = _get_slide_parts(zf, parser)

        # Extract layout and master names
        deck.layout_names = _get_layout_names(zf, parser)
        deck.master_names = _get_master_names(zf, parser)

        # Parse each slide
        for i, part_name in enumerate(slide_parts, 1):
            if part_name in zf.namelist():
                has_notes, has_comments = _related_slide_content(zf, part_name, parser)
                if has_notes:
                    deck.notes_slides.add(i)
                if has_comments:
                    deck.comment_slides.add(i)
                xml_bytes = zf.read(part_name)
                tree = etree.fromstring(xml_bytes, parser=parser)
                preprocess_markup_compatibility(tree)
                slide = _parse_slide(tree, i, zf, part_name, parser)
                deck.slides.append(slide)

        # Scan ALL XML parts for typeface references (theme, masters, layouts, slides)
        deck.all_fonts = _extract_all_fonts(zf, parser)

    return deck


def _related_slide_content(
    zf: zipfile.ZipFile,
    part_name: str,
    parser: etree.XMLParser,
) -> tuple[bool, bool]:
    """Return whether a slide relationship set contains notes or comments."""
    rels_name = part_name.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    if rels_name not in zf.namelist():
        return False, False
    rels = etree.fromstring(zf.read(rels_name), parser=parser)
    relationship_kinds = {
        rel.get("Type", "").rsplit("/", 1)[-1].lower()
        for rel in rels.iter(f"{{{NS['rel']}}}Relationship")
    }
    has_notes = "notesslide" in relationship_kinds
    has_comments = bool(
        relationship_kinds & {"comment", "comments", "moderncomment", "moderncomments"}
    )
    return has_notes, has_comments


def _extract_media_hashes(zf: zipfile.ZipFile) -> dict[str, str]:
    """Hash all media files in the .pptx."""
    hashes = {}
    for name in zf.namelist():
        if name.startswith("ppt/media/"):
            data = zf.read(name)
            hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes


def _extract_all_fonts(zf: zipfile.ZipFile, parser: etree.XMLParser) -> set[str]:
    """Scan all XML parts for typeface= attributes (slides, themes, masters, layouts)."""
    fonts: set[str] = set()
    xml_parts = [n for n in zf.namelist() if n.startswith("ppt/") and n.endswith(".xml")]
    for part in xml_parts:
        try:
            xml_bytes = zf.read(part)
            tree = etree.fromstring(xml_bytes, parser=parser)
            for elem in tree.iter():
                typeface = elem.get("typeface")
                if typeface and not typeface.startswith("+"):
                    fonts.add(typeface)
        except etree.XMLSyntaxError:
            continue
    return fonts


def _get_slide_parts(zf: zipfile.ZipFile, parser: etree.XMLParser) -> list[str]:
    """Get ordered list of slide part names from presentation.xml."""
    if "ppt/presentation.xml" not in zf.namelist():
        return []

    pres_xml = zf.read("ppt/presentation.xml")
    pres = etree.fromstring(pres_xml, parser=parser)

    # Get slide relationship IDs from sldIdLst
    slide_ids = []
    for sld_id in pres.iter(f"{{{NS['p']}}}sldId"):
        rid = sld_id.get(f"{{{NS['r']}}}id")
        if rid:
            slide_ids.append(rid)

    # Resolve rIds to part names via rels
    rels_path = "ppt/_rels/presentation.xml.rels"
    if rels_path not in zf.namelist():
        # Fallback: just find slides by name
        return sorted(
            n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")
        )

    rels_xml = zf.read(rels_path)
    rels = etree.fromstring(rels_xml, parser=parser)

    rid_to_target: dict[str, str] = {}
    for rel in rels.iter(f"{{{NS['rel']}}}Relationship"):
        rid = rel.get("Id", "")
        target = rel.get("Target", "")
        rid_to_target[rid] = f"ppt/{target}" if not target.startswith("ppt/") else target

    parts = []
    for rid in slide_ids:
        target = rid_to_target.get(rid, "")
        if target:
            parts.append(target)

    return parts


def _get_layout_names(zf: zipfile.ZipFile, parser: etree.XMLParser) -> list[str]:
    """Extract slide layout names."""
    names = []
    for name in sorted(zf.namelist()):
        if name.startswith("ppt/slideLayouts/") and name.endswith(".xml"):
            xml_bytes = zf.read(name)
            tree = etree.fromstring(xml_bytes, parser=parser)
            tree.get("name", "") or tree.get(f"{{{NS['p']}}}cSld", "")
            # Try to get the name from cSld element
            csld = tree.find(f"{{{NS['p']}}}cSld")
            layout_name = csld.get("name", name) if csld is not None else name
            names.append(layout_name)
    return names


def _get_master_names(zf: zipfile.ZipFile, parser: etree.XMLParser) -> list[str]:
    """Extract slide master names."""
    names = []
    for name in sorted(zf.namelist()):
        if name.startswith("ppt/slideMasters/") and name.endswith(".xml"):
            xml_bytes = zf.read(name)
            tree = etree.fromstring(xml_bytes, parser=parser)
            csld = tree.find(f"{{{NS['p']}}}cSld")
            master_name = csld.get("name", name) if csld is not None else name
            names.append(master_name)
    return names


def _parse_slide(
    tree: etree._Element,
    slide_number: int,
    zf: zipfile.ZipFile,
    part_name: str,
    parser: etree.XMLParser,
) -> SlideGraph:
    """Parse a slide XML tree into a SlideGraph."""
    slide = SlideGraph(slide_number=slide_number)

    # Get layout reference from rels
    rels_name = part_name.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    if rels_name in zf.namelist():
        rels_xml = zf.read(rels_name)
        rels = etree.fromstring(rels_xml, parser=parser)
        for rel in rels.iter(f"{{{NS['rel']}}}Relationship"):
            rel_type = rel.get("Type", "")
            if "slideLayout" in rel_type:
                slide.layout_ref = rel.get("Target", "")

    # Parse shape tree (spTree)
    csld = tree.find(f"{{{NS['p']}}}cSld")
    if csld is None:
        return slide

    sp_tree = csld.find(f"{{{NS['p']}}}spTree")
    if sp_tree is None:
        return slide

    slide.objects = _parse_shape_tree(sp_tree, z_start=0)
    return slide


def _parse_shape_tree(
    sp_tree: etree._Element,
    z_start: int = 0,
    parent_path: str = "",
) -> list[SceneObject]:
    """Recursively parse a shape tree into SceneObjects."""
    objects: list[SceneObject] = []
    z_index = z_start

    for child in sp_tree:
        tag = etree.QName(child.tag).localname
        obj = None

        if tag == "sp":
            obj = _parse_shape(child)
        elif tag == "pic":
            obj = _parse_picture(child)
        elif tag == "graphicFrame":
            obj = _parse_graphic_frame(child)
        elif tag == "grpSp":
            obj = _parse_group(child, parent_path)
        elif tag == "cxnSp":
            obj = _parse_connector(child)

        if obj is not None:
            obj.z_index = z_index
            obj.parent_group_path = parent_path
            objects.append(obj)
            z_index += 1

    return objects


def _parse_shape(elem: etree._Element) -> SceneObject:
    """Parse a shape (sp) element."""
    obj = SceneObject(obj_type="shape")
    obj.name = _get_nv_name(elem)
    obj.bbox = _get_bbox(elem)
    obj.rotation = _get_rotation(elem)
    obj.text_runs = _get_text_runs(elem)
    obj.placeholder_type = _get_placeholder_type(elem)
    obj.placeholder_idx = _get_placeholder_idx(elem)
    obj.fill_type = _get_fill_type(elem)
    obj.has_shadow = _has_shadow(elem)
    obj.field_type = _get_field_type(elem)
    obj.is_picture = _has_blip_fill(elem)
    return obj


def _parse_picture(elem: etree._Element) -> SceneObject:
    """Parse a picture (pic) element."""
    obj = SceneObject(obj_type="picture")
    obj.is_picture = True
    obj.name = _get_nv_name(elem)
    obj.bbox = _get_bbox(elem)
    obj.rotation = _get_rotation(elem)
    return obj


def _parse_graphic_frame(elem: etree._Element) -> SceneObject:
    """Parse a graphic frame — could be table, chart, or other."""
    obj = SceneObject(obj_type="graphicFrame")
    obj.name = _get_nv_name(elem)
    obj.bbox = _get_bbox(elem)

    # Check if it's a table
    tbl = elem.find(f".//{{{NS['a']}}}tbl")
    if tbl is not None:
        obj.obj_type = "table"
        obj.is_table = True
        rows = tbl.findall(f"{{{NS['a']}}}tr")
        obj.table_rows = len(rows)
        if rows:
            cols = rows[0].findall(f"{{{NS['a']}}}tc")
            obj.table_cols = len(cols)
        obj.text_runs = _get_text_runs(elem)
        return obj

    # Check if it's a chart
    chart_ref = elem.find(f".//{{{NS['c']}}}chart")
    if chart_ref is not None:
        obj.obj_type = "chart"
        obj.is_chart = True
        return obj

    return obj


def _parse_group(elem: etree._Element, parent_path: str) -> SceneObject:
    """Parse a group shape (grpSp)."""
    obj = SceneObject(obj_type="group")
    obj.name = _get_nv_name(elem)
    obj.bbox = _get_bbox(elem)

    group_path = f"{parent_path}/{obj.name}" if parent_path else obj.name
    # Recursively parse children
    grp_sp_tree = elem  # group children are direct children
    obj.children = _parse_shape_tree(grp_sp_tree, parent_path=group_path)
    return obj


def _parse_connector(elem: etree._Element) -> SceneObject:
    """Parse a connector shape (cxnSp)."""
    obj = SceneObject(obj_type="connector")
    obj.name = _get_nv_name(elem)
    obj.bbox = _get_bbox(elem)
    return obj


# --- Helper functions ---


def _get_nv_name(elem: etree._Element) -> str:
    """Get the non-visual name from nvSpPr/nvPicPr/etc."""
    for nv in elem:
        tag = etree.QName(nv.tag).localname
        if tag.startswith("nv") and tag.endswith("Pr"):
            cnv_pr = nv.find(f"{{{NS['p']}}}cNvPr")
            if cnv_pr is None:
                # Try without namespace
                for sub in nv:
                    if etree.QName(sub.tag).localname == "cNvPr":
                        return str(sub.get("name", ""))
            else:
                return str(cnv_pr.get("name", ""))
    return ""


def _get_bbox(
    elem: etree._Element,
) -> tuple[int, int, int, int]:
    """Extract bounding box (x, y, cx, cy) in EMUs."""
    for _xfrm_tag in ["a:xfrm", "a:off", "p:xfrm"]:
        pass

    # Find xfrm in spPr or grpSpPr
    for desc in elem.iter():
        tag = etree.QName(desc.tag).localname
        if tag == "xfrm":
            off = desc.find(f"{{{NS['a']}}}off")
            ext = desc.find(f"{{{NS['a']}}}ext")
            if off is not None and ext is not None:
                return (
                    int(off.get("x", "0")),
                    int(off.get("y", "0")),
                    int(ext.get("cx", "0")),
                    int(ext.get("cy", "0")),
                )
    return (0, 0, 0, 0)


def _get_rotation(elem: etree._Element) -> int:
    """Get rotation from xfrm/@rot in 60,000ths of a degree."""
    for desc in elem.iter():
        if etree.QName(desc.tag).localname == "xfrm":
            rot = desc.get("rot")
            if rot:
                return int(rot)
    return 0


def _get_text_runs(elem: etree._Element) -> list[TextRun]:
    """Extract text runs from the element's text body."""
    runs: list[TextRun] = []

    for r_elem in elem.iter(f"{{{NS['a']}}}r"):
        t_elem = r_elem.find(f"{{{NS['a']}}}t")
        if t_elem is not None and t_elem.text:
            run = TextRun(text=t_elem.text)

            rpr = r_elem.find(f"{{{NS['a']}}}rPr")
            if rpr is not None:
                run.bold = rpr.get("b") == "1"
                run.italic = rpr.get("i") == "1"
                sz = rpr.get("sz")
                if sz:
                    run.font_size = int(sz)

                # Font family
                latin = rpr.find(f"{{{NS['a']}}}latin")
                if latin is not None:
                    run.font_family = latin.get("typeface", "")

            runs.append(run)

    return runs


def _get_placeholder_type(elem: etree._Element) -> str:
    """Get placeholder type (title, body, etc.)."""
    for ph in elem.iter(f"{{{NS['p']}}}ph"):
        return str(ph.get("type", "body"))
    return ""


def _get_placeholder_idx(elem: etree._Element) -> int | None:
    """Get placeholder index."""
    for ph in elem.iter(f"{{{NS['p']}}}ph"):
        idx = ph.get("idx")
        if idx is not None:
            return int(idx)
    return None


def _get_fill_type(elem: etree._Element) -> str:
    """Detect fill type from spPr."""
    for desc in elem.iter():
        tag = etree.QName(desc.tag).localname
        if tag == "solidFill":
            return "solid"
        if tag == "gradFill":
            return "gradient"
        if tag == "pattFill":
            return "pattern"
        if tag == "noFill":
            return "none"
    return ""


def _has_shadow(elem: etree._Element) -> bool:
    """Check if element has shadow effect."""
    for desc in elem.iter():
        tag = etree.QName(desc.tag).localname
        if tag in ("outerShdw", "innerShdw"):
            return True
    return False


def _has_blip_fill(elem: etree._Element) -> bool:
    """Return whether a native shape is raster-backed via DrawingML blip fill."""
    return any(etree.QName(desc.tag).localname == "blipFill" for desc in elem.iter())


def _get_field_type(elem: etree._Element) -> str:
    """Detect field type (slidenum, datetime, etc.)."""
    for fld in elem.iter(f"{{{NS['a']}}}fld"):
        fld_type = fld.get("type", "")
        if "slidenum" in fld_type.lower():
            return "slidenum"
        if "datetime" in fld_type.lower():
            return "datetime"
        return str(fld_type)
    return ""


def _obj_to_dict(obj: SceneObject) -> dict[str, Any]:
    """Serialize a SceneObject to dict."""
    d: dict[str, Any] = {
        "type": obj.obj_type,
        "name": obj.name,
        "z_index": obj.z_index,
        "bbox": list(obj.bbox),
        "rotation": obj.rotation,
    }
    if obj.text_runs:
        d["text_runs"] = [
            {"text": r.text, "font": r.font_family, "size": r.font_size} for r in obj.text_runs
        ]
    if obj.placeholder_type:
        d["placeholder_type"] = obj.placeholder_type
    if obj.is_table:
        d["table"] = {"rows": obj.table_rows, "cols": obj.table_cols}
    if obj.is_chart:
        d["chart_type"] = obj.chart_type
    if obj.is_picture:
        d["is_picture"] = True
    if obj.field_type:
        d["field_type"] = obj.field_type
    if obj.fill_type:
        d["fill_type"] = obj.fill_type
    if obj.has_shadow:
        d["has_shadow"] = True
    if obj.asset_hash:
        d["asset_hash"] = obj.asset_hash
    if obj.children:
        d["children"] = [_obj_to_dict(c) for c in obj.children]
    return d
