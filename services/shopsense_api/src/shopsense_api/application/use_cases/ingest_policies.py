"""Policy ingestion (M3): validate the corpus, then index changed documents only.

Idempotent: a document whose content hash is unchanged is skipped (LLD-3 re-index trigger)."""

from collections.abc import Sequence
from dataclasses import dataclass

from shopsense_api.application.ports.policy import Embedder, PolicyIndex, PolicyStore
from shopsense_api.domain.policy.chunks import chunks_for
from shopsense_api.domain.policy.model import PolicyDocument
from shopsense_api.domain.policy.validation import validate_corpus


@dataclass(frozen=True, slots=True)
class IngestReport:
    indexed_docs: tuple[str, ...]
    skipped_docs: tuple[str, ...]
    chunks: int


class IngestPolicies:
    def __init__(self, store: PolicyStore, index: PolicyIndex, embedder: Embedder) -> None:
        self._store = store
        self._index = index
        self._embedder = embedder

    async def run(self, docs: Sequence[PolicyDocument]) -> IngestReport:
        validate_corpus(docs)
        known = await self._store.document_hashes()
        indexed: list[str] = []
        skipped: list[str] = []
        chunk_count = 0
        for doc in docs:
            if known.get(doc.doc_id) == doc.content_hash:
                skipped.append(doc.doc_id)
                continue
            chunks = chunks_for(doc)
            vectors = await self._embedder.embed([c.embed_text for c in chunks])
            await self._index.replace_document(doc.doc_id, chunks, vectors)
            await self._store.save_document(doc)
            indexed.append(doc.doc_id)
            chunk_count += len(chunks)
        return IngestReport(tuple(indexed), tuple(skipped), chunk_count)
