"""Order Platform client used by the MCP tools. The customer comes only from the verified
caller context (X-Customer-Id), never from a tool argument.

Resilience (M7-3, M7-4): reads and keyed writes are retried with bounded backoff; every call
passes through the circuit breaker, which fails fast while the order system is down."""

import asyncio
from typing import Any

import httpx

from mcp_server.resilience import CircuitBreaker


class ToolFailureError(Exception):
    """A tool failed in a way the agent may explain: code, message and retryable (LLD-4 L4c)."""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.retryable = retryable


class OrderClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        breaker: CircuitBreaker | None = None,
        *,
        retries: int = 2,
        backoff_s: float = 0.2,
    ) -> None:
        self._client = client
        self.breaker = breaker or CircuitBreaker()
        self._retries = retries
        self._backoff_s = backoff_s

    async def get(self, customer_no: str, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._call("GET", path, customer_no, params=params)

    async def post(
        self,
        customer_no: str | None,
        path: str,
        body: dict[str, Any],
        idempotency_key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        extra = dict(headers or {})
        if idempotency_key:
            extra["Idempotency-Key"] = idempotency_key
        return await self._call("POST", path, customer_no, json=body, headers=extra)

    async def _call(self, method: str, path: str, customer_no: str | None, **kwargs: Any) -> Any:
        if not self.breaker.allow():
            raise ToolFailureError("ORDER_SYSTEM_UNAVAILABLE", "order system circuit open", True)
        # Retry reads, and writes that carry an idempotency key (a replay returns the original)
        keyed = bool(kwargs.get("headers", {}).get("Idempotency-Key"))
        attempts = self._retries + 1 if (method == "GET" or keyed) else 1
        for attempt in range(attempts):
            try:
                result = await self._once(method, path, customer_no, **kwargs)
            except ToolFailureError as exc:
                if not exc.retryable:
                    self.breaker.record_success()  # the order system answered: not a fault
                    raise
                self.breaker.record_failure()
                if attempt == attempts - 1:
                    raise
                await asyncio.sleep(self._backoff_s * (attempt + 1))
                continue
            self.breaker.record_success()
            return result
        raise AssertionError("unreachable")

    async def _once(self, method: str, path: str, customer_no: str | None, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        if customer_no is not None:
            headers["X-Customer-Id"] = customer_no
        try:
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise ToolFailureError("TIMEOUT", "order system too slow", retryable=True) from exc
        except httpx.TransportError as exc:
            raise ToolFailureError(
                "ORDER_SYSTEM_UNAVAILABLE", "order system unreachable", retryable=True
            ) from exc
        if response.is_success:
            return response.json()
        raise _failure(response)


def _failure(response: httpx.Response) -> ToolFailureError:
    try:
        body = response.json()
        return ToolFailureError(
            str(body["code"]), str(body["message"]), bool(body.get("retryable"))
        )
    except (ValueError, KeyError, TypeError):
        retryable = response.status_code >= 500
        code = "ORDER_SYSTEM_UNAVAILABLE" if retryable else "UNEXPECTED"
        return ToolFailureError(code, f"HTTP {response.status_code}", retryable)
