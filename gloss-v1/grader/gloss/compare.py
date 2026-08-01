"""Visual and native-object comparison for presentation artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from gloss.models import VisualComparisonResult

if TYPE_CHECKING:
    from pathlib import Path

    from gloss.inspect_ooxml import DeckGraph, SceneObject

SSIM_THRESHOLD = 0.9999


@dataclass(frozen=True)
class NativeObjectChange:
    """One changed native presentation object, aggregated into one finding."""

    slide_number: int
    object_path: str
    label: str
    changed_fields: tuple[str, ...]
    change_type: str = "changed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "slide": self.slide_number,
            "object_path": self.object_path,
            "label": self.label,
            "change_type": self.change_type,
            "changed_fields": list(self.changed_fields),
        }


def compare_native_decks(submission: Path, reference: Path) -> list[NativeObjectChange]:
    """Return one finding for each native object that differs from ``reference``.

    This is the intentionally small front-door check used after editing the public
    Gloss deck. It compares the native object tree rather than rendered pixels and
    collapses any number of property differences on one object into one finding.
    The release grader remains responsible for full visual and protocol scoring.
    """
    from gloss.inspect_ooxml import extract_deck_graph

    submission_graph = extract_deck_graph(submission)
    reference_graph = extract_deck_graph(reference)
    return _compare_deck_graphs(submission_graph, reference_graph)


def _compare_deck_graphs(
    submission: DeckGraph,
    reference: DeckGraph,
) -> list[NativeObjectChange]:
    changes: list[NativeObjectChange] = []
    if len(submission.slides) != len(reference.slides):
        changes.append(
            NativeObjectChange(
                slide_number=0,
                object_path="deck",
                label="slide count",
                changed_fields=("slide_count",),
            )
        )

    shared_slides = min(len(submission.slides), len(reference.slides))
    for index in range(shared_slides):
        actual_slide = submission.slides[index]
        expected_slide = reference.slides[index]
        slide_number = expected_slide.slide_number
        slide_fields = tuple(
            field
            for field, actual, expected in (
                ("layout", actual_slide.layout_ref, expected_slide.layout_ref),
                ("layout_name", actual_slide.layout_name, expected_slide.layout_name),
                ("master", actual_slide.master_name, expected_slide.master_name),
            )
            if actual != expected
        )
        if slide_fields:
            changes.append(
                NativeObjectChange(
                    slide_number=slide_number,
                    object_path="slide",
                    label="slide properties",
                    changed_fields=slide_fields,
                )
            )

        actual_objects = dict(_flatten_objects(actual_slide.objects))
        expected_objects = dict(_flatten_objects(expected_slide.objects))
        for path in sorted(actual_objects.keys() | expected_objects.keys()):
            actual = actual_objects.get(path)
            expected = expected_objects.get(path)
            object_path = _format_object_path(path)
            if actual is None and expected is not None:
                changes.append(
                    NativeObjectChange(
                        slide_number=slide_number,
                        object_path=object_path,
                        label=_object_label(expected, object_path),
                        changed_fields=("presence",),
                        change_type="missing",
                    )
                )
                continue
            if expected is None and actual is not None:
                changes.append(
                    NativeObjectChange(
                        slide_number=slide_number,
                        object_path=object_path,
                        label=_object_label(actual, object_path),
                        changed_fields=("presence",),
                        change_type="unexpected",
                    )
                )
                continue
            if actual is None or expected is None:
                continue
            fields = _changed_object_fields(actual, expected)
            if fields:
                changes.append(
                    NativeObjectChange(
                        slide_number=slide_number,
                        object_path=object_path,
                        label=_object_label(expected, object_path),
                        changed_fields=fields,
                    )
                )

    for slide in reference.slides[shared_slides:]:
        changes.append(
            NativeObjectChange(
                slide_number=slide.slide_number,
                object_path="slide",
                label="entire slide",
                changed_fields=("presence",),
                change_type="missing",
            )
        )
    for slide in submission.slides[shared_slides:]:
        changes.append(
            NativeObjectChange(
                slide_number=slide.slide_number,
                object_path="slide",
                label="entire slide",
                changed_fields=("presence",),
                change_type="unexpected",
            )
        )
    return changes


def _flatten_objects(
    objects: list[SceneObject],
    parent: tuple[int, ...] = (),
) -> list[tuple[tuple[int, ...], SceneObject]]:
    flattened: list[tuple[tuple[int, ...], SceneObject]] = []
    for index, obj in enumerate(objects, 1):
        path = parent + (index,)
        flattened.append((path, obj))
        flattened.extend(_flatten_objects(obj.children, path))
    return flattened


def _format_object_path(path: tuple[int, ...]) -> str:
    return ".".join(str(value) for value in path)


def _object_label(obj: SceneObject, object_path: str) -> str:
    object_type = "placeholder" if obj.placeholder_type else obj.obj_type
    text = " ".join(run.text.strip() for run in obj.text_runs if run.text.strip())
    if text:
        excerpt = text if len(text) <= 42 else f"{text[:39].rstrip()}…"
        return f"{object_type} “{excerpt}”"
    if obj.name:
        return f"{object_type} “{obj.name}”"
    return f"{object_type} {object_path}"


def _changed_object_fields(actual: SceneObject, expected: SceneObject) -> tuple[str, ...]:
    fields: list[str] = []
    if actual.bbox[:2] != expected.bbox[:2]:
        fields.append("position")
    if actual.bbox[2:] != expected.bbox[2:]:
        fields.append("size")
    comparisons = (
        ("type", actual.obj_type, expected.obj_type),
        ("name", actual.name, expected.name),
        ("z_order", actual.z_index, expected.z_index),
        ("rotation", actual.rotation, expected.rotation),
        ("text", _text_snapshot(actual), _text_snapshot(expected)),
        (
            "placeholder",
            (actual.placeholder_type, actual.placeholder_idx),
            (expected.placeholder_type, expected.placeholder_idx),
        ),
        (
            "table",
            (actual.is_table, actual.table_rows, actual.table_cols),
            (expected.is_table, expected.table_rows, expected.table_cols),
        ),
        ("chart", (actual.is_chart, actual.chart_type), (expected.is_chart, expected.chart_type)),
        ("field", actual.field_type, expected.field_type),
        ("fill", (actual.fill_type, actual.opacity), (expected.fill_type, expected.opacity)),
        ("shadow", actual.has_shadow, expected.has_shadow),
        (
            "image",
            (actual.is_picture, actual.asset_hash),
            (expected.is_picture, expected.asset_hash),
        ),
        ("group", len(actual.children), len(expected.children)),
    )
    fields.extend(
        field
        for field, actual_value, expected_value in comparisons
        if actual_value != expected_value
    )
    return tuple(fields)


def _text_snapshot(obj: SceneObject) -> tuple[tuple[str, str, int, bool, bool], ...]:
    return tuple(
        (run.text, run.font_family, run.font_size, run.bold, run.italic) for run in obj.text_runs
    )


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
