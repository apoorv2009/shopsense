"""Order Platform use cases. Every call is scoped to the calling customer (L7c)."""

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from order_platform.application.ports import Clock, IdGenerator, UnitOfWork, UnitOfWorkFactory
from order_platform.domain.errors import DuplicateRequestError, NotFoundError
from order_platform.domain.model import Order, Refund, RefundReason, Replacement, Shipment
from order_platform.domain.rules import RefundQuote, decide_refund, decide_replacement, quote_refund


@dataclass(frozen=True, slots=True)
class RefundCommand:
    customer_no: str
    order_no: str
    item_sku: str
    amount_paise: int
    reason: RefundReason
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ReplacementCommand:
    customer_no: str
    order_no: str
    item_sku: str
    reason: RefundReason
    idempotency_key: str


class OrderQueries:
    def __init__(self, uow: UnitOfWorkFactory) -> None:
        self._uow = uow

    async def list_orders(self, customer_no: str, limit: int) -> list[Order]:
        async with self._uow() as uow:
            return await uow.orders.list_for_customer(customer_no, limit)

    async def get_order(self, customer_no: str, order_no: str) -> Order:
        async with self._uow() as uow:
            return await _owned(uow, customer_no, order_no)

    async def shipment(self, customer_no: str, order_no: str) -> Shipment:
        order = await self.get_order(customer_no, order_no)
        if order.shipment is None:
            raise NotFoundError(f"order {order_no} has not shipped yet")
        return order.shipment

    async def quote(
        self, customer_no: str, order_no: str, sku: str, reason: RefundReason
    ) -> RefundQuote:
        return quote_refund(await self.get_order(customer_no, order_no), sku, reason)


class RequestRefund:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, ids: IdGenerator) -> None:
        self._uow, self._clock, self._ids = uow, clock, ids

    async def execute(self, cmd: RefundCommand) -> dict[str, Any]:
        request_hash = _hash(cmd)
        async with self._uow() as uow:
            if (replay := await _replay(uow, cmd.idempotency_key, request_hash)) is not None:
                return replay
            order = await _owned(uow, cmd.customer_no, cmd.order_no, for_update=True)
            quote = quote_refund(order, cmd.item_sku, cmd.reason)
            status = decide_refund(quote, cmd.amount_paise)
            refund = Refund(
                refund_no=self._ids.new("RF"),
                order_no=cmd.order_no,
                item_sku=cmd.item_sku,
                amount_paise=cmd.amount_paise,
                reason=cmd.reason,
                status=status,
                created_at=self._clock.now(),
            )
            await uow.orders.add_refund(refund)
            body = to_json(refund)
            await uow.idempotency.save(cmd.idempotency_key, request_hash, body)
            await uow.commit()
            return body


class RequestReplacement:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, ids: IdGenerator) -> None:
        self._uow, self._clock, self._ids = uow, clock, ids

    async def execute(self, cmd: ReplacementCommand) -> dict[str, Any]:
        request_hash = _hash(cmd)
        async with self._uow() as uow:
            if (replay := await _replay(uow, cmd.idempotency_key, request_hash)) is not None:
                return replay
            order = await _owned(uow, cmd.customer_no, cmd.order_no, for_update=True)
            replacement = Replacement(
                replacement_no=self._ids.new("RP"),
                order_no=cmd.order_no,
                item_sku=cmd.item_sku,
                reason=cmd.reason,
                status=decide_replacement(order, cmd.item_sku),
                created_at=self._clock.now(),
            )
            await uow.orders.add_replacement(replacement)
            body = to_json(replacement)
            await uow.idempotency.save(cmd.idempotency_key, request_hash, body)
            await uow.commit()
            return body


async def _owned(
    uow: UnitOfWork, customer_no: str, order_no: str, *, for_update: bool = False
) -> Order:
    order = await uow.orders.get(customer_no, order_no, for_update=for_update)
    if order is None:
        raise NotFoundError(f"order {order_no} not found")
    return order


async def _replay(uow: UnitOfWork, key: str, request_hash: str) -> dict[str, Any] | None:
    stored = await uow.idempotency.get(key)
    if stored is None:
        return None
    if stored.request_hash != request_hash:
        raise DuplicateRequestError("idempotency key reused with a different request")
    return stored.body


def _hash(cmd: RefundCommand | ReplacementCommand) -> str:
    payload = {k: v for k, v in asdict(cmd).items() if k != "idempotency_key"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def to_json(entity: Refund | Replacement) -> dict[str, Any]:
    data = asdict(entity)
    data["created_at"] = entity.created_at.isoformat()
    return {k: (v.value if hasattr(v, "value") else v) for k, v in data.items()}
