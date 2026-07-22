"""Stage 1: LibreOffice headless export — converts .pptx slides to PNG."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from acidslide.models import SlideExport
from acidslide.resources import resolve_benchmark_dir

EXPORT_WIDTH = 1920
EXPORT_HEIGHT = 1080
EXPORT_TIMEOUT = 120  # seconds
# LibreOffice 7.3.7.2 rounds the exact 12192000-EMU width through its
# 1/100-mm internal unit. The raw PDF box is normative; rounded pdfinfo text
# is not evidence for this gate.
PDF_WIDTH_POINTS = Decimal("960.009448818898")
PDF_HEIGHT_POINTS = Decimal("540")
_PDF_NUMBER = rb"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_ALLOWED_LIBREOFFICE_STDERR_LINES = {
    "Warning: failed to launch javaldx - java may not function correctly",
}


def export_slides(
    pptx_path: Path,
    output_dir: Path,
    *,
    expected_page_count: int | None = None,
    pdf_output: Path | None = None,
) -> list[SlideExport]:
    """Export all slides from a .pptx to PNG using LibreOffice headless.

    Returns a list of SlideExport objects with paths to the exported PNGs.
    """
    libreoffice = find_libreoffice()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Copy input to temp dir (LibreOffice writes output alongside input)
        tmp_pptx = tmp / pptx_path.name
        shutil.copy2(pptx_path, tmp_pptx)

        # V1 has one normative export path. Direct PNG export and alternate
        # rasterizers are deliberately not fallbacks because they produce
        # different pixels.
        return _export_via_pdf(
            tmp_pptx,
            output_dir,
            libreoffice,
            expected_page_count=expected_page_count,
            pdf_output=pdf_output,
        )


def _export_via_pdf(
    pptx_path: Path,
    output_dir: Path,
    libreoffice: Path,
    *,
    expected_page_count: int | None = None,
    pdf_output: Path | None = None,
) -> list[SlideExport]:
    """Export via PDF intermediate: PPTX → PDF → per-page PNG."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        profile = tmp / "lo-profile"
        libreoffice_environment = _libreoffice_environment(tmp)

        # Step 1: PPTX → PDF
        _run_conversion(
            [
                str(libreoffice),
                "--headless",
                f"-env:UserInstallation={profile.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp),
                str(pptx_path),
            ],
            check=True,
            env=libreoffice_environment,
        )

        pdf_files = list(tmp.glob("*.pdf"))
        if not pdf_files:
            msg = "LibreOffice failed to produce PDF output"
            raise RuntimeError(msg)

        pdf_path = pdf_files[0]

        # Step 2: PDF → per-page PNG using Pillow (if available) or pdftoppm
        exports = _pdf_to_pngs(
            pdf_path,
            output_dir,
            expected_page_count=expected_page_count,
        )
        if pdf_output is not None:
            pdf_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf_path, pdf_output)
        return exports


def _pdf_to_pngs(
    pdf_path: Path,
    output_dir: Path,
    *,
    expected_page_count: int | None = None,
) -> list[SlideExport]:
    """Convert PDF pages to PNGs at 1920x1080."""
    if expected_page_count is not None:
        _validate_pdf_geometry(pdf_path, expected_page_count)
    # Try pdftoppm first (poppler-utils)
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        prefix = output_dir / "acidslide-render"
        _run_conversion(
            [
                pdftoppm,
                "-png",
                "-scale-to-x",
                str(EXPORT_WIDTH),
                "-scale-to-y",
                str(EXPORT_HEIGHT),
                str(pdf_path),
                str(prefix),
            ],
            check=True,
        )

        png_files = sorted(output_dir.glob("acidslide-render-*.png"), key=_page_number)
        if not png_files:
            msg = "pdftoppm failed to produce PNG output"
            raise RuntimeError(msg)
        if expected_page_count is not None and len(png_files) != expected_page_count:
            msg = (
                f"Canonical rasterizer produced {len(png_files)} pages; "
                f"expected exactly {expected_page_count}"
            )
            raise RuntimeError(msg)
        return _normalize_exports(png_files, output_dir)

    msg = "No PDF-to-PNG converter available. Install poppler-utils (pdftoppm)."
    raise RuntimeError(msg)


