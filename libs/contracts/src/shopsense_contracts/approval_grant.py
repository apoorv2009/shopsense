"""Signed approval grant (M8-4, LLD-7 L7). A reviewer's approval, bound to one refund: the order,
the item, the exact amount, who approved, and when it expires. The Order Platform refuses a
decision that does not match its grant, so an approval cannot be replayed on another refund.

Same format as the caller context: base64url(JSON) "." base64url(HMAC-SHA256(key, payload))."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

GRANT_HEADER = "X-Approval-Grant"
GRANT_TTL_S = 900


class InvalidGrantError(Exception):
    """The grant is malformed, forged, expired, or does not match the refund."""


@dataclass(frozen=True, slots=True)
class GrantScope:
    order_no: str
    item_sku: str
    amount_paise: int
    reviewer: str
    ticket_id: str


def issue(
    scope: GrantScope, key: bytes, *, ttl_s: int = GRANT_TTL_S, now: int | None = None
) -> str:
    issued = int(time.time()) if now is None else now
    payload = {
        "order_no": scope.order_no,
        "sku": scope.item_sku,
        "amount_paise": scope.amount_paise,
        "reviewer": scope.reviewer,
        "ticket_id": scope.ticket_id,
        "exp": issued + ttl_s,
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return f"{_b64(body)}.{_b64(_mac(key, body))}"


def verify(token: str, key: bytes, *, expect: GrantScope, now: int | None = None) -> GrantScope:
    """Return the scope if the signature, the expiry and every bound field match `expect`."""
    try:
        body_part, mac_part = token.split(".", 1)
        body = _unb64(body_part)
        supplied = _unb64(mac_part)
    except (ValueError, TypeError) as exc:
        raise InvalidGrantError("malformed grant") from exc
    if not hmac.compare_digest(supplied, _mac(key, body)):
        raise InvalidGrantError("bad signature")
    payload = json.loads(body)
    current = int(time.time()) if now is None else now
    if payload["exp"] < current:
        raise InvalidGrantError("grant expired")
    scope = GrantScope(
        order_no=str(payload["order_no"]),
        item_sku=str(payload["sku"]),
        amount_paise=int(payload["amount_paise"]),
        reviewer=str(payload["reviewer"]),
        ticket_id=str(payload["ticket_id"]),
    )
    if scope.order_no != expect.order_no or scope.item_sku != expect.item_sku:
        raise InvalidGrantError("grant is for another item")
    if scope.amount_paise != expect.amount_paise:
        raise InvalidGrantError("grant is for another amount")
    return scope


def _mac(key: bytes, body: bytes) -> bytes:
    return hmac.new(key, body, hashlib.sha256).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("ascii"))
