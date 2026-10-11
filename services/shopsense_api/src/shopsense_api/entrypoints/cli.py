"""Command-line entrypoint for policy ingestion: `shopsense-ingest`.

Runs the shopsense migrations, then indexes the policy corpus. Unchanged documents are
skipped, so the command is safe to repeat (M3 acceptance: idempotent ingestion)."""

import argparse
import asyncio
from pathlib import Path

from shopsense_api.adapters.db.migrate import upgrade
from shopsense_api.adapters.policy.markdown_corpus import load_corpus
from shopsense_api.entrypoints.composition import container
from shopsense_api.entrypoints.settings import Settings


async def _ingest(settings: Settings, rebuild: bool) -> None:
    docs = load_corpus(Path(settings.policy_dir))
    async with container(settings) as c:
        if c.engine is None:
            raise SystemExit("SHOPSENSE_DATABASE_URL is not set")
        await upgrade(c.engine)
        report = await c.ingest_policies().run(docs, rebuild=rebuild)
    print(
        f"documents: {len(docs)} · indexed: {len(report.indexed_docs)} · "
        f"unchanged: {len(report.skipped_docs)} · chunks written: {report.chunks}"
    )
    for doc_id in report.indexed_docs:
        print(f"  indexed {doc_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index the policy corpus into Qdrant.")
    parser.add_argument("--rebuild", action="store_true", help="re-index every document")
    args = parser.parse_args()
    asyncio.run(_ingest(Settings(), rebuild=args.rebuild))


if __name__ == "__main__":
    main()
