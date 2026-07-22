"""Tests for deterministic slide export helpers and diagnostics."""

from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfWriter

from acidslide import export
from acidslide.models import SlideExport

_MAC_FONTCONFIG_STDERR = "\n".join(
    (
        "Fontconfig warning: no <cachedir> elements found. Check configuration.",
        "Fontconfig warning: adding "
        "<cachedir>/@.__________________________________________________OOO/var/cache/fontconfig"
        "</cachedir>",
        'Fontconfig warning: adding <cachedir prefix="xdg">fontconfig</cachedir>',
    )
)


def test_normalize_exports_rejects_noncanonical_dimensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(export, "EXPORT_WIDTH", 64)
    monkeypatch.setattr(export, "EXPORT_HEIGHT", 36)
    source = tmp_path / "raw-1.png"
    Image.new("RGB", (32, 18), "red").save(source)

    with pytest.raises(RuntimeError, match="expected 64x36"):
        export._normalize_exports([source], tmp_path)


def test_normalize_exports_uses_stable_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(export, "EXPORT_WIDTH", 64)
    monkeypatch.setattr(export, "EXPORT_HEIGHT", 36)
    source = tmp_path / "raw-1.png"
    Image.new("RGB", (64, 36), "red").save(source)

    exports = export._normalize_exports([source], tmp_path)

    assert exports[0].path == tmp_path / "slide-01.png"
    assert exports[0].path.name == "slide-01.png"
    with Image.open(exports[0].path) as image:
        assert image.size == (64, 36)


def test_pdf_to_pngs_sorts_pages_numerically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(export, "EXPORT_WIDTH", 64)
    monkeypatch.setattr(export, "EXPORT_HEIGHT", 36)
    monkeypatch.setattr("acidslide.export.shutil.which", lambda _name: "/usr/bin/pdftoppm")

    def fake_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        assert check is True
        prefix = Path(command[-1])
        Image.new("RGB", (64, 36), "red").save(prefix.with_name(f"{prefix.name}-10.png"))
        Image.new("RGB", (64, 36), "blue").save(prefix.with_name(f"{prefix.name}-2.png"))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(export, "_run_conversion", fake_run)

    exports = export._pdf_to_pngs(tmp_path / "slides.pdf", tmp_path)

    assert [item.path.name for item in exports] == ["slide-01.png", "slide-02.png"]
    with Image.open(exports[0].path) as first:
        assert first.getpixel((0, 0)) == (0, 0, 255)


def test_pdf_to_pngs_requires_converter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("acidslide.export.shutil.which", lambda _name: None)

    with pytest.raises(RuntimeError, match="poppler-utils"):
        export._pdf_to_pngs(tmp_path / "slides.pdf", tmp_path)


def test_run_conversion_surfaces_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "acidslide.export.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(["renderer"], 7, "", "broken"),
    )

    with pytest.raises(RuntimeError, match="code 7: broken"):
        export._run_conversion(["renderer"], check=True)


def test_run_conversion_rejects_unclassified_success_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "acidslide.export.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["libreoffice"], 0, "converted", "unexpected warning"
        ),
    )

    with pytest.raises(RuntimeError, match="unclassified stderr"):
        export._run_conversion(["libreoffice", "--convert-to", "pdf"], check=True)


def test_run_conversion_rejects_exact_mac_fontconfig_warning_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "acidslide.export.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["libreoffice"], 0, "converted", _MAC_FONTCONFIG_STDERR + "\n"
        ),
    )

    with pytest.raises(RuntimeError, match="unclassified stderr") as error:
        export._run_conversion(["libreoffice", "--convert-to", "pdf"], check=True)

    assert "no <cachedir> elements found" in str(error.value)
    assert "/var/cache/fontconfig" in str(error.value)


def test_run_conversion_rejects_mac_bundle_with_additional_unknown_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = _MAC_FONTCONFIG_STDERR + "\nunknown fourth warning\n"
    monkeypatch.setattr(
        "acidslide.export.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["libreoffice"], 0, "converted", stderr
        ),
    )

    with pytest.raises(RuntimeError, match="unknown fourth warning"):
        export._run_conversion(["libreoffice", "--convert-to", "pdf"], check=True)


def test_run_conversion_accepts_exact_javaldx_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warning = "Warning: failed to launch javaldx - java may not function correctly"
    monkeypatch.setattr(
        "acidslide.export.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["libreoffice"], 0, "converted", warning + "\n"
        ),
    )

    completed = export._run_conversion(["libreoffice", "--convert-to", "pdf"], check=True)

    assert completed.returncode == 0


