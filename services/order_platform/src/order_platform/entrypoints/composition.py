"""Composition root for the Order Platform."""

import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from azure.identity.aio import DefaultAzureCredential
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from order_platform.adapters.db.repository import SqlUnitOfWork
from order_platform.adapters.http.app import Services
from order_platform.application.use_cases import OrderQueries, RequestRefund, RequestReplacement
from order_platform.entrypoints.settings import DbAuth, Settings


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class RandomIds:
    def new(self, prefix: str) -> str:
        return f"{prefix}-{secrets.token_hex(5).upper()}"


def build_engine(settings: Settings) -> AsyncEngine:
    connect_args: dict[str, Any] = {}
    if settings.db_auth is DbAuth.ENTRA:
        connect_args = {"password": _entra_password(settings.db_token_scope), "ssl": "require"}
    return create_async_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


def build_services(engine: AsyncEngine) -> Services:
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    def uow() -> SqlUnitOfWork:
        return SqlUnitOfWork(sessions)

    clock, ids = SystemClock(), RandomIds()
    return Services(
        queries=OrderQueries(uow),
        refunds=RequestRefund(uow, clock, ids),
        replacements=RequestReplacement(uow, clock, ids),
    )


def _entra_password(scope: str) -> Callable[[], Awaitable[str]]:
    """asyncpg accepts a coroutine function as password: a fresh Entra token per connection."""
    credential = DefaultAzureCredential()

    async def token() -> str:
        return (await credential.get_token(scope)).token

    return token
