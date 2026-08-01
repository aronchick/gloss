"""Opaque immutable-object storage for uploads and resolved packages."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from gloss_service.config import Settings
from gloss_service.models import Artifact
from gloss_service.quarantine_handoff import ObjectBinding

ZIP_MAGIC = b"PK\x03\x04"
OBJECT_VERSION = re.compile(r"^objv1_[0-9a-f]{32}$")


class UploadTooLargeError(ValueError):
    pass


class UploadTimeoutError(ValueError):
    pass


class InvalidUploadError(ValueError):
    pass


class ImmutableObjectError(ValueError):
    pass


@dataclass(frozen=True)
class StoredUpload:
    path: Path
    size: int
    sha256: str
    object_version: str

    @property
    def binding(self) -> ObjectBinding:
        return ObjectBinding(
            object_version=self.object_version,
            sha256=f"sha256:{self.sha256}",
            size_bytes=self.size,
        )


def new_object_version() -> str:
    return f"objv1_{uuid.uuid4().hex}"


def ensure_storage(settings: Settings) -> None:
    for directory in (
        settings.storage_path,
        settings.storage_path / "staging",
        settings.storage_path / "objects" / "original",
        settings.storage_path / "objects" / "resolved",
        settings.storage_path / "quarantine-jobs",
        settings.storage_path / "artifacts",
    ):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)


def immutable_object_path(
    settings: Settings,
    *,
    kind: str,
    sha256: str,
    object_version: str,
) -> Path:
    if kind not in {"original", "resolved"}:
        raise ImmutableObjectError("Unknown immutable object kind")
    digest = sha256.removeprefix("sha256:")
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ImmutableObjectError("Immutable object digest is invalid")
    if OBJECT_VERSION.fullmatch(object_version) is None:
        raise ImmutableObjectError("Immutable object version is invalid")
    return (
        settings.storage_path / "objects" / kind / "sha256" / digest / f"{object_version}.pptx"
    ).resolve()


def _publish_staged(
    staged: Path,
    settings: Settings,
    *,
    kind: str,
    sha256: str,
    object_version: str,
) -> Path:
    final = immutable_object_path(
        settings,
        kind=kind,
        sha256=sha256,
        object_version=object_version,
    )
    final.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.link(staged, final)
    except FileExistsError as exc:
        raise ImmutableObjectError("Immutable object version already exists") from exc
    staged.unlink()
    os.chmod(final, 0o400)
    return final


async def store_upload(upload: UploadFile, submission_id: str, settings: Settings) -> StoredUpload:
    """Stream one opaque upload while checking only transport metadata and magic bytes."""
    ensure_storage(settings)
    if not (upload.filename or "").lower().endswith(".pptx"):
        await upload.close()
        raise InvalidUploadError("File extension must be .pptx")
    object_version = new_object_version()
    staging = settings.storage_path / "staging" / f"{submission_id}-{object_version}.upload"
    digest = hashlib.sha256()
    size = 0
    magic = bytearray()
    try:
        try:
            async with asyncio.timeout(settings.upload_timeout_seconds):
                with staging.open("xb") as destination:
                    os.chmod(staging, 0o600)
                    while chunk := await upload.read(settings.upload_chunk_bytes):
                        size += len(chunk)
                        if size > settings.max_upload_bytes:
                            raise UploadTooLargeError(
                                f"File exceeds the {settings.max_upload_bytes}-byte upload limit"
                            )
                        if len(magic) < len(ZIP_MAGIC):
                            magic.extend(chunk[: len(ZIP_MAGIC) - len(magic)])
                        digest.update(chunk)
                        destination.write(chunk)
        except TimeoutError as exc:
            raise UploadTimeoutError("Upload exceeded the transport timeout") from exc
        if bytes(magic) != ZIP_MAGIC:
            raise InvalidUploadError("The upload is not an OOXML ZIP package")
        hexdigest = digest.hexdigest()
        final = _publish_staged(
            staging,
            settings,
            kind="original",
            sha256=hexdigest,
            object_version=object_version,
        )
        return StoredUpload(
            path=final,
            size=size,
            sha256=hexdigest,
            object_version=object_version,
        )
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def publish_resolved_object(
    staged: Path,
    settings: Settings,
    binding: ObjectBinding,
) -> Path:
    """Atomically commit sandbox output under its signed content address/version."""
    actual_digest, actual_size = hash_file(staged)
    if binding.sha256 != f"sha256:{actual_digest}" or binding.size_bytes != actual_size:
        raise ImmutableObjectError("Resolved sandbox output does not match its signed binding")
    return _publish_staged(
        staged,
        settings,
        kind="resolved",
        sha256=actual_digest,
        object_version=binding.object_version,
    )


def verify_immutable_object(
    path: Path,
    settings: Settings,
    *,
    kind: str,
    binding: ObjectBinding,
) -> Path:
    """Re-resolve, stat, and hash one immutable object before any package parse."""
    expected = immutable_object_path(
        settings,
        kind=kind,
        sha256=binding.sha256,
        object_version=binding.object_version,
    )
    resolved = path.resolve(strict=True)
    if resolved != expected or path.is_symlink() or not resolved.is_file():
        raise ImmutableObjectError("Immutable object path/version binding is invalid")
    actual_digest, actual_size = hash_file(resolved)
    if f"sha256:{actual_digest}" != binding.sha256 or actual_size != binding.size_bytes:
        raise ImmutableObjectError("Immutable object digest or size changed")
    return resolved


def delete_upload(path: Path) -> None:
    """Delete only a known object; retained for explicit administrative cleanup."""
    path.unlink(missing_ok=True)


def purge_expired_artifacts(session: Session, settings: Settings) -> int:
    from sqlalchemy import select

    now = datetime.now(UTC)
    rows = list(session.scalars(select(Artifact).where(Artifact.expires_at < now)))
    root = (settings.storage_path / "artifacts").resolve()
    removed = 0
    for artifact in rows:
        path = Path(artifact.storage_path).resolve()
        if path.is_relative_to(root):
            path.unlink(missing_ok=True)
            with suppress(OSError):
                path.parent.rmdir()
        session.delete(artifact)
        removed += 1
    session.commit()
    return removed
