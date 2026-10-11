"""Markdown policy corpus (adapter): front matter, numbered sections and rules blocks (LLD-6).

A document is a markdown file with YAML-style front matter. Each `## N. Title` section holds
prose and optionally a fenced `rules` block whose JSON is validated here at the edge."""

import hashlib
import json
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from shopsense_api.domain.policy.model import (
    ConditionValue,
    Evidence,
    Outcome,
    PolicyDocument,
    PolicyRule,
    PolicySection,
    RuleKind,
)

REQUIRED_META = ("doc_id", "title", "version", "effective_date")
_FENCE = re.compile(r"^```rules\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
_SECTION = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)


class PolicyFormatError(ValueError):
    """A policy file does not follow the document format."""


class RuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    rule_id: str
    kind: RuleKind
    applies_to: dict[str, ConditionValue]
    window_days: int | None
    outcome: Outcome
    overrides: list[str]
    requires_evidence: Evidence


def load_corpus(directory: Path) -> list[PolicyDocument]:
    return [parse_document(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.md"))]


def parse_document(text: str) -> PolicyDocument:
    meta, body = _front_matter(text)
    doc_id = meta["doc_id"]
    return PolicyDocument(
        doc_id=doc_id,
        title=meta["title"],
        version=int(meta["version"]),
        effective_date=date.fromisoformat(meta["effective_date"]),
        sections=tuple(_sections(doc_id, body)),
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise PolicyFormatError("missing front matter")
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        raise PolicyFormatError("unterminated front matter")
    meta = {k.strip(): v.strip() for k, _, v in (line.partition(":") for line in head.splitlines())}
    missing = [key for key in REQUIRED_META if key not in meta]
    if missing:
        raise PolicyFormatError(f"front matter lacks {missing}")
    return meta, body


def _sections(doc_id: str, body: str) -> Iterator[PolicySection]:
    matches = list(_SECTION.finditer(body))
    if not matches:
        raise PolicyFormatError(f"{doc_id} has no numbered sections")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        raw = body[match.end() : end]
        number, title = match.group(1), match.group(2).strip()
        yield PolicySection(
            doc_id=doc_id,
            section_id=number,
            title=title,
            text=_FENCE.sub("", raw).strip(),
            rules=tuple(_rules(doc_id, number, raw)),
        )


def _rules(doc_id: str, number: str, raw: str) -> Iterator[PolicyRule]:
    for block in _FENCE.findall(raw):
        try:
            items = [RuleIn.model_validate(item) for item in json.loads(block)]
        except (json.JSONDecodeError, ValidationError) as exc:
            raise PolicyFormatError(f"{doc_id} section {number}: {exc}") from exc
        for item in items:
            yield PolicyRule(
                rule_id=item.rule_id,
                kind=item.kind,
                applies_to=dict(item.applies_to),
                window_days=item.window_days,
                outcome=item.outcome,
                overrides=tuple(item.overrides),
                evidence=item.requires_evidence,
                doc_id=doc_id,
                section_id=number,
            )
