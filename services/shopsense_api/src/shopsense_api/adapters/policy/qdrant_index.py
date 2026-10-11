"""Qdrant policy index (LLD-3): one point per section chunk, cosine dense vectors.

Re-indexing a document deletes its points and upserts the new ones, so repeated ingestion
of the same content is safe. Point IDs derive from the chunk ID (deterministic)."""

import uuid
from collections.abc import Sequence

from qdrant_client import AsyncQdrantClient, models

from shopsense_api.application.ports.policy import Hit
from shopsense_api.domain.policy.chunks import ANY_CATEGORY, PolicyChunk

_NAMESPACE = uuid.UUID("6f1c2d4e-0b7a-4c1e-9d2a-5a8e3c7b9f10")


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
            vectors_config=models.VectorParams(size=self._dim, distance=models.Distance.COSINE),
        )

    async def replace_document(
        self, doc_id: str, chunks: Sequence[PolicyChunk], vectors: Sequence[Sequence[float]]
    ) -> None:
        await self.ensure_collection()
        await self._client.delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(filter=_doc_filter(doc_id)),
        )
        points = [
            models.PointStruct(id=_point_id(c.chunk_id), vector=list(v), payload=_payload(c))
            for c, v in zip(chunks, vectors, strict=True)
        ]
        if points:
            await self._client.upsert(collection_name=self._collection, points=points)

    async def search(self, vector: Sequence[float], limit: int, category: str | None) -> list[Hit]:
        query_filter = None
        if category is not None:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="categories",
                        match=models.MatchAny(any=[category, ANY_CATEGORY]),
                    )
                ]
            )
        result = await self._client.query_points(
            collection_name=self._collection,
            query=list(vector),
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        return [Hit(_chunk(p.payload or {}), float(p.score)) for p in result.points]


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
        rule_ids=tuple(str(x) for x in payload["rule_ids"]),  # type: ignore[attr-defined]
        categories=tuple(str(x) for x in payload["categories"]),  # type: ignore[attr-defined]
        content_hash=str(payload["content_hash"]),
    )
