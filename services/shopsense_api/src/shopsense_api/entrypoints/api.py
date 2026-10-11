"""Production entrypoint for the ShopSense API (M6): `uvicorn shopsense_api.entrypoints.api:app`.

The lifespan builds the container (model clients, Qdrant, database, MCP tools) and the
PostgreSQL checkpointer, then holds them for the life of the process."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from shopsense_api.adapters.http.channels_api import create_app
from shopsense_api.adapters.policy.markdown_corpus import load_corpus
from shopsense_api.entrypoints.channels import load_senders
from shopsense_api.entrypoints.composition import container
from shopsense_api.entrypoints.settings import Settings
from shopsense_api.entrypoints.workflow_cli import checkpoint_conninfo


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    corpus = load_corpus(Path(settings.policy_dir))
    conninfo = await checkpoint_conninfo(settings)
    async with (
        container(settings) as services,
        AsyncPostgresSaver.from_conn_string(conninfo) as saver,
    ):
        await saver.setup()
        app.state.runner = services.ticket_runner(corpus, saver)
        app.state.senders = load_senders()
        yield


app = create_app(lifespan)
