"""Deterministic product-safety screen.

Product-safety reports have zero-tolerance recall (D14b), so they must not depend on
the model alone. False positives only route a ticket to a human, which is the safe side.
"""

import re

_PATTERNS = (
    r"\b(burn(t|ed|s|ing)?|scald(ed)?|fire|caught fire|flames?|smoke|smoking|sparks?|sparking)\b",
    r"\b(overheat(s|ed|ing)?|explod(e|ed|es|ing)|exploded|blew (up|off)|bursts?|burst)\b",
    r"\b(electric shock|electrocut\w*|short circuit)\b",
    r"\b(rash(es)?|skin (reaction|irritation|burn)|allerg(y|ic|ies)|swelling|hives|itching)\b",
    r"\b(chok(e|ed|ing)|injur(y|ed|ies)|hospital|doctor|bleeding|cut my)\b",
    r"\b(jal gaya|aag lag|chot lag)\b",
)
_REGEX = re.compile("|".join(_PATTERNS), re.IGNORECASE)


def looks_like_safety_report(text: str) -> bool:
    return _REGEX.search(text) is not None
