"""Tests for truthful ECMA-376 schema validation status."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from lxml import etree

from acidslide.schema_validate import validate_schema

PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PRESENTATION_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
)
CHART_STYLE_NS = "http://schemas.microsoft.com/office/drawing/2012/chartStyle"
CHART_STYLE_CONTENT_TYPE = "application/vnd.ms-office.chartstyle+xml"
CHART_COLOR_STYLE_CONTENT_TYPE = "application/vnd.ms-office.chartcolorstyle+xml"
ROOT = Path(__file__).resolve().parents[2]


def _write_schema(schema_dir: Path) -> None:
    schema_dir.mkdir(parents=True)
    (schema_dir / "pml.xsd").write_text(
        f"""<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
  targetNamespace="{PRESENTATION_NS}" elementFormDefault="qualified">
  <xs:element name="presentation" type="xs:anyType"/>
</xs:schema>
""",
        encoding="utf-8",
    )


def _write_pptx(
    path: Path,
    root_element: str = "presentation",
    *,
    slide_size: tuple[int, int] | None = (12192000, 6858000),
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            f'''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Override PartName="/ppt/presentation.xml"
                ContentType="{PRESENTATION_CONTENT_TYPE}"/>
            </Types>''',
        )
        size = (
            f'<p:sldSz cx="{slide_size[0]}" cy="{slide_size[1]}"/>'
            if slide_size is not None and root_element == "presentation"
            else ""
        )
        archive.writestr(
            "ppt/presentation.xml",
            f'<p:{root_element} xmlns:p="{PRESENTATION_NS}">{size}</p:{root_element}>',
        )


def _write_extension_pptx(path: Path, *, content_type: str, document: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            f'''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Override PartName="/ppt/charts/extension.xml"
                ContentType="{content_type}"/>
            </Types>''',
        )
        archive.writestr("ppt/charts/extension.xml", document)


def _minimal_chart_style() -> str:
    required_entries = (
        "axisTitle",
        "categoryAxis",
        "chartArea",
        "dataLabel",
        "dataPoint",
        "dataPoint3D",
        "dataPointLine",
        "dataPointMarker",
        "dataPointWireframe",
        "dataTable",
        "downBar",
        "dropLine",
        "errorBar",
        "floor",
        "gridlineMajor",
        "gridlineMinor",
        "hiLoLine",
        "leaderLine",
        "legend",
        "plotArea",
        "plotArea3D",
        "seriesAxis",
        "seriesLine",
        "title",
        "trendline",
        "trendlineLabel",
        "upBar",
        "valueAxis",
        "wall",
    )
    entry = (
        '<cs:{name}><cs:lnRef idx="0"/><cs:fillRef idx="0"/>'
        '<cs:effectRef idx="0"/><cs:fontRef idx="minor"/></cs:{name}>'
    )
    children = "".join(entry.format(name=name) for name in required_entries)
    return f'<cs:chartStyle xmlns:cs="{CHART_STYLE_NS}">{children}</cs:chartStyle>'


def test_missing_explicit_schema_directory_is_not_reported_valid(tmp_path: Path) -> None:
    pptx = tmp_path / "submission.pptx"
    _write_pptx(pptx)

    result = validate_schema(pptx, tmp_path / "missing")

    assert result.performed is False
    assert result.valid is False
    assert "unavailable" in result.violations[0]


def test_validates_mapped_parts_with_available_schema(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schemas"
    _write_schema(schema_dir)
    pptx = tmp_path / "submission.pptx"
    _write_pptx(pptx)

    result = validate_schema(pptx, schema_dir)

    assert result.performed is True
    assert result.valid is True
    assert result.violations == []


@pytest.mark.parametrize("slide_size", [None, (12192000, 6857999), (6858000, 12192000)])
def test_noncanonical_slide_size_fails_closed(
    tmp_path: Path, slide_size: tuple[int, int] | None
) -> None:
    schema_dir = tmp_path / "schemas"
    _write_schema(schema_dir)
    pptx = tmp_path / "submission.pptx"
    _write_pptx(pptx, slide_size=slide_size)

    result = validate_schema(pptx, schema_dir)

    assert result.performed is True
    assert result.valid is False
    assert any("p:sldSz" in violation for violation in result.violations)


def test_schema_violation_is_reported_after_validation(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schemas"
    _write_schema(schema_dir)
    pptx = tmp_path / "submission.pptx"
    _write_pptx(pptx, root_element="notPresentation")

    result = validate_schema(pptx, schema_dir)

    assert result.performed is False
    assert result.valid is False
    assert "validated 0 of 1" in result.violations[0]
    assert "unmapped relevant XML part" in result.violations[1]


def test_unmapped_relevant_extension_part_fails_closed(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schemas"
    _write_schema(schema_dir)
    pptx = tmp_path / "submission.pptx"
    with zipfile.ZipFile(pptx, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            f'''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Override PartName="/ppt/presentation.xml" ContentType="{PRESENTATION_CONTENT_TYPE}"/>
              <Override PartName="/ppt/extensions/opaque.xml"
                ContentType="application/x-opaque+xml"/>
            </Types>''',
        )
        archive.writestr(
            "ppt/presentation.xml",
            f'<p:presentation xmlns:p="{PRESENTATION_NS}">'
            '<p:sldSz cx="12192000" cy="6858000"/>'
            "</p:presentation>",
        )
        archive.writestr("ppt/extensions/opaque.xml", '<x:opaque xmlns:x="urn:opaque"/>')

    result = validate_schema(pptx, schema_dir)

    assert result.performed is False
    assert result.valid is False
    assert any("unmapped relevant XML part" in violation for violation in result.violations)


def test_malformed_schema_is_configuration_failure(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    (schema_dir / "pml.xsd").write_text("not XML", encoding="utf-8")
    pptx = tmp_path / "submission.pptx"
    _write_pptx(pptx)

    result = validate_schema(pptx, schema_dir)

    assert result.performed is False
    assert result.valid is False
    assert "Could not load pml.xsd" in result.violations[0]


def test_bad_zip_is_invalid_and_not_performed(tmp_path: Path) -> None:
    pptx = tmp_path / "submission.pptx"
    pptx.write_bytes(b"not a zip")
    schema_dir = tmp_path / "schemas"
    _write_schema(schema_dir)

    result = validate_schema(pptx, schema_dir)

    assert result.performed is False
    assert result.valid is False
    assert "No relevant PresentationML" in result.violations[0]
    assert "Invalid ZIP" in result.violations[1]


def test_transitional_bullet_size_accepts_decimal_and_percent_forms(tmp_path: Path) -> None:
    dml_schema = (
        Path(__file__).resolve().parents[2]
        / "schemas"
        / "ecma-376"
        / "xsd-transitional"
        / "dml-main.xsd"
    )
    wrapper = tmp_path / "wrapper.xsd"
    wrapper.write_text(
        f"""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
          xmlns:t="urn:acidslide:test" targetNamespace="urn:acidslide:test">
          <xs:import namespace="http://schemas.openxmlformats.org/drawingml/2006/main"
            schemaLocation="{dml_schema.as_uri()}"/>
          <xs:element name="size" type="a:CT_TextBulletSizePercent"/>
        </xs:schema>""",
        encoding="utf-8",
    )
    schema = etree.XMLSchema(etree.parse(wrapper))

    assert schema.validate(etree.fromstring(b'<t:size xmlns:t="urn:acidslide:test" val="75000"/>'))
    assert schema.validate(etree.fromstring(b'<t:size xmlns:t="urn:acidslide:test" val="75%"/>'))
    assert not schema.validate(
        etree.fromstring(b'<t:size xmlns:t="urn:acidslide:test" val="24999"/>')
    )


def test_reference_deck_validates_all_relevant_xml_parts() -> None:
    deck = ROOT / "benchmark" / "deck" / "gold" / "acidslide-v1-gold.pptx"
    with zipfile.ZipFile(deck) as archive:
        relevant_parts = [
            name
            for name in archive.namelist()
            if name.startswith("ppt/") and name.endswith(".xml") and "/_rels/" not in name
        ]

    result = validate_schema(deck)

    assert len(relevant_parts) == 39
    assert result.performed is True
    assert result.valid is True
    assert result.violations == []


@pytest.mark.parametrize(
    ("content_type", "document"),
    [
        (CHART_STYLE_CONTENT_TYPE, _minimal_chart_style()),
        (
            CHART_COLOR_STYLE_CONTENT_TYPE,
            f'<cs:colorStyle xmlns:cs="{CHART_STYLE_NS}" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" meth="cycle">'
            '<a:schemeClr val="accent1"/><cs:variation><a:lumMod val="60000"/>'
            "</cs:variation></cs:colorStyle>",
        ),
    ],
)
def test_office_2013_chart_style_documents_validate(
    tmp_path: Path, content_type: str, document: str
) -> None:
    pptx = tmp_path / "extension.pptx"
    _write_extension_pptx(pptx, content_type=content_type, document=document)

    result = validate_schema(pptx)

    assert result.performed is True
    assert result.valid is True
    assert result.violations == []


def test_chart_style_content_type_and_root_must_match(tmp_path: Path) -> None:
    pptx = tmp_path / "wrong-pair.pptx"
    color_style = f'<cs:colorStyle xmlns:cs="{CHART_STYLE_NS}" meth="cycle"/>'
    _write_extension_pptx(
        pptx,
        content_type=CHART_STYLE_CONTENT_TYPE,
        document=color_style,
    )

    result = validate_schema(pptx)

    assert result.performed is False
    assert result.valid is False
    assert any("unmapped relevant XML part" in violation for violation in result.violations)


@pytest.mark.parametrize(
    "document",
    [
        f'<cs:colorStyle xmlns:cs="{CHART_STYLE_NS}" meth="cycle" bogus="true"/>',
        f'<cs:colorStyle xmlns:cs="{CHART_STYLE_NS}" meth="cycle"><cs:unknown/></cs:colorStyle>',
    ],
)
def test_chart_style_schema_rejects_unknown_content(tmp_path: Path, document: str) -> None:
    pptx = tmp_path / "malformed-extension.pptx"
    _write_extension_pptx(
        pptx,
        content_type=CHART_COLOR_STYLE_CONTENT_TYPE,
        document=document,
    )

    result = validate_schema(pptx)

    assert result.performed is True
    assert result.valid is False
    assert result.violations
