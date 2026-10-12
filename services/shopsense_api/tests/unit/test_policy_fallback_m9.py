"""A slow or failing reranker must not stop a policy answer: the search uses hybrid order."""

import asyncio
from typing import Any

from test_policy_m3 import HashingEmbedder, corpus, index_with

from shopsense_api.application.use_cases import hybrid_search
from shopsense_api.application.use_cases.hybrid_search import HybridSearch


class HangingReranker:
    async def rerank(self, query: str, chunks: Any, top_n: int) -> Any:
        await asyncio.sleep(3600)


class BrokenReranker:
    async def rerank(self, query: str, chunks: Any, top_n: int) -> Any:
        raise RuntimeError("model could not be loaded")


async def test_hanging_reranker_falls_back_to_hybrid_order(monkeypatch: Any) -> None:
    monkeypatch.setattr(hybrid_search, "RERANK_TIMEOUT_S", 0.2)
    index = await index_with(corpus())
    hits = await HybridSearch(HashingEmbedder(), index, HangingReranker()).run(
        "how long is the return window", limit=4
    )
    assert hits


async def test_failing_reranker_falls_back_to_hybrid_order() -> None:
    index = await index_with(corpus())
    hits = await HybridSearch(HashingEmbedder(), index, BrokenReranker()).run(
        "how long is the return window", limit=4
    )
    assert hits
