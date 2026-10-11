"""PII masking before anything is traced or logged (M7-2, D13).

Replaces emails, Indian mobile numbers, long digit runs (card, account, Aadhaar-like) and PAN
numbers with fixed tags. Deterministic and pure, so the same input always masks the same way."""

import re

_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[phone]"),
    (re.compile(r"(?<![\w-])\d(?:[ -]?\d){11,18}(?![\w-])"), "[number]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[pan]"),
)


def mask(text: str) -> str:
    for pattern, tag in _RULES:
        text = pattern.sub(tag, text)
    return text
