"""Local trace store: one masked JSON line per workflow step, appended to a file. Always on."""

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from shopsense_api.application.ports.tracing import TraceEvent


class JsonlTracer:
    def __init__(self, path: Path) -> None:
        self._path = path

    async def record(self, event: TraceEvent) -> None:
        line = json.dumps(asdict(event), ensure_ascii=False, default=str)
        await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
