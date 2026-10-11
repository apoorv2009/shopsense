"""Wrap untrusted text in delimiter tags carrying a per-request random ID (L5d).

An attacker cannot close a tag whose ID they do not know, so ticket text cannot
escape its block. Any occurrence of the tag name inside the text is neutralised.
"""

import re
import secrets
from collections.abc import Callable

from shopsense_api.domain.values.untrusted_text import UntrustedText

BlockIdFactory = Callable[[], str]


def random_block_id() -> str:
    return secrets.token_hex(4)


def wrap_untrusted(tag: str, text: UntrustedText, block_id: str) -> str:
    neutralised = re.sub(rf"</?\s*{re.escape(tag)}\b", "[tag removed]", text.value, flags=re.I)
    return f'<{tag} id="{block_id}">\n{neutralised}\n</{tag} id="{block_id}">'
