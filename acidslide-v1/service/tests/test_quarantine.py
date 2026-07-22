from __future__ import annotations

from pathlib import Path

import pytest

from acidslide_service.config import Settings
from acidslide_service.quarantine import inspect_pptx

from .conftest import make_pptx


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"external_relationship": True}, "External OOXML"),
        ({"nested_archive": True}, "Nested archive"),
        ({"ole": True}, "Hidden OLE"),
        ({"traversal": True}, "Unsafe path"),
    ],
)
def test_evasion_techniques_are_rejected(
    tmp_path: Path,
    settings: Settings,
    kwargs: dict[str, bool],
    reason: str,
) -> None:
    path = tmp_path / "attack.pptx"
    path.write_bytes(make_pptx(**kwargs))
    result = inspect_pptx(path, 1, settings)
    assert not result.passed
    assert reason in result.reason


def test_extension_and_magic_are_both_checked(tmp_path: Path, settings: Settings) -> None:
    renamed = tmp_path / "renamed.pptx"
    renamed.write_bytes(b"not-a-zip")
    assert "not an OOXML" in inspect_pptx(renamed, 1, settings).reason

    wrong_extension = tmp_path / "deck.zip"
    wrong_extension.write_bytes(make_pptx())
    assert "extension" in inspect_pptx(wrong_extension, 1, settings).reason


def test_valid_tier_deck_passes(tmp_path: Path, settings: Settings) -> None:
    path = tmp_path / "valid.pptx"
    path.write_bytes(make_pptx(12))
    result = inspect_pptx(path, 2, settings)
    assert result.passed
    assert result.slide_count == 12


def test_safe_embedded_chart_workbook_passes(tmp_path: Path, settings: Settings) -> None:
    path = tmp_path / "chart-deck.pptx"
    path.write_bytes(make_pptx(5, embedded_spreadsheet=True))
    result = inspect_pptx(path, 1, settings)
    assert result.passed
    assert result.slide_count == 5