def test_find_libreoffice_failure_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("acidslide.export.shutil.which", lambda _candidate: None)

    with pytest.raises(RuntimeError, match="LibreOffice not found"):
        export.find_libreoffice()


def test_export_slides_always_uses_pdf_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    submission = tmp_path / "submission.pptx"
    submission.write_bytes(b"pptx")
    destination = tmp_path / "output"
    monkeypatch.setattr(export, "find_libreoffice", lambda: Path("/renderer"))
    expected = [SlideExport(1, destination / "slide-01.png")]
    calls: list[tuple[Path, Path, Path]] = []

    def fake_pdf(
        pptx: Path,
        output: Path,
        renderer: Path,
        *,
        expected_page_count: int | None = None,
        pdf_output: Path | None = None,
    ) -> list[SlideExport]:
        assert expected_page_count is None
        assert pdf_output is None
        calls.append((pptx, output, renderer))
        return expected

    monkeypatch.setattr(export, "_export_via_pdf", fake_pdf)

    assert export.export_slides(submission, destination) == expected
    assert len(calls) == 1
    assert calls[0][1:] == (destination, Path("/renderer"))


def test_export_via_pdf_requires_generated_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        export,
        "_run_conversion",
        lambda _command, *, check, env=None: subprocess.CompletedProcess(["renderer"], 0),
    )

    with pytest.raises(RuntimeError, match="failed to produce PDF"):
        export._export_via_pdf(tmp_path / "submission.pptx", tmp_path, Path("/renderer"))


