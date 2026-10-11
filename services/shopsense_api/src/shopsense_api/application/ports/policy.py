"""Policy ports: embeddings, the vector index (Qdrant) and the policy store (PostgreSQL)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from shopsense_api.domain.policy.chunks import PolicyChunk
from shopsense_api.domain.policy.model import PolicyDocument


@dataclass(frozen=True, slots=True)
class Hit:
    chunk: PolicyChunk
    score: float


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class PolicyIndex(Protocol):
    async def replace_document(
        self, doc_id: str, chunks: Sequence[PolicyChunk], vectors: Sequence[Sequence[float]]
    ) -> None: ...

    async def search(
        self, vector: Sequence[float], limit: int, category: str | None
    ) -> list[Hit]: ...


class PolicyStore(Protocol):
    async def document_hashes(self) -> dict[str, str]: ...

    async def save_document(self, doc: PolicyDocument) -> None: ...
