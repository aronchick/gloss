"""API-key issuance, authentication, encryption, and request security."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from gloss_service.config import Settings, get_settings
from gloss_service.database import get_session
from gloss_service.models import Organization


@dataclass(frozen=True)
class IssuedKey:
    value: str
    prefix: str
    digest: str


def _key_digest(value: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


def issue_api_key(settings: Settings) -> IssuedKey:
    prefix = secrets.token_hex(4)
    value = f"asv1_{prefix}_{secrets.token_urlsafe(32)}"
    return IssuedKey(value=value, prefix=prefix, digest=_key_digest(value, settings.api_key_pepper))


def authenticate_api_key(value: str, session: Session, settings: Settings) -> Organization | None:
    parts = value.split("_", 2)
    if len(parts) != 3 or parts[0] != "asv1":
        return None
    organization = session.scalar(select(Organization).where(Organization.key_prefix == parts[1]))
    if organization is None:
        return None
    candidate = _key_digest(value, settings.api_key_pepper)
    if not hmac.compare_digest(candidate, organization.api_key_hash):
        return None
    return organization


def require_organization(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> Organization:
    value = x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        value = authorization[7:].strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_required", "message": "Provide an API key."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    organization = authenticate_api_key(value, session, settings)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_api_key", "message": "The API key is not valid."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if organization.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "account_suspended",
                "message": "This organization is suspended. Contact appeals@gloss.dev.",
            },
        )
    request.state.organization_id = organization.id
    return organization


def require_admin(
    settings: Annotated[Settings, Depends(get_settings)],
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    if not x_admin_key or not hmac.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "admin_authentication_required", "message": "Admin key required."},
        )


def encrypt_secret(secret: str, settings: Settings) -> str:
    return settings.fernet.encrypt(secret.encode()).decode()


def decrypt_secret(token: str, settings: Settings) -> str:
    return settings.fernet.decrypt(token.encode()).decode()