def test_export_via_pdf_retains_validated_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "submission.pptx"
    source.write_bytes(b"pptx")
    retained = tmp_path / "evidence" / "canonical.pdf"

    def fake_run(
        command: list[str],
        *,
        check: bool,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert env is not None
        if "--convert-to" in command:
            profile_arguments = [
                value for value in command if value.startswith("-env:UserInstallation=")
            ]
            assert len(profile_arguments) == 1
            assert profile_arguments[0].startswith("-env:UserInstallation=file://")
            assert profile_arguments[0] != (
                "-env:UserInstallation=file://<isolated-temporary-profile>"
            )
            output = Path(command[command.index("--outdir") + 1]) / "submission.pdf"
            output.write_bytes(b"canonical-pdf")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(export, "_run_conversion", fake_run)
    monkeypatch.setattr(export, "_pdf_to_pngs", lambda *_args, **_kwargs: [])

    assert (
        export._export_via_pdf(
            source,
            tmp_path / "exports",
            Path("/renderer"),
            pdf_output=retained,
        )
        == []
    )
    assert retained.read_bytes() == b"canonical-pdf"


def test_local_export_generates_isolated_fontconfig_for_libreoffice_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark = tmp_path / "benchmark"
    fonts = benchmark / "fonts" / "files"
    fonts.mkdir(parents=True)
    (fonts / "Test & Demo.ttf").write_bytes(b"font")
    source = tmp_path / "submission.pptx"
    source.write_bytes(b"pptx")
    sentinel = "preserved-value"
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)
    monkeypatch.delenv("FONTCONFIG_PATH", raising=False)
    monkeypatch.setenv("ACIDSLIDE_EXPORT_TEST_SENTINEL", sentinel)
    monkeypatch.setattr(export, "resolve_benchmark_dir", lambda: benchmark)
    observed_environment: dict[str, str] | None = None

    def fake_run(
        command: list[str],
        *,
        check: bool,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal observed_environment
        assert check is True
        assert env is not None
        observed_environment = env
        assert env["ACIDSLIDE_EXPORT_TEST_SENTINEL"] == sentinel
        config_path = Path(env["FONTCONFIG_FILE"])
        assert Path(env["FONTCONFIG_PATH"]) == config_path.parent
        root = ET.parse(config_path).getroot()
        assert root.tag == "fontconfig"
        assert [node.text for node in root.findall("dir")] == [str(fonts.resolve())]
        caches = root.findall("cachedir")
        assert len(caches) == 1
        assert caches[0].text is not None
        cache_path = Path(caches[0].text)
        assert cache_path.is_dir()
        assert cache_path.parent == config_path.parent
        output = Path(command[command.index("--outdir") + 1]) / "submission.pdf"
        output.write_bytes(b"local-pdf")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(export, "_run_conversion", fake_run)
    monkeypatch.setattr(export, "_pdf_to_pngs", lambda *_args, **_kwargs: [])

    assert export._export_via_pdf(source, tmp_path / "exports", Path("/renderer")) == []
    assert observed_environment is not None
    assert "FONTCONFIG_FILE" not in os.environ
    assert "FONTCONFIG_PATH" not in os.environ


def test_existing_frozen_fontconfig_environment_is_preserved_exactly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "submission.pptx"
    source.write_bytes(b"pptx")
    frozen_file = "/opt/acidslide/fontconfig/fonts.conf"
    frozen_path = "/opt/acidslide/fontconfig"
    monkeypatch.setenv("FONTCONFIG_FILE", frozen_file)
    monkeypatch.setenv("FONTCONFIG_PATH", frozen_path)
    monkeypatch.setattr(
        export,
        "resolve_benchmark_dir",
        lambda: pytest.fail("frozen environment must not generate host Fontconfig"),
    )
    expected_environment = dict(os.environ)
    observed_environment: dict[str, str] | None = None

    def fake_run(
        command: list[str],
        *,
        check: bool,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal observed_environment
        assert check is True
        assert env is not None
        observed_environment = env
        output = Path(command[command.index("--outdir") + 1]) / "submission.pdf"
        output.write_bytes(b"canonical-pdf")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(export, "_run_conversion", fake_run)
    monkeypatch.setattr(export, "_pdf_to_pngs", lambda *_args, **_kwargs: [])

    assert export._export_via_pdf(source, tmp_path / "exports", Path("/renderer")) == []
    assert observed_environment == expected_environment
    assert observed_environment["FONTCONFIG_FILE"] == frozen_file
    assert observed_environment["FONTCONFIG_PATH"] == frozen_path


def test_missing_benchmark_fonts_fail_before_renderer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark = tmp_path / "benchmark"
    benchmark.mkdir()
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)
    monkeypatch.delenv("FONTCONFIG_PATH", raising=False)
    monkeypatch.setattr(export, "resolve_benchmark_dir", lambda: benchmark)
    monkeypatch.setattr(
        export,
        "_run_conversion",
        lambda *_args, **_kwargs: pytest.fail("renderer must not run without benchmark fonts"),
    )

    with pytest.raises(RuntimeError, match="Bundled benchmark fonts are unavailable"):
        export._export_via_pdf(
            tmp_path / "submission.pptx",
            tmp_path / "exports",
            Path("/renderer"),
        )


def test_run_conversion_surfaces_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("renderer", export.EXPORT_TIMEOUT)

    monkeypatch.setattr("acidslide.export.subprocess.run", timeout)

    with pytest.raises(RuntimeError, match="timed out"):
        export._run_conversion(["renderer"], check=True)


def _write_exact_minimal_pdf(path: Path) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 960.009448818898 540] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 960.009448818898 540] "
        b"/CropBox [0 0 960.009448818898 540] >>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_number, body in enumerate(objects, 1):
        offsets.append(len(payload))
        payload.extend(f"{object_number} 0 obj\n".encode())
        payload.extend(body + b"\nendobj\n")
    xref_offset = len(payload)
    payload.extend(f"xref\n0 {len(offsets)}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    path.write_bytes(payload)


def test_pdf_geometry_accepts_exact_v1_pages(tmp_path: Path) -> None:
    pdf = tmp_path / "slides.pdf"
    _write_exact_minimal_pdf(pdf)

    export._validate_pdf_geometry(pdf, 2)


@pytest.mark.parametrize(
    ("pages", "width", "rotation", "message"),
    [
        (1, export.PDF_WIDTH_POINTS, 0, "contains 1 pages"),
        (2, export.PDF_WIDTH_POINTS, 90, "rotation 90"),
        (2, Decimal("960"), 0, "MediaBox/effective CropBox"),
    ],
)
def test_pdf_geometry_fails_closed(
    tmp_path: Path,
    pages: int,
    width: Decimal,
    rotation: int,
    message: str,
) -> None:
    pdf = tmp_path / "slides.pdf"
    writer = PdfWriter()
    for page_number in range(pages):
        page = writer.add_blank_page(
            width=float(width),
            height=float(export.PDF_HEIGHT_POINTS),
        )
        if page_number == 0 and rotation:
            page.rotate(rotation)
    writer.write(pdf)

    with pytest.raises(RuntimeError, match=message):
        export._validate_pdf_geometry(pdf, 2)


def test_page_number_handles_invalid_name() -> None:
    assert export._page_number(Path("slide-nope.png")) == 0
