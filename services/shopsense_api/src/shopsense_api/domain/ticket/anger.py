"""A floor under triage's sentiment: strong anger in the words always counts as angry, so a
refund for an angry customer goes to a reviewer, whatever the model's label says."""

import re

_ANGER = re.compile(
    r"\b(disgust\w*|ridiculous|outrageous|furious|pathetic|unacceptable|horrible|terrible|"
    r"worst|useless|scam\w*|fraud\w*|cheat\w*|hate|idiot\w*)\b",
    re.IGNORECASE,
)


def is_angry_text(text: str) -> bool:
    return _ANGER.search(text) is not None
