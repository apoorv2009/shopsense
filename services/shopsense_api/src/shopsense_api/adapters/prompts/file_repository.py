"""Prompt repository backed by versioned files in application/prompts/<name>/v<N>.md."""

import re
from importlib import resources

from shopsense_api.application.ports.prompts import PromptTemplate

_VERSION_FILE = re.compile(r"^v(\d+)\.md$")
_PROMPTS_PACKAGE = "shopsense_api.application.prompts"


class FilePromptRepository:
    def __init__(self, pinned_versions: dict[str, str] | None = None) -> None:
        self._pinned = pinned_versions or {}
        self._cache: dict[str, PromptTemplate] = {}

    def get(self, name: str) -> PromptTemplate:
        if name not in self._cache:
            self._cache[name] = self._load(name)
        return self._cache[name]

    def _load(self, name: str) -> PromptTemplate:
        folder = resources.files(_PROMPTS_PACKAGE).joinpath(name)
        versions = sorted(
            int(m.group(1)) for item in folder.iterdir() if (m := _VERSION_FILE.match(item.name))
        )
        if not versions:
            raise FileNotFoundError(f"no prompt versions for {name!r}")
        version = self._pinned.get(name, f"v{versions[-1]}")
        text = folder.joinpath(f"{version}.md").read_text(encoding="utf-8")
        return PromptTemplate(name=name, version=version, text=text)
