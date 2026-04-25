"""Stage 0: Ingestion and quarantine — validates .pptx files before grading."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from lxml import etree

from acidslide.models import QuarantineResult

if TYPE_CHECKING:
    from pathlib import Path

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_DECOMPRESSED_SIZE = 500 * 1024 * 1024  # 500 MB
MAX_DECOMPRESSION_RATIO = 20

# Content types that indicate dangerous content
DANGEROUS_PARTS = {
    "application/vnd.ms-office.vbaProject",
    "application/vnd.ms-office.activeX+xml",
    "application/vnd.openxmlformats-officedocument.oleObject",
}

EXTERNAL_LINK_RELS = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
}


def quarantine_check(pptx_path: Path) -> QuarantineResult:
    """Run quarantine checks on a .pptx submission."""
    file_size = pptx_path.stat().st_size

    if pptx_path.suffix.lower() != ".pptx":
        return QuarantineResult(passed=False, reason="File extension is not .pptx")

    if file_size > MAX_FILE_SIZE:
        return QuarantineResult(
            passed=False,
            reason=f"File size {file_size} exceeds {MAX_FILE_SIZE} limit",
            file_size_bytes=file_size,
        )

    try:
        with zipfile.ZipFile(pptx_path, "r") as zf:
            # Check for ZIP bomb
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > MAX_DECOMPRESSED_SIZE:
                return QuarantineResult(
                    passed=False,
                    reason=f"Decompressed size {total_uncompressed} exceeds limit",
                    file_size_bytes=file_size,
                )

            ratio = total_uncompressed / file_size if file_size > 0 else 0
            if ratio > MAX_DECOMPRESSION_RATIO:
                return QuarantineResult(
                    passed=False,
                    reason=f"Decompression ratio {ratio:.1f}x exceeds limit",
                    file_size_bytes=file_size,
                )

            result = QuarantineResult(passed=True, file_size_bytes=file_size)

            # Check [Content_Types].xml for dangerous content
            if "[Content_Types].xml" in zf.namelist():
                parser = _hardened_parser()
                ct_xml = zf.read("[Content_Types].xml")
                ct_tree = etree.fromstring(ct_xml, parser=parser)

                for override in ct_tree.iter():
                    content_type = override.get("ContentType", "")
                    if content_type in DANGEROUS_PARTS:
                        if "vbaProject" in content_type:
                            result.has_macros = True
                        elif "activeX" in content_type:
                            result.has_activex = True
                        elif "oleObject" in content_type:
                            result.has_ole = True

            # Check for external links in rels
            for name in zf.namelist():
                if name.endswith(".rels"):
                    parser = _hardened_parser()
                    rels_xml = zf.read(name)
                    rels_tree = etree.fromstring(rels_xml, parser=parser)
                    for rel in rels_tree.iter():
                        rel_type = rel.get("Type", "")
                        target_mode = rel.get("TargetMode", "")
                        if rel_type in EXTERNAL_LINK_RELS and target_mode == "External":
                            result.has_external_links = True

            # Count slides
            slide_count = sum(
                1
                for name in zf.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )
            result.slide_count = slide_count

            # Check for password protection
            if "EncryptedPackage" in zf.namelist() or "EncryptionInfo" in zf.namelist():
                result.has_password = True

            # Determine pass/fail
            if result.has_macros:
                result.passed = False
                result.reason = "File contains VBA macros"
            elif result.has_activex:
                result.passed = False
                result.reason = "File contains ActiveX controls"
            elif result.has_ole:
                result.passed = False
                result.reason = "File contains embedded OLE objects"
            elif result.has_external_links:
                result.passed = False
                result.reason = "File contains external links"
            elif result.has_password:
                result.passed = False
                result.reason = "File is password protected"

            return result

    except zipfile.BadZipFile:
        return QuarantineResult(passed=False, reason="Invalid ZIP structure")
    except Exception as e:
        return QuarantineResult(passed=False, reason=f"Quarantine error: {e}")


def _hardened_parser() -> etree.XMLParser:
    """Create an XML parser with security hardening per §23."""
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
        huge_tree=False,
    )
