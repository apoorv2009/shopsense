"""Deterministic prompt-injection screen.

Runs independently of any model, so an injection that also fools the model is still
flagged. It never blocks a ticket; it raises a flag that routes the ticket to a human.
"""

import re

_PATTERNS = (
    r"ignore (all |any |the |your )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any |the |your )?(previous |prior |above |earlier )?"
    r"(instructions|rules|policy)",
    r"\byou are now\b",
    r"\b(system|developer) (prompt|message|override)\b",
    r"\bsystem override\b",
    r"\bpolicy checks? (are |is )?disabled\b",
    r"\bnote to (the )?(ai|assistant|bot|model)\b",
    r"\bnew instructions?\b",
    r"</?\s*(system|ticket|instructions?)\b",
    r"\bjailbreak\b|\bDAN mode\b",
)
_REGEX = re.compile("|".join(_PATTERNS), re.IGNORECASE)


def looks_like_injection(text: str) -> bool:
    return _REGEX.search(text) is not None
