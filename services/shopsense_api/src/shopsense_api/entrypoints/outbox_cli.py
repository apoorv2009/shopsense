"""Outbox worker (M7-6): `shopsense-outbox drain` sends pending approved writes once;
`shopsense-outbox drain --loop --interval 5` keeps draining until stopped."""

import argparse
import asyncio

from shopsense_api.application.use_cases.drain_outbox import DrainOutbox
from shopsense_api.entrypoints.composition import container
from shopsense_api.entrypoints.logging_config import configure_logging
from shopsense_api.entrypoints.settings import Settings


async def _drain(loop: bool, interval: float) -> None:
    # The worker sends writes only: it does not need the policy index (no Qdrant lock)
    async with container(Settings(), qdrant=False) as app:
        store = app.outbox_store()
        drainer = DrainOutbox(store, app.order_tools())
        while True:
            settled = await drainer.drain_pending()
            done = sum(item.status == "done" for item in settled)
            dead = sum(item.status == "dead" for item in settled)
            still = sum(item.status == "pending" for item in settled)
            print(f"drained {len(settled)}: done {done} · dead {dead} · still pending {still}")
            if not loop:
                return
            await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(prog="shopsense-outbox")
    sub = parser.add_subparsers(dest="command", required=True)
    drain = sub.add_parser("drain")
    drain.add_argument("--loop", action="store_true")
    drain.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()
    configure_logging(json=Settings().log_json)
    # psycopg's async mode needs the selector loop on Windows (see entrypoints/loop.py)
    asyncio.run(_drain(args.loop, args.interval), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
