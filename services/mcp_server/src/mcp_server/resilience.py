"""Circuit breaker for calls to the Order Platform (M7-4, LLD-4 L4f).

Closed: calls flow. Open after `threshold` consecutive retryable failures: calls fail fast for
`open_s` seconds. Half-open after that: one probe is let through; success closes the breaker,
failure opens it again. Business refusals (for example NOT_FOUND) count as success because the
order system answered."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

State = Literal["closed", "open", "half_open"]


@dataclass(slots=True)
class CircuitBreaker:
    threshold: int = 3
    open_s: float = 10.0
    clock: Callable[[], float] = time.monotonic
    state: State = "closed"
    failures: int = 0
    opened_at: float = 0.0
    trips: int = field(default=0)

    def allow(self) -> bool:
        if self.state == "open" and self.clock() - self.opened_at >= self.open_s:
            self.state = "half_open"
        return self.state != "open"

    def record_success(self) -> None:
        self.failures = 0
        self.state = "closed"

    def record_failure(self) -> None:
        self.failures += 1
        if self.state == "half_open" or self.failures >= self.threshold:
            if self.state != "open":
                self.trips += 1
            self.state = "open"
            self.opened_at = self.clock()

    def snapshot(self) -> dict[str, object]:
        return {"state": self.state, "failures": self.failures, "trips": self.trips}
