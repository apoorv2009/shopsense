"""Grounding checks on generated text (M4 decision R4-6). Pure functions.

Numeric fabrication: every number in a reply must occur in the policy text it cites.
Sparse keyword vectors: deterministic hashed term weights for hybrid retrieval."""

import math
import re
import zlib
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_TERM = re.compile(r"[a-z0-9]+")
_STOP_WORDS = (
    "a an and are as at be but by can do does for from how i if in is it its my of on or so "
    "that the this to up was we what when with you your"
)
_STOP = frozenset(_STOP_WORDS.split())
SPARSE_SPACE = 2**20


@dataclass(frozen=True, slots=True)
class SparseVector:
    indices: tuple[int, ...]
    values: tuple[float, ...]


def numbers_in(text: str) -> set[str]:
    return {m.replace(",", "") for m in _NUMBER.findall(text)}


def unsupported_numbers(reply: str, sources: Iterable[str]) -> set[str]:
    allowed: set[str] = set()
    for source in sources:
        allowed |= numbers_in(source)
    return numbers_in(reply) - allowed


def encode_sparse(text: str) -> SparseVector:
    """Log-scaled term frequency over hashed terms (BM25 without IDF; documented in M4)."""
    terms = [t for t in _TERM.findall(text.lower()) if t not in _STOP and len(t) > 1]
    counts = Counter(zlib.crc32(t.encode("utf-8")) % SPARSE_SPACE for t in terms)
    ordered = sorted(counts)
    return SparseVector(
        indices=tuple(ordered),
        values=tuple(1.0 + math.log(counts[i]) for i in ordered),
    )
