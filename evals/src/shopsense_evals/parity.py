"""M6 channel-parity evaluation: the same ticket through chat and through email.

Each case runs over HTTP against the live ShopSense API. Email goes first: an email refund waits
for approval and writes nothing, so the chat run that follows still sees the original order.
Parity: the same eligibility and policy rule on both channels. Gate: an email refund never
reaches an automatic write (its route is approval)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class ParityCase:
    case_id: str
    note: str
    customer_no: str
    message: str
    expect: dict[str, Any]


def load_parity(path: Path) -> list[ParityCase]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [
        ParityCase(r["id"], r["note"], r["customer_no"], r["message"], r["expect"]) for r in rows
    ]


def sender_for(customer_no: str, senders: dict[str, str]) -> str:
    matches = [addr for addr, no in senders.items() if no == customer_no]
    if not matches:
        raise ValueError(f"no registered sender for {customer_no}")
    return matches[0]


async def run_case(
    client: httpx.AsyncClient, case: ParityCase, senders: dict[str, str], run: str
) -> dict[str, Any]:
    message_id = f"<parity-{case.case_id}-{run}>"
    email = await client.post(
        "/v1/channels/email/inbound",
        json={
            "from_address": sender_for(case.customer_no, senders),
            "subject": case.message[:60],
            "body": case.message,
            "message_id": message_id,
        },
    )
    chat = await client.post(
        "/v1/chat/tickets", json={"customer_no": case.customer_no, "message": case.message}
    )
    email_view = email.json()
    chat_view = chat.json()
    return {
        "id": case.case_id,
        "note": case.note,
        "chat": _pick(chat_view),
        "email": _pick(email_view),
        "expected": case.expect,
    }


def _pick(view: dict[str, Any]) -> dict[str, Any]:
    keys = ("outcome", "route", "eligibility", "rule_id", "amount_paise")
    return {k: view.get(k) for k in keys}


def judge(result: dict[str, Any]) -> dict[str, bool]:
    chat, email, expected = result["chat"], result["email"], result["expected"]
    parity = chat["eligibility"] == email["eligibility"] and chat["rule_id"] == email["rule_id"]
    chat_ok = chat["route"] == expected["chat_route"]
    email_ok = email["route"] == expected["email_route"]
    email_gate = email["route"] != "auto"
    return {
        "parity": parity,
        "chat_route_ok": chat_ok,
        "email_route_ok": email_ok,
        "email_never_auto": email_gate,
        "correct": parity and chat_ok and email_ok and email_gate,
    }
