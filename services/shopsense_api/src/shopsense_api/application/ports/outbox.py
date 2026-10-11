"""Outbox port (M7-6, LLD-3). Approved writes are recorded before they are sent, so an approval
is never lost to a timeout or an outage. A worker drains pending items until they settle."""

from dataclasses import dataclass, field
from typing import Any, Protocol

PENDING, DONE, DEAD = "pending", "done", "dead"


@dataclass(frozen=True, slots=True)
class OutboxItem:
    key: str
    ticket_id: str
    action: str
    payload: dict[str, Any]
    status: str = PENDING
    attempts: int = 0
    last_error: str | None = None
    result: dict[str, Any] = field(default_factory=dict)


class OutboxStore(Protocol):
    async def enqueue(self, item: OutboxItem) -> None:
        """Insert if the key is new; an existing key is left alone (idempotent)."""
        ...

    async def get(self, key: str) -> OutboxItem | None: ...

    async def pending(self, limit: int) -> list[OutboxItem]: ...

    async def for_ticket(self, ticket_id: str) -> list[OutboxItem]: ...

    async def update(self, item: OutboxItem) -> None: ...
