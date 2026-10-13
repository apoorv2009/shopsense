"""Words that mark a customer message as a policy question about delivery, returns or payment."""

import re

_POLICY_WORDS = re.compile(
    r"\b(deliver|delivers|delivery|deliveries|ship|shipping|return|returns|refund|refunds|"
    r"warranty|pin ?code|cash on delivery|serviceable|available in)\b",
    re.IGNORECASE,
)


def is_policy_shaped(message: str) -> bool:
    return _POLICY_WORDS.search(message) is not None
