"""Customer memory port (PostgreSQL in production; in-memory in unit tests)."""

from typing import Protocol

from shopsense_api.domain.memory.model import CustomerPreferences, TicketRecord


class MemoryStore(Protocol):
    async def recent_tickets(self, customer_no: str, limit: int) -> list[TicketRecord]: ...

    async def add_ticket(self, record: TicketRecord) -> None: ...

    async def preferences(self, customer_no: str) -> CustomerPreferences | None: ...

    async def set_preferences(self, customer_no: str, prefs: CustomerPreferences) -> None: ...
