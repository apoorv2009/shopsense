"""Domain exception hierarchy. Adapters translate infrastructure errors into these."""


class DomainException(Exception):  # noqa: N818 - name fixed by project standards
    """Base class for every error that crosses a layer boundary."""


class InvalidOrderId(DomainException):
    """An order reference does not match the ORD-123456 format."""


class InvalidMoney(DomainException):
    """A monetary amount is negative or otherwise invalid."""


class TriageFailed(DomainException):
    """Triage could not produce a valid SupportTicket; the ticket goes to a human."""


class LLMUnavailable(DomainException):
    """Every configured model provider failed with a transient error."""


class LLMRefused(DomainException):
    """The model declined the request; the ticket goes to a human (fail closed)."""


class LLMOutputInvalid(DomainException):
    """The model's output did not satisfy the expected schema."""

    def __init__(self, problems: tuple[str, ...]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


class OrderToolError(DomainException):
    """The order system rejected or could not complete a tool call (LLD-4 error model)."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable
