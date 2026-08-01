"""Tests for Stage 0: Quarantine checks."""

import tempfile
import zipfile
from pathlib import Path

from gloss.quarantine import quarantine_check


def _make_minimal_pptx(path: Path) -> None:
    """Create a minimal valid .pptx (empty ZIP with required content types)."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
        zf.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        )
        zf.writestr(
            "ppt/slides/slide1.xml",
            '<?xml version="1.0"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        )


def test_valid_pptx_passes() -> None:
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        path = Path(f.name)
    _make_minimal_pptx(path)
    result = quarantine_check(path)
    assert result.passed
    assert result.slide_count == 1
    path.unlink()


def test_wrong_extension_fails() -> None:
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    result = quarantine_check(path)
    assert not result.passed
    assert "extension" in result.reason.lower()
    path.unlink()


def test_too_large_fails() -> None:
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        path = Path(f.name)
        # Write 101 MB of zeros
        f.write(b"\x00" * (101 * 1024 * 1024))
    result = quarantine_check(path)
    assert not result.passed
    assert "size" in result.reason.lower()
    path.unlink()


def test_invalid_zip_fails() -> None:
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        f.write(b"not a zip file")
        path = Path(f.name)
    result = quarantine_check(path)
    assert not result.passed
    assert "zip" in result.reason.lower()
    path.unlink()


def test_macros_detected() -> None:
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        path = Path(f.name)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Override PartName="/ppt/vbaProject.bin" '
            'ContentType="application/vnd.ms-office.vbaProject"/>'
            "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
    result = quarantine_check(path)
    assert not result.passed
    assert result.has_macros
    path.unlink()
