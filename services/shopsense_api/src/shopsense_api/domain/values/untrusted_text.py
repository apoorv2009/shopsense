"""Text supplied by customers or tools. It may be shown to a model only inside
delimited blocks and can never be used where trusted text is expected."""

from dataclasses import dataclass

MAX_UNTRUSTED_CHARS = 8_000


@dataclass(frozen=True, slots=True)
class UntrustedText:
    value: str

    def __post_init__(self) -> None:
        if len(self.value) > MAX_UNTRUSTED_CHARS:
            object.__setattr__(self, "value", self.value[:MAX_UNTRUSTED_CHARS])

    def __str__(self) -> str:
        return "[untrusted text]"

    def __repr__(self) -> str:
        return f"UntrustedText(<{len(self.value)} chars>)"
