"""Money as an integer number of paise. Never float, never Decimal."""

from dataclasses import dataclass
from typing import Self

from shopsense_api.domain.exceptions import InvalidMoney

PAISE_PER_RUPEE = 100


@dataclass(frozen=True, slots=True, order=True)
class Money:
    paise: int
    currency: str = "INR"

    def __post_init__(self) -> None:
        if isinstance(self.paise, bool) or not isinstance(self.paise, int):
            raise InvalidMoney("amount must be an integer number of paise")
        if self.paise < 0:
            raise InvalidMoney("amount cannot be negative")
        if self.currency != "INR":
            raise InvalidMoney("only INR is supported")

    @classmethod
    def from_rupees(cls, rupees: int) -> Self:
        return cls(rupees * PAISE_PER_RUPEE)

    def __add__(self, other: "Money") -> "Money":
        return Money(self.paise + other.paise, self.currency)

    def format(self) -> str:
        rupees, paise = divmod(self.paise, PAISE_PER_RUPEE)
        return f"₹{rupees:,}.{paise:02d}"
