"""Policy search (M3): dense retrieval over policy sections, optionally filtered by category."""

from dataclasses import dataclass

from shopsense_api.application.ports.policy import Embedder, Hit, PolicyIndex


@dataclass(frozen=True, slots=True)
class SearchPolicy:
    embedder: Embedder
    index: PolicyIndex

    async def run(self, query: str, limit: int = 4, category: str | None = None) -> list[Hit]:
        [vector] = await self.embedder.embed([query])
        return await self.index.search(vector, limit, category)
