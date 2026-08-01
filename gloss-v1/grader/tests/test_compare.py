"""Tests for render comparison and diff diagnostics."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
from lxml import etree
from PIL import Image

from gloss.compare import compare_native_decks, compare_slides


def _image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (16, 16)) -> None:
    Image.new("RGB", size, color).save(path)


def test_identical_slides_are_pixel_exact(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    submission = tmp_path / "submission"
    gold.mkdir()
    submission.mkdir()
    _image(gold / "slide-01.png", (20, 30, 40))
    _image(submission / "slide-01.png", (20, 30, 40))

    result = compare_slides(submission, gold)

    assert result[0].pixel_exact is True
    assert result[0].ssim == 1.0


def test_missing_submission_slide_scores_zero(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    submission = tmp_path / "submission"
    gold.mkdir()
    submission.mkdir()
    _image(gold / "slide-01.png", (20, 30, 40))

    result = compare_slides(submission, gold)

    assert result[0].ssim == 0.0
    assert result[0].pixel_exact is False


def test_dimension_mismatch_fails_without_resizing(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    submission = tmp_path / "submission"
    diffs = tmp_path / "diffs"
    gold.mkdir()
    submission.mkdir()
    _image(gold / "slide-01.png", (0, 0, 0))
    _image(submission / "slide-01.png", (255, 255, 255), size=(32, 32))

    result = compare_slides(submission, gold, diffs)

    assert result[0].ssim == 0.0
    assert result[0].pixel_exact is False
    assert result[0].diff_path is None


def test_diff_uses_signed_arithmetic_before_amplification(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    submission = tmp_path / "submission"
    diffs = tmp_path / "diffs"
    gold.mkdir()
    submission.mkdir()
    _image(gold / "slide-01.png", (0, 0, 0))
    _image(submission / "slide-01.png", (255, 255, 255))

    result = compare_slides(submission, gold, diffs)

    assert result[0].diff_path == diffs / "diff-slide-01.png"
    with Image.open(result[0].diff_path) as diff:
        assert np.array(diff).max() == 255


def _move_named_native_objects(
    source: Path,
    destination: Path,
    targets: dict[str, str],
) -> None:
    drawing_namespace = "http://schemas.openxmlformats.org/drawingml/2006/main"
    presentation_namespace = "http://schemas.openxmlformats.org/presentationml/2006/main"
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w") as mutated:
        for info in original.infolist():
            content = original.read(info.filename)
            if target_text := targets.get(info.filename):
                root = etree.fromstring(content, parser=parser)
                shape_tree = root.find(f".//{{{presentation_namespace}}}spTree")
                assert shape_tree is not None

                def shape_text(candidate: etree._Element) -> str:
                    values = candidate.xpath(
                        ".//a:t/text()",
                        namespaces={"a": drawing_namespace},
                    )
                    assert isinstance(values, list)
                    return "".join(str(value) for value in values)

                shape = next(
                    (
                        candidate
                        for candidate in shape_tree.findall(f"{{{presentation_namespace}}}sp")
                        if target_text in shape_text(candidate)
                    ),
                    None,
                )
                assert shape is not None
                offset = shape.find(
                    f"{{{presentation_namespace}}}spPr/"
                    f"{{{drawing_namespace}}}xfrm/{{{drawing_namespace}}}off"
                )
                assert offset is not None
                offset.set("x", str(int(offset.get("x", "0")) + 914_400))
                content = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
            mutated.writestr(info, content)


def test_native_check_gold_is_exact_and_two_moves_are_two_findings(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    gold = root / "benchmark" / "deck" / "gold" / "gloss-v1-gold.pptx"
    assert compare_native_decks(gold, gold) == []

    edited = tmp_path / "edited.pptx"
    _move_named_native_objects(
        gold,
        edited,
        {
            "ppt/slides/slide2.xml": "Agenda",
            "ppt/slides/slide12.xml": "Document Fields",
        },
    )

    changes = compare_native_decks(edited, gold)

    assert len(changes) == 2
    assert [change.slide_number for change in changes] == [2, 12]
    assert [change.label for change in changes] == [
        "placeholder “Agenda”",
        "placeholder “Document Fields”",
    ]
    assert all(change.changed_fields == ("position",) for change in changes)
