"""Policy ingestion: validate the corpus, then index changed documents (LLD-3 re-index trigger).

Idempotent: a document whose content hash is unchanged is skipped. `rebuild=True` ignores the
stored hashes and re-indexes everything (used when the Qdrant collection is created)."""

from collections.abc import Sequence
from dataclasses import dataclass

from shopsense_api.application.ports.policy import Embedder, PolicyIndex, PolicyStore
from shopsense_api.domain.policy.chunks import chunks_for
from shopsense_api.domain.policy.grounding import encode_sparse
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

    async def run(self, docs: Sequence[PolicyDocument], *, rebuild: bool = False) -> IngestReport:
        validate_corpus(docs)
        known = {} if rebuild else await self._store.document_hashes()
        indexed: list[str] = []
        skipped: list[str] = []
        chunk_count = 0
        for doc in docs:
            if known.get(doc.doc_id) == doc.content_hash:
                skipped.append(doc.doc_id)
                continue
            chunks = chunks_for(doc)
            texts = [c.embed_text for c in chunks]
            dense = await self._embedder.embed(texts)
            sparse = [encode_sparse(t) for t in texts]
            await self._index.replace_document(doc.doc_id, chunks, dense, sparse)
            await self._store.save_document(doc)
            indexed.append(doc.doc_id)
            chunk_count += len(chunks)
        return IngestReport(tuple(indexed), tuple(skipped), chunk_count)
