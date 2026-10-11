"""Policy documents as data (ADR-011, LLD-6). Frozen dataclasses; no I/O."""

import hashlib
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

ConditionValue = str | int | bool


class RuleKind(StrEnum):
    RETURN_WINDOW = "return_window"
    NOT_RETURNABLE = "not_returnable"
    EXCEPTION = "exception"
    WARRANTY = "warranty"
    REFUND_METHOD = "refund_method"
    REFUND_TIMELINE = "refund_timeline"
    CANCELLATION = "cancellation"
    GOODWILL = "goodwill"


class Outcome(StrEnum):
    RETURN = "return"
    REPLACEMENT_ONLY = "replacement_only"
    REPAIR_OR_REPLACE = "repair_or_replace"
    NOT_RETURNABLE = "not_returnable"
    ESCALATE = "escalate"


class Evidence(StrEnum):
    NONE = "none"
    PHOTO = "photo"


@dataclass(frozen=True, slots=True)
class PolicyRule:
    rule_id: str
    kind: RuleKind
    applies_to: dict[str, ConditionValue]
    window_days: int | None
    outcome: Outcome
    overrides: tuple[str, ...]
    evidence: Evidence
    doc_id: str
    section_id: str


@dataclass(frozen=True, slots=True)
class PolicySection:
    doc_id: str
    section_id: str
    title: str
    text: str
    rules: tuple[PolicyRule, ...] = field(default=())

    @property
    def chunk_id(self) -> str:
        return f"{self.doc_id}#{self.section_id}"

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PolicyDocument:
    doc_id: str
    title: str
    version: int
    effective_date: date
    sections: tuple[PolicySection, ...]
    content_hash: str
