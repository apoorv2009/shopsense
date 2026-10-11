"""Local cross-encoder reranker (M4 decision R4-3; L6f fallback): fastembed ONNX model.

The model loads on first use, in a worker thread, so the event loop is never blocked."""

import asyncio
from collections.abc import Sequence
from typing import Any

from shopsense_api.application.ports.policy import Hit
from shopsense_api.domain.policy.chunks import PolicyChunk


class FastEmbedReranker:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any = None

    async def rerank(self, query: str, chunks: Sequence[PolicyChunk], top_n: int) -> list[Hit]:
        if not chunks:
            return []
        docs = [c.embed_text for c in chunks]
        scores = await asyncio.to_thread(self._score, query, docs)
        ranked = sorted(zip(chunks, scores, strict=True), key=lambda p: p[1], reverse=True)
        return [Hit(chunk, float(score)) for chunk, score in ranked[:top_n]]

    def _score(self, query: str, docs: list[str]) -> list[float]:
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._model = TextCrossEncoder(model_name=self._model_name)
        return [float(s) for s in self._model.rerank(query, docs)]
