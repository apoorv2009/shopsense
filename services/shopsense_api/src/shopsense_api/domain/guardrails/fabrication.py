"""Fabrication guard on customer replies (M8-5). Pure.

A number in a reply must come from a source we hold: the policy corpus, the customer's message,
or the order record (amounts are also readable in rupees). Day counts that the code computed are
allowed only in a sentence about elapsed time ("passed", "ago", "closed"). Anything else is
fabricated, and the reply is replaced by a hand-off.
"""

import re

from shopsense_api.domain.policy.grounding import numbers_in

_DAY_COUNT = re.compile(
    r"(\d+)\s+days?\s+(?:have\s+passed|ago|closed)|closed\s+(\d+)\s+days?", re.I
)
_ELAPSED_WORDS = re.compile(r"passed|ago|closed", re.I)


def rupee_forms(numbers: set[str]) -> set[str]:
    """Each paise amount also as rupees, so 149900 supports the reply's 1499."""
    out = set(numbers)
    for value in numbers:
        if value.isdigit() and int(value) % 100 == 0:
            out.add(str(int(value) // 100))
    return out


def unsupported(reply: str, allowed: set[str]) -> set[str]:
    computed = {m.group(1) or m.group(2) for m in _DAY_COUNT.finditer(reply)}
    if _ELAPSED_WORDS.search(reply):
        computed |= {str(n) for n in range(0, 366)}
    return numbers_in(reply) - allowed - computed
