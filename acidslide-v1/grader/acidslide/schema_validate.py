"""Stage 0.5: ECMA-376 schema validation against Transitional XSD schemas."""

from __future__ import annotations

import zipfile
from functools import lru_cache
from pathlib import Path

from lxml import etree

from acidslide.models import SchemaValidationResult

# Namespace → XSD file mapping for PresentationML parts
NS_TO_XSD: dict[str, str] = {
    "http://schemas.openxmlformats.org/presentationml/2006/main": "pml.xsd",
    "http://schemas.openxmlformats.org/drawingml/2006/main": "dml-main.xsd",
    "http://schemas.openxmlformats.org/drawingml/2006/chart": "dml-chart.xsd",
}


def _hardened_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
        huge_tree=False,
    )


@lru_cache(maxsize=16)
def _load_xsd(xsd_path: str) -> etree.XMLSchema | None:
    """Load and cache an XSD schema. Returns None if loading fails."""
    try:
        doc = etree.parse(xsd_path, parser=_hardened_parser())
        return etree.XMLSchema(doc)
    except Exception:
        return None


def validate_schema(
    pptx_path: Path,
    schema_dir: Path | None = None,
) -> SchemaValidationResult:
    """Validate .pptx content against ECMA-376 Transitional XSD schemas.

    Non-blocking: schema-invalid files are not rejected, but violations
    are reported in the grading result.
    """
    violations: list[str] = []

    if schema_dir is None:
        base = Path(__file__).parent.parent.parent.parent
        schema_dir = base / "schemas" / "ecma-376" / "xsd-transitional"

    if not schema_dir.exists():
        return SchemaValidationResult(
            valid=True,
            violations=["ECMA-376 XSD schemas not found — skipping validation"],
        )

    try:
        with zipfile.ZipFile(pptx_path, "r") as zf:
            parser = _hardened_parser()

            for name in zf.namelist():
                if not _should_validate(name):
                    continue

                try:
                    xml_bytes = zf.read(name)
                    tree = etree.fromstring(xml_bytes, parser=parser)

                    # Find the root element's namespace
                    root_ns = _get_root_namespace(tree)
                    xsd_file = NS_TO_XSD.get(root_ns)

                    if xsd_file:
                        xsd_path = schema_dir / xsd_file
                        if xsd_path.exists():
                            schema = _load_xsd(str(xsd_path))
                            if schema and not schema.validate(tree):
                                for err in schema.error_log:
                                    violations.append(f"{name}:{err.line}: {err.message}")

                except etree.XMLSyntaxError as e:
                    violations.append(f"{name}: XML syntax error — {e}")

    except zipfile.BadZipFile:
        violations.append("Invalid ZIP structure")
    except Exception as e:
        violations.append(f"Schema validation error: {e}")

    return SchemaValidationResult(
        valid=len(violations) == 0,
        violations=violations,
    )


def _should_validate(name: str) -> bool:
    """Check if a ZIP entry should be schema-validated."""
    return name.startswith("ppt/") and name.endswith(".xml") and "/_rels/" not in name


def _get_root_namespace(tree: etree._Element) -> str:
    """Extract the namespace URI from the root element's tag."""
    tag = tree.tag
    if tag.startswith("{"):
        return tag[1 : tag.index("}")]
    return ""
