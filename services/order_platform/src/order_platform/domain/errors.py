"""Order Platform error hierarchy; each error carries its API error code (LLD-4 L4c)."""


class OrderPlatformError(Exception):
    code = "INTERNAL_ERROR"
    retryable = False


class NotFoundError(OrderPlatformError):
    """Missing, or not owned by the caller (deliberately indistinguishable)."""

    code = "NOT_FOUND"


class ValidationFailedError(OrderPlatformError):
    code = "VALIDATION_ERROR"


class NotAllowedError(OrderPlatformError):
    """A business rule forbids the action (not delivered, fully refunded, pending approval...)."""

    code = "NOT_ALLOWED"


class DuplicateRequestError(OrderPlatformError):
    """Same idempotency key reused with a different request body."""

    code = "DUPLICATE_REQUEST"
