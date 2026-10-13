"""Production entrypoint for the ShopSense API (M6): `uvicorn shopsense_api.entrypoints.api:app`.

The lifespan builds the container (model clients, Qdrant, database, MCP tools) and a PostgreSQL
connection pool for the checkpointer, then holds them for the life of the process. The pool
replaces broken connections, and the Entra token it authenticates with is refreshed before it
expires, so a dropped connection no longer breaks every chat request."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

import structlog
from azure.identity.aio import DefaultAzureCredential
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from shopsense_api.adapters.http.channels_api import create_app
from shopsense_api.adapters.policy.markdown_corpus import load_corpus
from shopsense_api.application.use_cases.drain_outbox import DrainOutbox
from shopsense_api.entrypoints.channels import load_senders
from shopsense_api.entrypoints.composition import container
from shopsense_api.entrypoints.settings import AuthMode, Settings
from shopsense_api.entrypoints.workflow_cli import checkpoint_conninfo

log = structlog.get_logger(__name__)

TOKEN_REFRESH_S = 25 * 60  # Entra access tokens last about an hour
POOL_MAX_LIFETIME_S = 40 * 60  # recycle connections before their token can expire


async def _refresh_token(pool_kwargs: dict[str, Any], settings: Settings) -> None:
    while True:
        await asyncio.sleep(TOKEN_REFRESH_S)
        async with DefaultAzureCredential() as credential:
            token = await credential.get_token(settings.db_token_scope)
        pool_kwargs["password"] = token.token


async def _drain_forever(drainer: DrainOutbox, interval: float) -> None:
    """Approved refunds are never dropped: a pass that fails is logged and retried next tick."""
    while True:
        try:
            await drainer.drain_pending()
        except Exception:
            log.warning("outbox drain pass failed", exc_info=True)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    corpus = load_corpus(Path(settings.policy_dir))
    conninfo = await checkpoint_conninfo(settings)
    async with container(settings) as services:
        pool_kwargs: dict[str, Any] = {
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        }
        pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] = AsyncConnectionPool(
            conninfo=conninfo,
            kwargs=pool_kwargs,
            min_size=1,
            max_size=5,
            max_lifetime=POOL_MAX_LIFETIME_S,
            check=AsyncConnectionPool.check_connection,
            open=False,
        )
        await pool.open(wait=True)
        refresh: asyncio.Task[None] | None = None
        try:
            saver = AsyncPostgresSaver(pool)
            await saver.setup()
            if settings.auth_mode is AuthMode.ENTRA:
                refresh = asyncio.create_task(_refresh_token(pool_kwargs, settings))
            drain: asyncio.Task[None] | None = None
            if settings.outbox_drain_interval_s > 0:
                drain = asyncio.create_task(
                    _drain_forever(services.drainer(), settings.outbox_drain_interval_s)
                )
            app.state.runner = services.ticket_runner(corpus, saver)
            app.state.senders = load_senders()
            yield
        finally:
            for task in (refresh, drain):
                if task is not None:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
            await pool.close()


app = create_app(lifespan, cors_origins=Settings().cors_origins)