def find_libreoffice() -> Path:
    """Find the LibreOffice binary."""
    candidates = [
        "libreoffice",
        "soffice",
        "/usr/bin/libreoffice",
        "/usr/bin/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]

    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return Path(path)

    msg = "LibreOffice not found. Install LibreOffice or ensure it is in PATH."
    raise RuntimeError(msg)


def _run_conversion(
    command: list[str],
    *,
    check: bool,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=EXPORT_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        msg = f"Renderer timed out after {EXPORT_TIMEOUT} seconds"
        raise RuntimeError(msg) from exc
    except OSError as exc:
        msg = f"Could not start renderer: {exc}"
        raise RuntimeError(msg) from exc

    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic output"
        msg = f"Renderer exited with code {completed.returncode}: {detail}"
        raise RuntimeError(msg)
    stderr_lines = {line.strip() for line in completed.stderr.splitlines() if line.strip()}
    allowed_stderr = _ALLOWED_LIBREOFFICE_STDERR_LINES if "--convert-to" in command else set()
    unexpected_stderr = sorted(stderr_lines - allowed_stderr)
    if check and unexpected_stderr:
        raise RuntimeError(
            "Renderer emitted unclassified stderr despite a zero exit: "
            + " | ".join(unexpected_stderr)
        )
    return completed


def _libreoffice_environment(temp_root: Path) -> dict[str, str]:
    """Return an isolated LibreOffice environment without changing the process.

    The frozen Docker renderer already supplies its attested Fontconfig file and
    search path. Preserve that environment exactly. A local host without the
    canonical configuration instead receives a one-conversion Fontconfig setup
    that exposes only the benchmark font directory and a writable cache.
    """
    environment = dict(os.environ)
    if environment.get("FONTCONFIG_FILE"):
        return environment

    benchmark_dir = resolve_benchmark_dir()
    font_dir = (benchmark_dir / "fonts" / "files").resolve()
    if not font_dir.is_dir() or not any(path.is_file() for path in font_dir.iterdir()):
        raise RuntimeError(
            f"Bundled benchmark fonts are unavailable; expected font files under {font_dir}"
        )

    fontconfig_dir = temp_root / "fontconfig"
    cache_dir = fontconfig_dir / "cache"
    cache_dir.mkdir(parents=True)
    config_path = fontconfig_dir / "fonts.conf"
    config_path.write_text(
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
        "<fontconfig>\n"
        f"  <dir>{_xml_text(font_dir)}</dir>\n"
        f"  <cachedir>{_xml_text(cache_dir.resolve())}</cachedir>\n"
        "  <config><rescan><int>0</int></rescan></config>\n"
        "</fontconfig>\n",
        encoding="utf-8",
    )
    environment["FONTCONFIG_FILE"] = str(config_path.resolve())
    environment["FONTCONFIG_PATH"] = str(fontconfig_dir.resolve())
    return environment


def _xml_text(path: Path) -> str:
    """Escape a filesystem path for use as Fontconfig XML text."""
    return str(path).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _validate_pdf_geometry(pdf_path: Path, expected_page_count: int) -> None:
    """Reject PDF outputs whose page count, boxes, or rotation differ from v1."""
    try:
        reader = PdfReader(pdf_path, strict=True)
        pages = list(reader.pages)
    except Exception as exc:
        raise RuntimeError(f"Canonical PDF metadata could not be parsed: {exc}") from exc
    if len(pages) != expected_page_count:
        raise RuntimeError(
            f"Canonical PDF contains {len(pages)} pages; expected exactly {expected_page_count}"
        )

    page_references: list[tuple[int, int]] = []
    for page in pages:
        reference = page.indirect_reference
        if reference is None:
            raise RuntimeError("Canonical PDF page has no indirect object reference")
        page_references.append((reference.idnum, reference.generation))
    raw_boxes = _raw_page_boxes(pdf_path, page_references)

    expected_box = (Decimal(0), Decimal(0), PDF_WIDTH_POINTS, PDF_HEIGHT_POINTS)
    for page_number, page in enumerate(pages, 1):
        rotation = page.rotation
        media_box, explicit_crop_box = raw_boxes[page_number - 1]
        crop_box = explicit_crop_box or media_box
        if rotation != 0:
            raise RuntimeError(
                f"Canonical PDF page {page_number} has rotation {rotation}; expected 0"
            )
        if media_box != expected_box or crop_box != expected_box:
            raise RuntimeError(
                f"Canonical PDF page {page_number} must have MediaBox/effective CropBox "
                f"{expected_box}; found MediaBox={media_box}, CropBox={crop_box}"
            )


def _raw_page_boxes(
    pdf_path: Path,
    page_references: list[tuple[int, int]],
) -> list[
    tuple[
        tuple[Decimal, Decimal, Decimal, Decimal],
        tuple[Decimal, Decimal, Decimal, Decimal] | None,
    ]
]:
    """Read page boxes without a PDF library's floating-point normalization."""
    try:
        raw = pdf_path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"Canonical PDF bytes could not be read: {exc}") from exc

    boxes = []
    for object_number, generation in page_references:
        body = _raw_indirect_object(raw, object_number, generation)
        media_box = _raw_box(body, b"MediaBox", required=True)
        crop_box = _raw_box(body, b"CropBox", required=False)
        assert media_box is not None
        boxes.append((media_box, crop_box))
    return boxes


def _raw_indirect_object(raw: bytes, object_number: int, generation: int) -> bytes:
    header = re.compile(
        rb"(?m)^[ \t]*"
        + str(object_number).encode("ascii")
        + rb"[ \t]+"
        + str(generation).encode("ascii")
        + rb"[ \t]+obj(?:[ \t]*\r?\n|[ \t]+)"
    )
    matches = list(header.finditer(raw))
    if len(matches) != 1:
        raise RuntimeError(
            f"Canonical PDF page object {object_number} {generation} is missing or ambiguous"
        )
    start = matches[0].end()
    end = raw.find(b"endobj", start)
    if end < 0:
        raise RuntimeError(f"Canonical PDF page object {object_number} {generation} has no endobj")
    return raw[start:end]


def _raw_box(
    object_body: bytes,
    name: bytes,
    *,
    required: bool,
) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    pattern = re.compile(
        rb"/"
        + name
        + rb"\b\s*\[\s*("
        + _PDF_NUMBER
        + rb")\s+("
        + _PDF_NUMBER
        + rb")\s+("
        + _PDF_NUMBER
        + rb")\s+("
        + _PDF_NUMBER
        + rb")\s*\]"
    )
    matches = pattern.findall(object_body)
    if not matches:
        if not required:
            return None
        raise RuntimeError(f"Canonical PDF page has no direct /{name.decode('ascii')}")
    if len(matches) != 1:
        raise RuntimeError(f"Canonical PDF page has ambiguous /{name.decode('ascii')}")
    try:
        return tuple(Decimal(value.decode("ascii")) for value in matches[0])  # type: ignore[return-value]
    except (UnicodeDecodeError, ArithmeticError) as exc:
        raise RuntimeError("Canonical PDF contains an invalid page box") from exc


def _normalize_exports(png_files: list[Path], output_dir: Path) -> list[SlideExport]:
    exports: list[SlideExport] = []
    for slide_number, png in enumerate(png_files, 1):
        destination = output_dir / f"slide-{slide_number:02d}.png"
        with Image.open(png) as image:
            rgb = image.convert("RGB")
            if rgb.size != (EXPORT_WIDTH, EXPORT_HEIGHT):
                msg = (
                    f"Canonical rasterizer produced {rgb.size[0]}x{rgb.size[1]} for "
                    f"slide {slide_number}; expected {EXPORT_WIDTH}x{EXPORT_HEIGHT}"
                )
                raise RuntimeError(msg)
            rgb.save(destination, "PNG", optimize=False, compress_level=9)
        if png != destination:
            png.unlink()
        exports.append(SlideExport(slide_number=slide_number, path=destination))
    return exports


def _page_number(path: Path) -> int:
    try:
        return int(path.stem.rsplit("-", maxsplit=1)[1])
    except (IndexError, ValueError):
        return 0
