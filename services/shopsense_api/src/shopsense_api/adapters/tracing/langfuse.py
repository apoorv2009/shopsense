"""Langfuse adapter (M7-1): sends spans to the Langfuse public ingestion API when keys are set.

Only the masked event leaves the process (M7-2). Enabled by SHOPSENSE_LANGFUSE_HOST, _PUBLIC_KEY
and _SECRET_KEY; without them the ShopSense API uses the local JSONL tracer only."""

import base64
import uuid
from datetime import UTC, datetime

import httpx

from shopsense_api.application.ports.tracing import TraceEvent


class LangfuseTracer:
    def __init__(self, client: httpx.AsyncClient, public_key: str, secret_key: str) -> None:
        self._client = client
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode("ascii")
        self._headers = {"Authorization": f"Basic {token}"}

    async def record(self, event: TraceEvent) -> None:
        ended = datetime.now(UTC)
        batch = [
            {
                "id": str(uuid.uuid4()),
                "type": "span-create",
                "timestamp": ended.isoformat(),
                "body": {
                    "id": str(uuid.uuid4()),
                    "traceId": event.trace_id,
                    "name": event.name,
                    "startTime": event.started_at,
                    "endTime": ended.isoformat(),
                    "input": event.input,
                    "output": event.output,
                    "level": "ERROR" if event.status == "error" else "DEFAULT",
                    "statusMessage": event.error,
                },
            }
        ]
        response = await self._client.post(
            "/api/public/ingestion", json={"batch": batch}, headers=self._headers
        )
        response.raise_for_status()
