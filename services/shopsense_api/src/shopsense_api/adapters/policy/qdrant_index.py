"""Qdrant policy index (LLD-3): one point per section chunk with named dense and sparse vectors.

Re-indexing a document deletes its points and upserts the new ones, so repeated ingestion
of the same content is safe. Point IDs derive from the chunk ID (deterministic)."""

import uuid
from collections.abc import Sequence

from qdrant_client import AsyncQdrantClient, models

from shopsense_api.application.ports.policy import Hit
from shopsense_api.domain.policy.chunks import ANY_CATEGORY, PolicyChunk
from shopsense_api.domain.policy.grounding import SparseVector

_NAMESPACE = uuid.UUID("6f1c2d4e-0b7a-4c1e-9d2a-5a8e3c7b9f10")
DENSE = "dense"
SPARSE = "sparse"


class QdrantPolicyIndex:
    def __init__(self, client: AsyncQdrantClient, collection: str, dim: int) -> None:
        self._client = client
        self._collection = collection
        self._dim = dim

    async def ensure_collection(self) -> None:
        if await self._client.collection_exists(self._collection):
            return
        await self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                DENSE: models.VectorParams(size=self._dim, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={SPARSE: models.SparseVectorParams()},
        )

    async def replace_document(
        self,
        doc_id: str,
        chunks: Sequence[PolicyChunk],
        dense: Sequence[Sequence[float]],
        sparse: Sequence[SparseVector],
    ) -> None:
        await self.ensure_collection()
        await self._client.delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(filter=_doc_filter(doc_id)),
        )
        points = [
            models.PointStruct(
                id=_point_id(c.chunk_id),
                vector={DENSE: list(d), SPARSE: _sparse(s)},
                payload=_payload(c),
            )
            for c, d, s in zip(chunks, dense, sparse, strict=True)
        ]
        if points:
            await self._client.upsert(collection_name=self._collection, points=points)

    async def search_dense(
        self, vector: Sequence[float], limit: int, category: str | None
    ) -> list[Hit]:
        return await self._query(list(vector), DENSE, limit, category)

    async def search_sparse(
        self, vector: SparseVector, limit: int, category: str | None
    ) -> list[Hit]:
        if not vector.indices:
            return []
        return await self._query(_sparse(vector), SPARSE, limit, category)

    async def get_chunk(self, chunk_id: str) -> PolicyChunk | None:
        points = await self._client.retrieve(
            collection_name=self._collection,
            ids=[_point_id(chunk_id)],
            with_payload=True,
        )
        return _chunk(points[0].payload or {}) if points else None

    async def _query(
        self,
        query: list[float] | models.SparseVector,
        using: str,
        limit: int,
        category: str | None,
    ) -> list[Hit]:
        result = await self._client.query_points(
            collection_name=self._collection,
            query=query,
            using=using,
            limit=limit,
            query_filter=_category_filter(category),
            with_payload=True,
        )
        return [Hit(_chunk(p.payload or {}), float(p.score)) for p in result.points]


def _category_filter(category: str | None) -> models.Filter | None:
    if category is None:
        return None
    return models.Filter(
        must=[
            models.FieldCondition(
                key="categories", match=models.MatchAny(any=[category, ANY_CATEGORY])
            )
        ]
    )


def _sparse(vector: SparseVector) -> models.SparseVector:
    return models.SparseVector(indices=list(vector.indices), values=list(vector.values))


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, chunk_id))


def _doc_filter(doc_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
    )


def _payload(chunk: PolicyChunk) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "section_id": chunk.section_id,
        "title": chunk.title,
        "text": chunk.text,
        "rule_ids": list(chunk.rule_ids),
        "categories": list(chunk.categories),
        "content_hash": chunk.content_hash,
    }


def _chunk(payload: dict[str, object]) -> PolicyChunk:
    return PolicyChunk(
        chunk_id=str(payload["chunk_id"]),
        doc_id=str(payload["doc_id"]),
        section_id=str(payload["section_id"]),
        title=str(payload["title"]),
        text=str(payload["text"]),
        rule_ids=tuple(str(x) for x in _list(payload["rule_ids"])),
        categories=tuple(str(x) for x in _list(payload["categories"])),
        content_hash=str(payload["content_hash"]),
    )


def _list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []
