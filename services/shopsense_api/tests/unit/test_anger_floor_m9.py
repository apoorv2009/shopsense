"""Strong anger in the words always counts as angry, so the refund goes to a reviewer."""

import pytest

from shopsense_api.domain.ticket.anger import is_angry_text


@pytest.mark.parametrize(
    "text",
    ["Absolutely disgusted with this", "This is ridiculous", "worst service ever", "it's a scam"],
)
def test_strong_anger_words_are_detected(text: str) -> None:
    assert is_angry_text(text)


@pytest.mark.parametrize("text", ["My mixer stopped working", "Please refund ORD-100012", "Thanks"])
def test_neutral_text_is_not_flagged(text: str) -> None:
    assert not is_angry_text(text)
