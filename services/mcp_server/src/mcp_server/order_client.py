"""Order Platform client used by the MCP tools. The customer comes only from the verified
caller context (X-Customer-Id), never from a tool argument."""

from typing import Any

import httpx


class ToolFailureError(Exception):
    """A tool failed in a way the agent may explain: code, message and retryable (LLD-4 L4c)."""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.retryable = retryable


class OrderClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get(self, customer_no: str, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._call("GET", path, customer_no, params=params)

    async def post(
        self,
        customer_no: str | None,
        path: str,
        body: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        return await self._call("POST", path, customer_no, json=body, headers=headers)

    async def _call(self, method: str, path: str, customer_no: str | None, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        if customer_no is not None:
            headers["X-Customer-Id"] = customer_no
        try:
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise ToolFailureError("TIMEOUT", "order system too slow", retryable=True) from exc
        except httpx.TransportError as exc:
            raise ToolFailureError(
                "ORDER_SYSTEM_UNAVAILABLE", "order system unreachable", True
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
