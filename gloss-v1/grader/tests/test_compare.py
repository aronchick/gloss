"""Tests for render comparison and diff diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from gloss.compare import compare_slides

if TYPE_CHECKING:
    from pathlib import Path


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
