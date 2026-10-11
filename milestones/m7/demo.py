"""M7 demo: an outage on the order system, as the customer and the reviewer experience it.

Steps: a refund waits for a reviewer, the order system goes down, a new chat ticket is parked for a
human, the reviewer approves during the outage (queued in the outbox, not lost), the outage ends,
the outbox worker settles the refund once, and the trace shows every step with PII masked.

Needs the three services running with ORDER_PLATFORM_ADMIN_TOKEN set on the Order Platform and in
this process's environment (see milestones/m7/README.md).

  uv run python milestones/m7/demo.py
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

API = os.environ.get("SHOPSENSE_API", "http://localhost:8000")
MCP = os.environ.get("SHOPSENSE_MCP", "http://localhost:8100")
ADMIN = os.environ.get("SHOPSENSE_ADMIN", "http://localhost:8001")
TOKEN = os.environ.get("ORDER_PLATFORM_ADMIN_TOKEN", "")
OUTAGE_S = 40
TRACE = Path("traces/shopsense.jsonl")


def heading(text: str) -> None:
    print(f"\n=== {text} ===")


async def breaker(mcp: httpx.AsyncClient) -> dict[str, Any]:
    return dict((await mcp.get("/health/breaker")).json())


async def main() -> None:
    if not TOKEN:
        raise SystemExit("set ORDER_PLATFORM_ADMIN_TOKEN")
    async with (
        httpx.AsyncClient(base_url=API, timeout=180) as api,
        httpx.AsyncClient(base_url=ADMIN, timeout=30) as admin,
        httpx.AsyncClient(base_url=MCP, timeout=30) as mcp,
    ):
        heading("1. Healthy: a refund from email waits for a reviewer")
        email = (
            await api.post(
                "/v1/channels/email/inbound",
                json={
                    "from_address": "vikram.singh@example.in",
                    "subject": "Shoes too small",
                    "body": "The smartwatch in ORD-100005 stopped working. Please refund it.",
                    "message_id": f"<m7-demo-{uuid.uuid4().hex[:8]}>",
                },
            )
        ).json()
        print(f"ticket {email.get('ticket_id')}: {email.get('outcome')} · {email.get('route')}")
        print(f"circuit breaker: {await breaker(mcp)}")

        heading("2. The order system goes down")
        headers = {"X-Admin-Token": TOKEN}
        await admin.post(
            "/admin/faults",
            json={"mode": "error", "rate": 1.0, "duration_s": OUTAGE_S},
            headers=headers,
        )
        started = time.monotonic()
        print(f"fault injected for {OUTAGE_S} s (it expires on its own)")

        heading("3. A new ticket during the outage is parked for a human")
        chat = (
            await api.post(
                "/v1/chat/tickets",
                json={
                    "customer_no": "C0003",
                    "message": "Please refund ORD-100004, it is leaking.",
                },
            )
        ).json()
        print(f"ticket {chat['ticket_id']}: {chat['outcome']}")
        print(f"reply: {chat['reply']}")
        print(f"circuit breaker: {await breaker(mcp)}")

        heading("4. The reviewer approves during the outage: queued, not lost")
        decided = (
            await api.post(
                f"/v1/tickets/{email['ticket_id']}/decision",
                json={"approve": True, "reviewer": "reviewer-demo"},
            )
        ).json()
        print(f"ticket {decided['ticket_id']}: {decided['outcome']}")
        print(f"reply: {decided['reply']}")

        heading("5. The outage ends; the outbox worker settles the refund")
        wait = OUTAGE_S - (time.monotonic() - started) + 2
        if wait > 0:
            await asyncio.sleep(wait)
        print(await asyncio.to_thread(run_worker))
        settled = (await api.get(f"/v1/tickets/{email['ticket_id']}")).json()
        print(f"ticket {settled['ticket_id']} after the worker: {settled['outcome']}")
        print(f"circuit breaker: {await breaker(mcp)}")

        heading("6. The trace: every step, PII masked")
        for line in await asyncio.to_thread(trace_tail):
            print(line)


def run_worker() -> str:
    worker = subprocess.run(
        [sys.executable, "-m", "shopsense_api.entrypoints.outbox_cli", "drain"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "SHOPSENSE_LOG_JSON": "false"},
    )
    return worker.stdout.strip() or worker.stderr.strip()


def trace_tail() -> list[str]:
    if not TRACE.exists():
        return ["no trace file yet"]
    lines = TRACE.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in lines[-12:]:
        event = json.loads(line)
        rows.append(
            f"{event['trace_id']:<18} {event['name']:<16} {event['status']:<6} "
            f"{event['duration_ms']:>8.1f} ms  {event['output']}"
        )
    rows.append(f"total spans recorded in {TRACE}: {len(lines)}")
    return rows


if __name__ == "__main__":
    asyncio.run(main())
