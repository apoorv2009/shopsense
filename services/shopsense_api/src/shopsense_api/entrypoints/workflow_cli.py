"""Ticket workflow CLI (M5): start a ticket, see where it is, resume it after a reviewer decides.

  shopsense-workflow start  --ticket TKT-1 --customer C0001 --message "..."
  shopsense-workflow status --ticket TKT-1
  shopsense-workflow resume --ticket TKT-1 --approve --reviewer name
  shopsense-workflow resume --ticket TKT-1 --reject  --reviewer name

Checkpoints live in the shopsense PostgreSQL database, so a paused ticket can be resumed
from a different process (the M5 checkpoint round-trip)."""

import argparse
import asyncio
from pathlib import Path

from azure.identity.aio import DefaultAzureCredential
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.engine import make_url

from shopsense_api.adapters.policy.markdown_corpus import load_corpus
from shopsense_api.adapters.workflow.runner import TicketView
from shopsense_api.entrypoints.composition import container
from shopsense_api.entrypoints.logging_config import configure_logging
from shopsense_api.entrypoints.settings import AuthMode, Settings


async def checkpoint_conninfo(settings: Settings) -> str:
    """libpq connection string for the checkpointer; the Entra token is the password (L3a)."""
    url = make_url(settings.database_url).set(drivername="postgresql")
    if settings.auth_mode is AuthMode.ENTRA:
        async with DefaultAzureCredential() as credential:
            token = (await credential.get_token(settings.db_token_scope)).token
        url = url.set(password=token)
    return url.update_query_dict({"sslmode": "require"}).render_as_string(hide_password=False)


def show(view: TicketView) -> None:
    print(f"ticket:  {view.ticket_id}")
    print(f"outcome: {view.outcome}")
    print(f"route:   {view.route}")
    if view.approval:
        print(f"waiting for a reviewer: {view.approval}")
    if view.reply:
        print(f"reply:   {view.reply}")


async def _run(args: argparse.Namespace) -> None:
    settings = Settings()
    conninfo = await checkpoint_conninfo(settings)
    corpus = load_corpus(Path(settings.policy_dir))
    async with (
        container(settings) as app,
        AsyncPostgresSaver.from_conn_string(conninfo) as saver,
    ):
        await saver.setup()
        runner = app.ticket_runner(corpus, saver)
        if args.command == "start":
            view = await runner.start(args.ticket, args.customer, args.message)
        elif args.command == "resume":
            view = await runner.resume(args.ticket, args.approve, args.reviewer)
        else:
            view = await runner.view(args.ticket)
    show(view)


def main() -> None:
    parser = argparse.ArgumentParser(prog="shopsense-workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--ticket", required=True)
    start.add_argument("--customer", required=True)
    start.add_argument("--message", required=True)
    status = sub.add_parser("status")
    status.add_argument("--ticket", required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("--ticket", required=True)
    decision = resume.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--reject", dest="approve", action="store_false")
    resume.add_argument("--reviewer", required=True)
    args = parser.parse_args()
    configure_logging(json=Settings().log_json)
    # psycopg's async mode needs the selector loop on Windows (not the default proactor loop)
    asyncio.run(_run(args), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
