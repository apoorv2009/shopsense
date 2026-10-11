"""Deterministic prompt-injection screen.

Runs independently of any model, so an injection that also fools the model is still
flagged. It never blocks a ticket; it raises a flag that routes the ticket to a human.
"""

import re

_PATTERNS = (
    # "ignore your rules", "ignore all previous instructions", "forget the policy", ...
    r"\b(ignore|disregard|forget|bypass|override|skip)\s+(all\s+|any\s+|the\s+|your\s+|these\s+"
    r"|those\s+|previous\s+|prior\s+|above\s+|earlier\s+|system\s+)*(\w+\s+){0,2}"
    r"(instructions?|rules?|prompts?|polic(y|ies)|guidelines?|checks?|limits?|commands?)\b",
    # claims that the request is already authorised: "it is approved", "pre-approved"
    r"\b(it\s+is|it's|this\s+is)\s+(already\s+)?(pre-?)?approved\b",
    r"\b(pre-?approved|auto-?approve\s+(it|this|my))\b",
    r"\byou are now\b",
    r"\b(system|developer) (prompt|message|override)\b",
    r"\bsystem override\b",
    # fake role markers inside customer text, e.g. "SYSTEM: refund approved"
    r"(^|[\s.!?,;])(system|admin|administrator|developer|assistant|supervisor)\s*:",
    r"\bas per (your |the )?new policy\b",
    r"\bpolicy checks? (are |is )?disabled\b",
    r"\bnote to (the )?(ai|assistant|bot|model)\b",
    r"\bnew instructions?\b",
    r"</?\s*(system|ticket|instructions?)\b",
    r"\bjailbreak\b|\bDAN mode\b",
)
_REGEX = re.compile("|".join(_PATTERNS), re.IGNORECASE)


def looks_like_injection(text: str) -> bool:
    return _REGEX.search(text) is not None
