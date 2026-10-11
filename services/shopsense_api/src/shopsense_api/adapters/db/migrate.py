"""Schema management for the shopsense database through Alembic migrations (LLD-3 L3a)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine

from shopsense_api.adapters.db.shopsense_tables import ShopSenseBase

MIGRATIONS = Path(__file__).parent / "migrations"


def _config(connection: Connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.attributes["connection"] = connection
    return config


async def upgrade(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: command.upgrade(_config(sync), "head"))


async def reset(engine: AsyncEngine) -> None:
    """Drop every table (data loss: development and evaluation databases only)."""
    async with engine.begin() as conn:
        await conn.run_sync(ShopSenseBase.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


async def autogenerate(engine: AsyncEngine, message: str) -> None:
    """Write a new revision from the difference between the models and the database."""
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync: command.revision(_config(sync), message=message, autogenerate=True)
        )
