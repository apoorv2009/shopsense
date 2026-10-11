"""Fans one trace event out to several tracers. A failing tracer never blocks the others."""

import logging

from shopsense_api.application.ports.tracing import TraceEvent, Tracer

log = logging.getLogger(__name__)


class CompositeTracer:
    def __init__(self, *tracers: Tracer) -> None:
        self._tracers = tracers

    async def record(self, event: TraceEvent) -> None:
        for tracer in self._tracers:
            try:
                await tracer.record(event)
            except Exception:
                log.warning("trace sink failed", exc_info=True)
