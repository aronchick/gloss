"""Static OOXML quarantine performed before a grading job is queued."""

from __future__ import annotations

import io
import ipaddress
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from gloss_service.config import Settings

OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
ZIP_MAGIC = b"PK\x03\x04"
NESTED_ARCHIVE_EXTENSIONS = {".zip", ".pptx", ".docx", ".xlsx", ".jar", ".7z", ".rar"}
SAFE_EMBEDDED_SPREADSHEET_CONTENT_TYPE = (
    b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
DANGEROUS_EXTENSIONS = {
    ".exe",
    ".dll",
    ".com",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".js",
    ".jar",
    ".msi",
    ".scr",
    ".sh",
    ".py",
    ".app",
    ".dylib",
    ".so",
}
DANGEROUS_CONTENT_MARKERS = (
    b"macroEnabled",
    b"application/vnd.ms-office.vbaProject",
    b"application/vnd.ms-office.activeX",
    b"application/vnd.openxmlformats-officedocument.oleObject",
)
EXTERNAL_RELATIONSHIP = re.compile(rb'TargetMode\s*=\s*["\']External["\']', re.IGNORECASE)


@dataclass(frozen=True)
class QuarantineResult:
    passed: bool
    reason: str = ""
    slide_count: int = 0


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return not (path.is_absolute() or ".." in path.parts or "\\" in name or "\x00" in name)


def _inspect_embedded_spreadsheet(
    payload: bytes,
    settings: Settings,
) -> tuple[str | None, int, int]:
    """Validate the inert OOXML workbook backing a native chart."""
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as workbook:
            entries = workbook.infolist()
            names = {info.filename for info in entries}
            if not entries:
                return "Embedded spreadsheet package has no parts", 0, 0
            if len(names) != len(entries):
                return "Embedded spreadsheet has duplicate part names", 0, 0
            if any(info.flag_bits & 0x1 for info in entries):
                return "Encrypted embedded spreadsheets are forbidden", 0, 0
            if any(not _safe_member_name(info.filename) for info in entries):
                return "Unsafe path found inside embedded spreadsheet", 0, 0
            required = {"[Content_Types].xml", "xl/workbook.xml"}
            if missing := required - names:
                return f"Embedded spreadsheet is missing required parts: {sorted(missing)}", 0, 0

            total_uncompressed = sum(info.file_size for info in entries)
            compressed = max(sum(info.compress_size for info in entries), 1)
            if total_uncompressed / compressed > settings.max_decompression_ratio:
                return "Embedded spreadsheet decompression ratio exceeds the safety limit", 0, 0

            content_types = workbook.read("[Content_Types].xml")
            if b"spreadsheetml.sheet.main+xml" not in content_types:
                return "Embedded package is not a standard OOXML spreadsheet", 0, 0
            if any(marker in content_types for marker in DANGEROUS_CONTENT_MARKERS):
                return "Dangerous embedded spreadsheet content type is forbidden", 0, 0

            for info in entries:
                suffix = PurePosixPath(info.filename).suffix.lower()
                if suffix in DANGEROUS_EXTENSIONS or suffix in NESTED_ARCHIVE_EXTENSIONS:
                    return (
                        f"Nested content is forbidden in embedded spreadsheet: {info.filename}",
                        0,
                        0,
                    )
                if info.filename.startswith("xl/embeddings/"):
                    return "Nested embedded packages are forbidden in spreadsheets", 0, 0
                if info.filename.startswith("xl/activeX/") or "vbaProject" in info.filename:
                    return "Active content is forbidden in embedded spreadsheets", 0, 0
                if info.filename.endswith(".rels") and EXTERNAL_RELATIONSHIP.search(
                    workbook.read(info)
                ):
                    return "External relationships are forbidden in embedded spreadsheets", 0, 0
                if info.file_size >= len(OLE_MAGIC) and info.file_size <= 25 * 1024 * 1024:
                    with workbook.open(info) as part:
                        if part.read(len(OLE_MAGIC)) == OLE_MAGIC:
                            return "Hidden OLE content is forbidden in embedded spreadsheets", 0, 0
            return None, total_uncompressed, len(entries)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, OSError):
        return "Embedded spreadsheet is not a valid OOXML ZIP package", 0, 0


