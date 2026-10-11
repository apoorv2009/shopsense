"""Embeddings through Foundry's OpenAI-compatible endpoint (L3g: text-embedding-3-small)."""

from collections.abc import Sequence

from openai import AsyncOpenAI

BATCH_SIZE = 16


class FoundryEmbedder:
    def __init__(self, client: AsyncOpenAI, deployment: str) -> None:
        self._client = client
        self._deployment = deployment

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = list(texts[start : start + BATCH_SIZE])
            response = await self._client.embeddings.create(model=self._deployment, input=batch)
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(list(item.embedding) for item in ordered)
        return vectors
