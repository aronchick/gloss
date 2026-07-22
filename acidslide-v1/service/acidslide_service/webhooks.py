"""HMAC-signed webhook delivery with DNS rebinding and SSRF defenses."""

from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import json
import socket
import ssl
import time
from typing import Any, cast
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from acidslide_service.config import Settings
from acidslide_service.models import Submission, WebhookDelivery
from acidslide_service.security import decrypt_secret


class UnsafeWebhookURLError(ValueError):
    pass


def _resolve_webhook(value: str) -> tuple[str, int, str, list[str]]:
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise UnsafeWebhookURLError("Webhook URL must use https://")
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise UnsafeWebhookURLError("Webhook URL is not allowed")
    try:
        answers = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeWebhookURLError("Webhook hostname did not resolve") from exc
    addresses = {cast(str, answer[4][0]) for answer in answers}
    if not addresses:
        raise UnsafeWebhookURLError("Webhook hostname did not resolve")
    for resolved in addresses:
        if not ipaddress.ip_address(resolved).is_global:
            raise UnsafeWebhookURLError("Webhook URL resolves to a private or non-routable address")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return parsed.hostname, parsed.port or 443, path, sorted(addresses)


def validate_webhook_url(value: str) -> None:
    _resolve_webhook(value)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Pin a vetted IP while retaining hostname-based certificate and SNI checks."""

    def __init__(self, hostname: str, address: str, port: int, timeout: int) -> None:
        self._ssl_context = ssl.create_default_context()
        super().__init__(hostname, port=port, timeout=timeout, context=self._ssl_context)
        self._address = address

    def connect(self) -> None:
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._ssl_context.wrap_socket(sock, server_hostname=self.host)


def _post_pinned(url: str, body: bytes, headers: dict[str, str]) -> int:
    hostname, port, path, addresses = _resolve_webhook(url)
    connection = _PinnedHTTPSConnection(hostname, addresses[0], port, timeout=10)
    try:
        connection.request("POST", path, body=body, headers={**headers, "Host": hostname})
        response = connection.getresponse()
        response.read(1024 * 1024)
        return response.status
    finally:
        connection.close()


def webhook_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def deliver_webhook(
    session: Session,
    submission: Submission,
    payload: dict[str, Any],
    settings: Settings,
) -> bool:
    if not submission.webhook_url or not submission.webhook_secret_encrypted:
        return True
    secret = decrypt_secret(submission.webhook_secret_encrypted, settings)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    headers = {
        "Content-Type": "application/json",
        "X-AcidSlide-Signature": webhook_signature(body, secret),
        "User-Agent": "AcidSlide-Webhook/1.0",
    }
    # Initial attempt plus the three OpenSpec retries at 1, 4, and 16 seconds.
    for attempt, delay in enumerate((0, 1, 4, 16), start=1):
        if delay:
            time.sleep(delay)
        try:
            response_status = _post_pinned(submission.webhook_url, body, headers)
            success = 200 <= response_status < 300
            outcome = (
                "delivered"
                if success
                else ("redirect_rejected" if 300 <= response_status < 400 else "http_error")
            )
            session.add(
                WebhookDelivery(
                    submission_id=submission.id,
                    attempt=attempt,
                    response_status=response_status,
                    outcome=outcome,
                )
            )
            session.commit()
            if success:
                return True
            if response_status < 500:
                return False
        except (http.client.HTTPException, OSError, UnsafeWebhookURLError) as exc:
            session.add(
                WebhookDelivery(
                    submission_id=submission.id,
                    attempt=attempt,
                    response_status=None,
                    outcome=type(exc).__name__,
                )
            )
            session.commit()
            if isinstance(exc, UnsafeWebhookURLError):
                return False
    return False
