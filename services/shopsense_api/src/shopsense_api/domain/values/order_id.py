"""Order reference value object (ORD- followed by six digits)."""

import re
from dataclasses import dataclass

from shopsense_api.domain.exceptions import InvalidOrderId

ORDER_ID_PATTERN = re.compile(r"^ORD-\d{6}$")


def normalise_order_id(raw: str) -> str:
    """Upper-case and trim; raise InvalidOrderId if the result is not ORD-123456."""
    candidate = raw.strip().upper()
    if not ORDER_ID_PATTERN.fullmatch(candidate):
        raise InvalidOrderId("order_id must look like ORD-123456")
    return candidate


@dataclass(frozen=True, slots=True)
class OrderId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", normalise_order_id(self.value))
