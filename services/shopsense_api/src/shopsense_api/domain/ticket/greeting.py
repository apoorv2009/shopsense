"""Greetings are answered with a fixed reply and never reach the model (no LLM call, no handoff)."""

import re

_GREETING = re.compile(
    r"^\s*(hi+|hello+|hey+|helo|hiya|greetings|namaste|good (morning|afternoon|evening))"
    r"[\s!.,?]*((there|shopsense|support)[\s!.,?]*)?$",
    re.IGNORECASE,
)
GREETING_REPLY = (
    "Hello! How can I help you today? Please tell me about your order or your question."
)
_MAX_GREETING_CHARS = 40


def is_greeting(text: str) -> bool:
    return len(text) <= _MAX_GREETING_CHARS and _GREETING.match(text) is not None
