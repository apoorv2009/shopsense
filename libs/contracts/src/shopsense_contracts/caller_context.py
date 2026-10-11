"""Caller context (LLD-4 L4b): a short-lived, signed statement of who is calling and with which
scope. ShopSense issues it per turn; the MCP server verifies it and forwards the customer to the
Order Platform. Customer identity therefore never comes from model output or from a tool argument.

Format: base64url(JSON payload) "." base64url(HMAC-SHA256(key, payload)). Stdlib only."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from enum import StrEnum

HEADER = "X-Caller-Context"
TTL_S = 300


class Scope(StrEnum):
    READ = "tools.read"
    SYSTEM = "tools.system"


class InvalidCallerContextError(Exception):
    """The token is malformed, forged, expired or for the wrong scope."""


@dataclass(frozen=True, slots=True)
class CallerContext:
    customer_no: str
    scope: str
    expires_at: int
    ticket_id: str | None = None
    channel: str | None = None


def issue(
    customer_no: str,
    scope: Scope,
    key: bytes,
    *,
    ticket_id: str | None = None,
    channel: str | None = None,
    ttl_s: int = TTL_S,
    now: int | None = None,
) -> str:
    issued = int(time.time()) if now is None else now
    payload = {
        "sub": customer_no,
        "scope": scope.value,
        "exp": issued + ttl_s,
        "tid": ticket_id,
        "ch": channel,
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return f"{_b64(body)}.{_b64(_mac(key, body))}"


def verify(token: str, key: bytes, *, now: int | None = None) -> CallerContext:
    try:
        body_part, mac_part = token.split(".", 1)
        body = _unb64(body_part)
        supplied = _unb64(mac_part)
    except (ValueError, TypeError) as exc:
        raise InvalidCallerContextError("malformed caller context") from exc
    if not hmac.compare_digest(supplied, _mac(key, body)):
        raise InvalidCallerContextError("bad signature")
    payload = json.loads(body)
    current = int(time.time()) if now is None else now
    if payload["exp"] < current:
        raise InvalidCallerContextError("caller context expired")
    return CallerContext(
        customer_no=str(payload["sub"]),
        scope=str(payload["scope"]),
        expires_at=int(payload["exp"]),
        ticket_id=payload.get("tid"),
        channel=payload.get("ch"),
    )


def _mac(key: bytes, body: bytes) -> bytes:
    return hmac.new(key, body, hashlib.sha256).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
