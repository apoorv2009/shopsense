"""ASGI entrypoint: uvicorn order_platform.entrypoints.api:app"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from order_platform.adapters.http.app import create_app
from order_platform.entrypoints.composition import Database, build_services
from order_platform.entrypoints.settings import Settings

_database = Database(Settings())


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await _database.aclose()


_token = Settings().admin_token
app = create_app(
    build_services(
        _database.engine,
        _token.get_secret_value() if _token else None,
        Settings().grant_key.get_secret_value().encode("utf-8"),
    ),
    lifespan=_lifespan,
)
