"""Retrieval chunks: one per policy section, with the document title prefixed (LLD-3)."""

from dataclasses import dataclass

from shopsense_api.domain.policy.model import PolicyDocument, PolicySection

ANY_CATEGORY = "*"


@dataclass(frozen=True, slots=True)
class PolicyChunk:
    chunk_id: str
    doc_id: str
    section_id: str
    title: str
    text: str
    rule_ids: tuple[str, ...]
    categories: tuple[str, ...]
    content_hash: str

    @property
    def embed_text(self) -> str:
        return f"{self.title}\n{self.text}"


def chunk_for(doc: PolicyDocument, section: PolicySection) -> PolicyChunk:
    categories = sorted(
        {str(r.applies_to["category"]) for r in section.rules if "category" in r.applies_to}
    )
    return PolicyChunk(
        chunk_id=section.chunk_id,
        doc_id=doc.doc_id,
        section_id=section.section_id,
        title=f"{doc.title} — {section.title}",
        text=section.text,
        rule_ids=tuple(r.rule_id for r in section.rules),
        categories=tuple(categories) or (ANY_CATEGORY,),
        content_hash=section.content_hash,
    )


def chunks_for(doc: PolicyDocument) -> list[PolicyChunk]:
    return [chunk_for(doc, section) for section in doc.sections]
