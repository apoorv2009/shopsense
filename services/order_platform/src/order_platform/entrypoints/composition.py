"""Composition root for the Order Platform."""

import secrets
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from azure.core.credentials import AccessToken
from azure.identity.aio import DefaultAzureCredential
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from order_platform.adapters.db.repository import SqlUnitOfWork
from order_platform.adapters.http.app import Services
from order_platform.adapters.http.faults import FaultState
from order_platform.application.use_cases import (
    DecideRefund,
    OrderQueries,
    RequestRefund,
    RequestReplacement,
)
from order_platform.entrypoints.settings import DbAuth, Settings


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class RandomIds:
    def new(self, prefix: str) -> str:
        return f"{prefix}-{secrets.token_hex(5).upper()}"


class Database:
    """Engine plus the Entra credential it uses; close both with aclose()."""

    def __init__(self, settings: Settings) -> None:
        connect_args: dict[str, Any] = {}
        self._credential: DefaultAzureCredential | None = None
        if settings.db_auth is DbAuth.ENTRA:
            self._credential = DefaultAzureCredential()
            password = _entra_password(self._credential, settings.db_token_scope)
            connect_args = {"password": password, "ssl": "require"}
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url, connect_args=connect_args, pool_pre_ping=True
        )

    async def aclose(self) -> None:
        await self.engine.dispose()
        if self._credential is not None:
            await self._credential.close()


def build_services(
    engine: AsyncEngine, admin_token: str | None = None, grant_key: bytes = b""
) -> Services:
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    def uow() -> SqlUnitOfWork:
        return SqlUnitOfWork(sessions)

    clock, ids = SystemClock(), RandomIds()
    return Services(
        queries=OrderQueries(uow),
        refunds=RequestRefund(uow, clock, ids),
        replacements=RequestReplacement(uow, clock, ids),
        decisions=DecideRefund(uow, grant_key),
        faults=FaultState() if admin_token else None,
        admin_token=admin_token,
    )


def _entra_password(credential: DefaultAzureCredential, scope: str) -> Callable[[], Awaitable[str]]:
    """asyncpg accepts a coroutine function as password. Tokens are cached until five
    minutes before expiry: fetching one (e.g. via the Azure CLI) can take seconds."""
    cached: list[AccessToken] = []

    async def token() -> str:
        if not cached or cached[0].expires_on - time.time() < 300:
            cached[:] = [await credential.get_token(scope)]
        return cached[0].token

    return token
