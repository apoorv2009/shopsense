"""Policy retrieval (M4): dense, hybrid (dense + sparse fused with reciprocal rank fusion) and
hybrid with reranking. The three modes are compared on the same questions in the evaluation.

Reciprocal rank fusion: score(chunk) = sum over rankings of 1 / (k + rank), k = 60."""

import asyncio
from dataclasses import dataclass
from typing import Literal

from shopsense_api.application.ports.policy import Embedder, Hit, PolicyIndex, Reranker
from shopsense_api.domain.policy.chunks import PolicyChunk
from shopsense_api.domain.policy.grounding import encode_sparse

Mode = Literal["dense", "hybrid", "hybrid_rerank"]
RRF_K = 60
CANDIDATES = 20
RERANK_POOL = 20


def reciprocal_rank_fusion(rankings: list[list[Hit]], k: int = RRF_K) -> list[Hit]:
    scores: dict[str, float] = {}
    chunks: dict[str, PolicyChunk] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            cid = hit.chunk.chunk_id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            chunks.setdefault(cid, hit.chunk)
    order = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [Hit(chunks[cid], scores[cid]) for cid in order]


@dataclass(frozen=True, slots=True)
class HybridSearch:
    embedder: Embedder
    index: PolicyIndex
    reranker: Reranker | None = None

    async def run(
        self, query: str, limit: int = 4, category: str | None = None, mode: Mode = "hybrid_rerank"
    ) -> list[Hit]:
        [dense_vector] = await self.embedder.embed([query])
        if mode == "dense":
            return await self.index.search_dense(dense_vector, limit, category)
        dense, sparse = await asyncio.gather(
            self.index.search_dense(dense_vector, CANDIDATES, category),
            self.index.search_sparse(encode_sparse(query), CANDIDATES, category),
        )
        fused = reciprocal_rank_fusion([dense, sparse])
        if mode == "hybrid":
            return fused[:limit]
        if self.reranker is None:
            raise RuntimeError("hybrid_rerank needs a reranker")
        return await self.reranker.rerank(query, [h.chunk for h in fused[:RERANK_POOL]], limit)
