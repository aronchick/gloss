"""Tests for ECMA-376 Markup Compatibility preprocessing."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from acidslide.inspect_ooxml import extract_deck_graph
from acidslide.mce import MC_NAMESPACE, MCEProfileError, preprocess_markup_compatibility

if TYPE_CHECKING:
    from pathlib import Path

PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"


def _document() -> etree._Element:
    return etree.fromstring(
        f"""<p:sld xmlns:p="{PRESENTATION_NS}" xmlns:p14="{P14_NS}"
          xmlns:mc="{MC_NAMESPACE}">
          <mc:AlternateContent>
            <mc:Choice Requires="p14"><p:transition p14:dur="2000"/></mc:Choice>
            <mc:Fallback><p:transition spd="slow"/></mc:Fallback>
          </mc:AlternateContent>
        </p:sld>"""
    )


def test_unsupported_choice_uses_fallback() -> None:
    root = preprocess_markup_compatibility(_document(), {PRESENTATION_NS})

    transition = root[0]
    assert etree.QName(transition).localname == "transition"
    assert transition.get("spd") == "slow"
    assert transition.get(f"{{{P14_NS}}}dur") is None


def test_understood_choice_is_selected() -> None:
    root = preprocess_markup_compatibility(_document(), {PRESENTATION_NS, P14_NS})

    transition = root[0]
    assert transition.get(f"{{{P14_NS}}}dur") == "2000"
    assert transition.get("spd") is None


def test_unsupported_choice_without_fallback_fails_closed() -> None:
    root = etree.fromstring(
        f"""<p:sld xmlns:p="{PRESENTATION_NS}" xmlns:p14="{P14_NS}"
          xmlns:mc="{MC_NAMESPACE}">
          <mc:AlternateContent>
            <mc:Choice Requires="p14"><p:transition p14:dur="2000"/></mc:Choice>
          </mc:AlternateContent>
        </p:sld>"""
    )

    with pytest.raises(MCEProfileError, match="neither a supported"):
        preprocess_markup_compatibility(root, {PRESENTATION_NS})


def test_undeclared_prefix_and_must_understand_fail_closed() -> None:
    undeclared = etree.fromstring(
        f'<p:sld xmlns:p="{PRESENTATION_NS}" xmlns:mc="{MC_NAMESPACE}" mc:Ignorable="missing"/>'
    )
    with pytest.raises(MCEProfileError, match="Undeclared"):
        preprocess_markup_compatibility(undeclared, {PRESENTATION_NS})

    must_understand = etree.fromstring(
        f'<p:sld xmlns:p="{PRESENTATION_NS}" xmlns:p14="{P14_NS}" '
        f'xmlns:mc="{MC_NAMESPACE}" mc:MustUnderstand="p14"/>'
    )
    with pytest.raises(MCEProfileError, match="MustUnderstand"):
        preprocess_markup_compatibility(must_understand, {PRESENTATION_NS})


def test_process_content_splices_children_and_preserve_records_evidence() -> None:
    extension = "urn:acidslide:unsupported"
    root = etree.fromstring(
        f'''<p:sld xmlns:p="{PRESENTATION_NS}" xmlns:x="{extension}" xmlns:mc="{MC_NAMESPACE}"
          mc:Ignorable="x" mc:ProcessContent="x:wrapper" mc:PreserveElements="x:preserved">
          <x:wrapper><p:transition spd="slow"/></x:wrapper>
          <x:preserved><p:transition spd="fast"/></x:preserved>
        </p:sld>'''
    )
    evidence: list[dict[str, str]] = []

    preprocess_markup_compatibility(
        root,
        {PRESENTATION_NS},
        preserved_evidence=evidence,
    )

    assert len(root) == 1
    assert root[0].get("spd") == "slow"
    assert evidence[0]["kind"] == "element"
    assert evidence[0]["qname"] == f"{{{extension}}}preserved"


def test_scene_graph_extraction_processes_alternate_content(tmp_path: Path) -> None:
    pptx = tmp_path / "mce.pptx"
    with zipfile.ZipFile(pptx, "w") as archive:
        archive.writestr(
            "ppt/presentation.xml",
            f"""<p:presentation xmlns:p="{PRESENTATION_NS}"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
            </p:presentation>""",
        )
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Target="slides/slide1.xml"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"/>
            </Relationships>""",
        )
        archive.writestr(
            "ppt/slides/slide1.xml",
            f"""<p:sld xmlns:p="{PRESENTATION_NS}" xmlns:p14="{P14_NS}"
              xmlns:mc="{MC_NAMESPACE}">
              <p:cSld><p:spTree>
                <mc:AlternateContent>
                  <mc:Choice Requires="p14"><p:pic/></mc:Choice>
                  <mc:Fallback><p:sp><p:nvSpPr><p:cNvPr id="1" name="fallback"/>
                    </p:nvSpPr></p:sp></mc:Fallback>
                </mc:AlternateContent>
              </p:spTree></p:cSld>
            </p:sld>""",
        )

    deck = extract_deck_graph(pptx)

    assert len(deck.slides) == 1
    assert len(deck.slides[0].objects) == 1
    assert deck.slides[0].objects[0].name == "fallback"
