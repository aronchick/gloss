"""Stage 1: LibreOffice headless export — converts .pptx slides to PNG."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from acidslide.models import SlideExport

EXPORT_WIDTH = 1920
EXPORT_HEIGHT = 1080
EXPORT_TIMEOUT = 120  # seconds


def export_slides(pptx_path: Path, output_dir: Path) -> list[SlideExport]:
    """Export all slides from a .pptx to PNG using LibreOffice headless.

    Returns a list of SlideExport objects with paths to the exported PNGs.
    """
    libreoffice = _find_libreoffice()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Copy input to temp dir (LibreOffice writes output alongside input)
        tmp_pptx = tmp / pptx_path.name
        shutil.copy2(pptx_path, tmp_pptx)

        # Try direct PNG export first
        subprocess.run(
            [
                str(libreoffice),
                "--headless",
                "--convert-to",
                "png",
                "--outdir",
                str(tmp),
                str(tmp_pptx),
            ],
            capture_output=True,
            text=True,
            timeout=EXPORT_TIMEOUT,
        )

        # LibreOffice single-file PNG export only gives slide 1.
        # Use PDF intermediate for all slides.
        png_files = sorted(tmp.glob("*.png"))

        if len(png_files) <= 1:
            # Fallback: PPTX → PDF → PNG per page
            return _export_via_pdf(tmp_pptx, output_dir, libreoffice)

        # Move PNGs to output directory with sequential naming
        exports = []
        for i, png in enumerate(png_files, 1):
            dest = output_dir / f"slide-{i:02d}.png"
            shutil.move(str(png), str(dest))
            exports.append(SlideExport(slide_number=i, path=dest))

        return exports


def _export_via_pdf(pptx_path: Path, output_dir: Path, libreoffice: Path) -> list[SlideExport]:
    """Export via PDF intermediate: PPTX → PDF → per-page PNG."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Step 1: PPTX → PDF
        subprocess.run(
            [
                str(libreoffice),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp),
                str(pptx_path),
            ],
            capture_output=True,
            text=True,
            timeout=EXPORT_TIMEOUT,
            check=True,
        )

        pdf_files = list(tmp.glob("*.pdf"))
        if not pdf_files:
            msg = "LibreOffice failed to produce PDF output"
            raise RuntimeError(msg)

        pdf_path = pdf_files[0]

        # Step 2: PDF → per-page PNG using Pillow (if available) or pdftoppm
        return _pdf_to_pngs(pdf_path, output_dir)


def _pdf_to_pngs(pdf_path: Path, output_dir: Path) -> list[SlideExport]:
    """Convert PDF pages to PNGs at 1920x1080."""
    # Try pdftoppm first (poppler-utils)
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        subprocess.run(
            [
                pdftoppm,
                "-png",
                "-rx",
                "150",  # DPI for ~1920px width at 16:9
                "-ry",
                "150",
                str(pdf_path),
                str(output_dir / "slide"),
            ],
            capture_output=True,
            text=True,
            timeout=EXPORT_TIMEOUT,
            check=True,
        )

        exports = []
        for i, png in enumerate(sorted(output_dir.glob("slide-*.png")), 1):
            dest = output_dir / f"slide-{i:02d}.png"
            if png != dest:
                png.rename(dest)
            exports.append(SlideExport(slide_number=i, path=dest))
        return exports

    # Fallback: use pdf2image if installed
    try:
        from pdf2image import convert_from_path

        images = convert_from_path(str(pdf_path), size=(EXPORT_WIDTH, EXPORT_HEIGHT))
        exports = []
        for i, img in enumerate(images, 1):
            dest = output_dir / f"slide-{i:02d}.png"
            img.save(str(dest), "PNG")
            exports.append(SlideExport(slide_number=i, path=dest))
        return exports
    except ImportError:
        pass

    msg = "No PDF-to-PNG converter available. Install poppler-utils or pdf2image."
    raise RuntimeError(msg)


def _find_libreoffice() -> Path:
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
