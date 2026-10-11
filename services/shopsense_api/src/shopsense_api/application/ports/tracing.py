"""Tracing port (M7-1). One event per workflow step; adapters decide where it goes."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class TraceEvent:
    trace_id: str
    name: str
    started_at: str
    duration_ms: float
    status: str
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Tracer(Protocol):
    async def record(self, event: TraceEvent) -> None: ...
