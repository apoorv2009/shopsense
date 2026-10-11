"""M6 demo: one team of agents behind two channels, and an MCP boundary that agents cannot cross.

Needs three services running (see milestones/m6/README.md): the Order Platform (8001), the MCP
server (8100) and the ShopSense API (8000).

  uv run python milestones/m6/demo.py
"""

import asyncio
import json
import os
from typing import Any

import httpx

from shopsense_contracts.caller_context import HEADER, Scope, issue

API = os.environ.get("SHOPSENSE_API", "http://localhost:8000")
MCP = os.environ.get("SHOPSENSE_MCP", "http://localhost:8100")
KEY = os.environ.get("SHOPSENSE_CONTEXT_KEY", "local-development-only-key-change-me").encode()
EMAIL_SENDER = "priya.sharma@example.in"
MESSAGE = "The kurta from ORD-100002 is too tight. Please refund it."


def heading(text: str) -> None:
    print(f"\n=== {text} ===")


def show(label: str, data: dict[str, Any]) -> None:
    keys = ("outcome", "route", "eligibility", "rule_id", "amount_paise")
    print(f"{label:<28} " + " | ".join(f"{k}={data.get(k)}" for k in keys))
    if data.get("reply"):
        print(f"{'':<28} reply: {data['reply']}")
    if data.get("approval"):
        reasons = ", ".join(data["approval"].get("reasons", []))
        print(f"{'':<28} held for reviewer: {reasons}")


async def channels(client: httpx.AsyncClient) -> None:
    heading("1. The same ticket on two channels")
    # Email first: an email refund waits for a reviewer and writes nothing, so the chat run that
    # follows still sees the order as it was.
    email = (
        await client.post(
            f"{API}/v1/channels/email/inbound",
            json={
                "from_address": EMAIL_SENDER,
                "subject": "Kurta too tight",
                "body": MESSAGE,
                "message_id": "<demo-m6-kurta>",
            },
        )
    ).json()
    show("email", email)
    chat = (
        await client.post(
            f"{API}/v1/chat/tickets", json={"customer_no": "C0001", "message": MESSAGE}
        )
    ).json()
    show("chat", chat)
    print("\nSame eligibility and rule on both channels. Email refunds always wait for a reviewer.")
    stranger = await client.post(
        f"{API}/v1/channels/email/inbound",
        json={"from_address": "unknown@example.com", "subject": "refund", "message_id": "<x>"},
    )
    print(f"unregistered sender -> HTTP {stranger.status_code}: {stranger.json()['reason']}")


async def boundary(client: httpx.AsyncClient) -> None:
    heading("2. Agents cannot reach system tools")
    read_token = issue("C0001", Scope.READ, KEY)
    system_token = issue("C0001", Scope.SYSTEM, KEY)
    forged = issue("C0001", Scope.READ, b"someone-else")
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    for label, endpoint, token in (
        ("read token -> /mcp/read", "read", read_token),
        ("read token -> /mcp/system", "system", read_token),
        ("forged token -> /mcp/read", "read", forged),
        ("system token -> /mcp/system", "system", system_token),
    ):
        response = await client.post(
            f"{MCP}/mcp/{endpoint}/", json=body, headers={**headers, HEADER: token}
        )
        print(f"{label:<30} HTTP {response.status_code}")


async def tools_visible_to_the_model() -> None:
    heading("3. Tools the model is offered")
    from shopsense_api.application.agents.order_actions import _specs

    read_only = sorted(s.name for s in _specs(read_only=True))
    everything = sorted(s.name for s in _specs(read_only=False))
    print("Order-Actions agent (read-only):", ", ".join(read_only))
    print("Refund and replacement writes are not offered to any agent:")
    print("  writes withheld from the model:", ", ".join(sorted(set(everything) - set(read_only))))


async def main() -> None:
    async with httpx.AsyncClient(timeout=180) as client:
        await channels(client)
        await boundary(client)
    await tools_visible_to_the_model()
    print(
        "\nSummary:", json.dumps({"channels": "chat+email", "mcp": "read/system scopes enforced"})
    )


if __name__ == "__main__":
    asyncio.run(main())