def inspect_pptx(path: Path, tier: int, settings: Settings) -> QuarantineResult:
    if path.suffix.lower() != ".pptx":
        return QuarantineResult(False, "File extension must be .pptx")
    if path.stat().st_size == 0:
        return QuarantineResult(False, "File is empty")
    with path.open("rb") as source:
        if source.read(4) != ZIP_MAGIC:
            return QuarantineResult(False, "The file is not an OOXML ZIP package")

    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > settings.max_zip_entries:
                return QuarantineResult(False, "ZIP entry count exceeds the safety limit")
            if not entries:
                return QuarantineResult(False, "OOXML package has no parts")
            if any(info.flag_bits & 0x1 for info in entries):
                return QuarantineResult(False, "Encrypted ZIP entries are not accepted")
            if any(not _safe_member_name(info.filename) for info in entries):
                return QuarantineResult(False, "Unsafe path found inside OOXML package")
            if len({info.filename for info in entries}) != len(entries):
                return QuarantineResult(False, "Duplicate OOXML part names are forbidden")

            names = {info.filename for info in entries}
            required = {"[Content_Types].xml", "ppt/presentation.xml"}
            missing = required - names
            if missing:
                return QuarantineResult(False, f"Missing required OOXML parts: {sorted(missing)}")

            total_uncompressed = sum(info.file_size for info in entries)
            if total_uncompressed > settings.max_uncompressed_bytes:
                return QuarantineResult(False, "Decompressed package size exceeds the safety limit")
            compressed = max(sum(info.compress_size for info in entries), 1)
            if total_uncompressed / compressed > settings.max_decompression_ratio:
                return QuarantineResult(False, "ZIP decompression ratio exceeds the safety limit")

            content_types = archive.read("[Content_Types].xml")
            if any(marker in content_types for marker in DANGEROUS_CONTENT_MARKERS):
                return QuarantineResult(False, "Dangerous OOXML content type is forbidden")

            nested_uncompressed = 0
            nested_entries = 0
            for info in entries:
                suffix = PurePosixPath(info.filename).suffix.lower()
                if suffix in DANGEROUS_EXTENSIONS:
                    return QuarantineResult(False, f"Executable content is forbidden: {suffix}")
                if info.filename.startswith("ppt/embeddings/"):
                    if (
                        suffix != ".xlsx"
                        or SAFE_EMBEDDED_SPREADSHEET_CONTENT_TYPE not in content_types
                    ):
                        return QuarantineResult(False, "Embedded OLE/package content is forbidden")
                    reason, inner_uncompressed, inner_entries = _inspect_embedded_spreadsheet(
                        archive.read(info), settings
                    )
                    if reason:
                        return QuarantineResult(False, reason)
                    nested_uncompressed += inner_uncompressed
                    nested_entries += inner_entries
                    if len(entries) + nested_entries > settings.max_zip_entries:
                        return QuarantineResult(
                            False, "Combined ZIP entry count exceeds the safety limit"
                        )
                    if total_uncompressed + nested_uncompressed > settings.max_uncompressed_bytes:
                        return QuarantineResult(
                            False, "Combined decompressed size exceeds the safety limit"
                        )
                elif suffix in NESTED_ARCHIVE_EXTENSIONS and info.filename != path.name:
                    return QuarantineResult(False, f"Nested archive is forbidden: {info.filename}")
                if info.filename.startswith("ppt/activeX/") or "vbaProject" in info.filename:
                    return QuarantineResult(False, "Active content is forbidden")

            for info in entries:
                if info.filename.endswith(".rels"):
                    relationships = archive.read(info)
                    if EXTERNAL_RELATIONSHIP.search(relationships):
                        return QuarantineResult(False, "External OOXML relationships are forbidden")
                if info.file_size >= len(OLE_MAGIC) and info.file_size <= 25 * 1024 * 1024:
                    with archive.open(info) as part:
                        if part.read(len(OLE_MAGIC)) == OLE_MAGIC:
                            return QuarantineResult(False, "Hidden OLE content is forbidden")

            slide_count = sum(
                1 for name in names if re.fullmatch(r"ppt/slides/slide[1-9][0-9]*\.xml", name)
            )
            expected = {1: 5, 2: 12, 3: 20}[tier]
            if slide_count != expected:
                return QuarantineResult(
                    False,
                    f"Tier {tier} requires {expected} slides; this deck contains {slide_count}",
                    slide_count,
                )
            return QuarantineResult(True, slide_count=slide_count)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, OSError) as exc:
        return QuarantineResult(False, f"Invalid OOXML package: {type(exc).__name__}")


def is_public_https_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return True
    return address.is_global
