"""Prompt repository port. Prompts are versioned files reviewed in pull requests (L2e)."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    name: str
    version: str
    text: str


class PromptRepository(Protocol):
    def get(self, name: str) -> PromptTemplate:
        """Return the current version of the named prompt."""
        ...
