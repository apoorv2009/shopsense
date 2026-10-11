"""Tool definitions for the Order-Actions agent and their deterministic execution guard.

The model supplies only *what* (order, item, amount, reason); our code supplies *who*
(customer ID) and the idempotency key. Arguments are validated before any call, and at
most one write action is allowed per agent run (D16 M2 guard).
"""

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from shopsense_api.application.ports.orders import OrderTools
from shopsense_api.application.ports.tool_llm import ToolCall, ToolSpec
from shopsense_api.domain.exceptions import OrderToolError

ORDER_NO = Field(pattern=r"^ORD-\d{6}$", description="Order reference, e.g. ORD-100003")
SKU = Field(pattern=r"^[A-Z0-9-]{3,32}$", description="Item SKU from get_order, e.g. ELE-LAPTOP14")


class Reason(StrEnum):
    DAMAGED = "damaged"
    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    MISSING_ITEM = "missing_item"
    NOT_AS_DESCRIBED = "not_as_described"
    SIZE_ISSUE = "size_issue"
    CHANGED_MIND = "changed_mind"
    LOST_IN_TRANSIT = "lost_in_transit"
    OTHER = "other"


class ListArgs(BaseModel):
    limit: int = Field(default=5, ge=1, le=10)


class OrderArgs(BaseModel):
    order_no: str = ORDER_NO


class QuoteArgs(BaseModel):
    order_no: str = ORDER_NO
    item_sku: str = SKU
    reason: Reason


class RefundArgs(BaseModel):
    order_no: str = ORDER_NO
    item_sku: str = SKU
    amount_paise: int = Field(
        gt=0, description="Amount in paise, normally refundable_paise from calculate_refund"
    )
    reason: Reason


class ReplacementArgs(BaseModel):
    order_no: str = ORDER_NO
    item_sku: str = SKU
    reason: Reason


Handler = Callable[[OrderTools, str, BaseModel, str], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class OrderTool:
    name: str
    description: str
    args: type[BaseModel]
    handler: Handler
    writes: bool = False

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.args.model_json_schema())


def _as[M: BaseModel](model: BaseModel, cls: type[M]) -> M:
    if not isinstance(model, cls):
        raise TypeError(f"expected {cls.__name__}")
    return model


async def _list(t: OrderTools, customer: str, m: BaseModel, _: str) -> Any:
    return await t.list_my_orders(customer, _as(m, ListArgs).limit)


async def _get(t: OrderTools, customer: str, m: BaseModel, _: str) -> Any:
    return await t.get_order(customer, _as(m, OrderArgs).order_no)


async def _track(t: OrderTools, customer: str, m: BaseModel, _: str) -> Any:
    return await t.track_shipment(customer, _as(m, OrderArgs).order_no)


async def _refunds(t: OrderTools, customer: str, m: BaseModel, _: str) -> Any:
    return await t.get_refund_status(customer, _as(m, OrderArgs).order_no)


async def _calculate(t: OrderTools, customer: str, m: BaseModel, _: str) -> Any:
    q = _as(m, QuoteArgs)
    return await t.calculate_refund(customer, q.order_no, q.item_sku, q.reason.value)


async def _refund(t: OrderTools, customer: str, m: BaseModel, key: str) -> Any:
    r = _as(m, RefundArgs)
    return await t.request_refund(
        customer, r.order_no, r.item_sku, r.amount_paise, r.reason.value, key
    )


async def _replace(t: OrderTools, customer: str, m: BaseModel, key: str) -> Any:
    r = _as(m, ReplacementArgs)
    return await t.request_replacement(customer, r.order_no, r.item_sku, r.reason.value, key)


TOOLS: dict[str, OrderTool] = {
    tool.name: tool
    for tool in (
        OrderTool("list_my_orders", "List the customer's recent orders.", ListArgs, _list),
        OrderTool(
            "get_order",
            "Order details: items with SKU, price paid, refunded amount, status, delivery date.",
            OrderArgs,
            _get,
        ),
        OrderTool(
            "track_shipment",
            "Shipping tracker: carrier, AWB, status, promised date and recent scans.",
            OrderArgs,
            _track,
        ),
        OrderTool(
            "get_refund_status",
            "Refunds already requested for an order and their status.",
            OrderArgs,
            _refunds,
        ),
        OrderTool(
            "calculate_refund",
            "Refund-amount calculator: refundable amount for an item and whether it needs "
            "human approval. Changes nothing.",
            QuoteArgs,
            _calculate,
        ),
        OrderTool(
            "request_refund",
            "Request a refund for one item. Amounts above the automatic limit are held for "
            "human approval.",
            RefundArgs,
            _refund,
            writes=True,
        ),
        OrderTool(
            "request_replacement",
            "Request a replacement for one delivered item.",
            ReplacementArgs,
            _replace,
            writes=True,
        ),
    )
}


@dataclass(slots=True)
class ToolExecutor:
    """Executes model tool calls for one agent run, for one verified customer."""

    tools: OrderTools
    customer_id: str
    run_id: str
    writes_allowed: bool = True
    # orders the customer explicitly named; writes are limited to these (never a guess)
    named_orders: frozenset[str] = frozenset()
    writes_done: int = 0
    log: list[dict[str, Any]] = field(default_factory=list)

    async def execute(self, call: ToolCall) -> dict[str, Any]:
        result = await self._execute(call)
        self.log.append({"tool": call.name, "arguments": call.arguments, "result": result})
        return result

    async def _execute(self, call: ToolCall) -> dict[str, Any]:
        tool = TOOLS.get(call.name)
        if tool is None:
            return _error("UNKNOWN_TOOL", f"no tool named {call.name}")
        try:
            args = tool.args.model_validate(call.arguments)
        except ValidationError as exc:
            fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
            return _error("VALIDATION_ERROR", f"invalid arguments: {fields}")
        if tool.writes and not self.writes_allowed:
            return _error(
                "NOT_ALLOWED",
                "write actions are disabled for this request; a specialist will review it",
            )
        if tool.writes and getattr(args, "order_no", None) not in self.named_orders:
            return _error(
                "NOT_ALLOWED",
                "refunds and replacements need the customer to state the order number; ask them",
            )
        if tool.writes and self.writes_done >= 1:
            return _error("NOT_ALLOWED", "only one refund or replacement per request")
        try:
            data = await tool.handler(self.tools, self.customer_id, args, self._key(tool, args))
        except OrderToolError as exc:
            return _error(exc.code, exc.message)
        self.writes_done += tool.writes
        return {"ok": True, "data": data}

    def _key(self, tool: OrderTool, args: BaseModel) -> str:
        """Deterministic: a repeated identical write replays instead of refunding twice."""
        material = json.dumps(
            [self.run_id, tool.name, args.model_dump(mode="json")], sort_keys=True
        )
        return hashlib.sha256(material.encode()).hexdigest()[:40]


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}
