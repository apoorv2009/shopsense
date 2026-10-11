"""Policy ports: embeddings, the vector index (Qdrant), the reranker and the policy store."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from shopsense_api.domain.policy.chunks import PolicyChunk
from shopsense_api.domain.policy.grounding import SparseVector
from shopsense_api.domain.policy.model import PolicyDocument, PolicyRule


@dataclass(frozen=True, slots=True)
class Hit:
    chunk: PolicyChunk
    score: float


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class PolicyIndex(Protocol):
    async def replace_document(
        self,
        doc_id: str,
        chunks: Sequence[PolicyChunk],
        dense: Sequence[Sequence[float]],
        sparse: Sequence[SparseVector],
    ) -> None: ...

    async def search_dense(
        self, vector: Sequence[float], limit: int, category: str | None
    ) -> list[Hit]: ...

    async def search_sparse(
        self, vector: SparseVector, limit: int, category: str | None
    ) -> list[Hit]: ...

    async def get_chunk(self, chunk_id: str) -> PolicyChunk | None: ...


class Reranker(Protocol):
    async def rerank(self, query: str, chunks: Sequence[PolicyChunk], top_n: int) -> list[Hit]: ...


class PolicyStore(Protocol):
    async def document_hashes(self) -> dict[str, str]: ...

    async def save_document(self, doc: PolicyDocument) -> None: ...

    async def rules(self) -> list[PolicyRule]: ...
