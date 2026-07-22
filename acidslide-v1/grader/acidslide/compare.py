"""Stage 2: Visual comparison — SSIM-based slide comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from acidslide.models import VisualComparisonResult

if TYPE_CHECKING:
    from pathlib import Path

SSIM_THRESHOLD = 0.9999


def compare_slides(
    submission_dir: Path,
    gold_dir: Path,
    diff_dir: Path | None = None,
) -> list[VisualComparisonResult]:
    """Compare exported submission slides against gold exports."""
    results: list[VisualComparisonResult] = []

    gold_slides = sorted(gold_dir.glob("slide-*.png"))
    for gold_path in gold_slides:
        slide_num = int(gold_path.stem.split("-")[1])
        sub_path = submission_dir / gold_path.name

        if not sub_path.exists():
            results.append(
                VisualComparisonResult(
                    slide_number=slide_num,
                    ssim=0.0,
                    pixel_exact=False,
                )
            )
            continue

        result = _compare_single(gold_path, sub_path, slide_num, diff_dir)
        results.append(result)

    return results


def _compare_single(
    gold_path: Path,
    sub_path: Path,
    slide_number: int,
    diff_dir: Path | None,
) -> VisualComparisonResult:
    """Compare two slide PNGs."""
    with Image.open(gold_path) as gold_source:
        gold_img = np.array(gold_source.convert("RGB"))
    with Image.open(sub_path) as submission_source:
        sub_img = np.array(submission_source.convert("RGB"))

    # Canonical exports must already have identical dimensions. Resizing would
    # introduce a second, non-normative visual pipeline.
    if gold_img.shape != sub_img.shape:
        return VisualComparisonResult(
            slide_number=slide_number,
            ssim=0.0,
            pixel_exact=False,
        )

    # Compute SSIM (RGB, per-channel then averaged)
    ssim_score = cast(
        "float",
        ssim(  # type: ignore[no-untyped-call]
            gold_img,
            sub_img,
            channel_axis=2,
            data_range=255,
            win_size=7,
            gaussian_weights=False,
            use_sample_covariance=True,
            K1=0.01,
            K2=0.03,
        ),
    )

    # Exact pixel match
    pixel_exact = np.array_equal(gold_img, sub_img)

    # Generate diff image if requested
    diff_path = None
    if diff_dir and not pixel_exact:
        diff_dir.mkdir(parents=True, exist_ok=True)
        diff_img = np.abs(gold_img.astype(np.int16) - sub_img.astype(np.int16))
        # Amplify differences for visibility
        diff_img = np.clip(diff_img * 10, 0, 255).astype(np.uint8)
        diff_path = diff_dir / f"diff-slide-{slide_number:02d}.png"
        Image.fromarray(diff_img).save(str(diff_path))

    return VisualComparisonResult(
        slide_number=slide_number,
        ssim=float(ssim_score),
        pixel_exact=pixel_exact,
        diff_path=diff_path,
    )
