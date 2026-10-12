"""SQLAlchemy implementations of the repository, idempotency store and unit of work."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from order_platform.adapters.db.tables import (
    CustomerRow,
    IdempotencyRow,
    OrderItemRow,
    OrderRow,
    ProductRow,
    RefundRow,
    ReplacementRow,
    ShipmentRow,
)
from order_platform.application.ports import StoredResponse
from order_platform.domain.errors import NotAllowedError, NotFoundError, ValidationFailedError
from order_platform.domain.model import (
    Order,
    OrderItem,
    OrderStatus,
    Product,
    Refund,
    RefundReason,
    RefundStatus,
    Replacement,
    ScanEvent,
    Shipment,
    ShipmentStatus,
)

_LOAD = (
    selectinload(OrderRow.customer),
    selectinload(OrderRow.items).selectinload(OrderItemRow.product),
    selectinload(OrderRow.items).selectinload(OrderItemRow.refunds),
    selectinload(OrderRow.shipment).selectinload(ShipmentRow.events),
)


class SqlOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_for_customer(self, customer_no: str, limit: int) -> list[Order]:
        query = (
            select(OrderRow)
            .join(CustomerRow)
            .where(CustomerRow.customer_no == customer_no)
            .options(*_LOAD)
            .order_by(OrderRow.placed_at.desc())
            .limit(limit)
        )
        return [to_order(row) for row in (await self._s.scalars(query)).all()]

    async def get(
        self, customer_no: str, order_no: str, *, for_update: bool = False
    ) -> Order | None:
        if for_update:  # lock the items first so concurrent refunds serialise
            lock = (
                select(OrderItemRow.id)
                .join(OrderRow)
                .join(CustomerRow)
                .where(OrderRow.order_no == order_no, CustomerRow.customer_no == customer_no)
                .with_for_update(of=OrderItemRow)
            )
            await self._s.execute(lock)
        row = await self._row(customer_no, order_no)
        return to_order(row) if row is not None else None

    async def add_refund(self, refund: Refund) -> None:
        item = await self._item(refund.order_no, refund.item_sku)
        self._s.add(
            RefundRow(
                refund_no=refund.refund_no,
                order_item_id=item.id,
                amount_paise=refund.amount_paise,
                reason=refund.reason.value,
                status=refund.status.value,
                created_at=refund.created_at,
            )
        )
        if refund.status is RefundStatus.APPROVED:
            item.refunded_paise += refund.amount_paise

    async def add_replacement(self, replacement: Replacement) -> None:
        item = await self._item(replacement.order_no, replacement.item_sku)
        self._s.add(
            ReplacementRow(
                replacement_no=replacement.replacement_no,
                order_item_id=item.id,
                reason=replacement.reason.value,
                status=replacement.status.value,
                created_at=replacement.created_at,
            )
        )

    async def refund_scope(self, refund_no: str) -> tuple[str, str, int]:
        row = (
            await self._s.execute(
                select(RefundRow, OrderRow.order_no, ProductRow.sku)
                .join(OrderItemRow, OrderItemRow.id == RefundRow.order_item_id)
                .join(OrderRow, OrderRow.id == OrderItemRow.order_id)
                .join(ProductRow, ProductRow.id == OrderItemRow.product_id)
                .where(RefundRow.refund_no == refund_no)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError(f"refund {refund_no} not found")
        refund, order_no, sku = row
        return str(order_no), str(sku), int(refund.amount_paise)

    async def decide_refund(self, refund_no: str, approve: bool) -> Refund:
        row = (
            await self._s.scalars(select(RefundRow).where(RefundRow.refund_no == refund_no))
        ).one_or_none()
        if row is None:
            raise NotFoundError(f"refund {refund_no} not found")
        item = (
            await self._s.scalars(
                select(OrderItemRow).where(OrderItemRow.id == row.order_item_id).with_for_update()
            )
        ).one()
        if row.status != RefundStatus.PENDING_APPROVAL.value:
            raise NotAllowedError(f"refund {refund_no} is {row.status}, not pending_approval")
        if approve:
            if item.refunded_paise + row.amount_paise > item.unit_price_paise * item.qty:
                raise ValidationFailedError("approval would exceed the amount paid")
            item.refunded_paise += row.amount_paise
            row.status = RefundStatus.PROCESSED.value
        else:
            row.status = RefundStatus.REJECTED.value
        order_no, sku = (
            await self._s.execute(
                select(OrderRow.order_no, ProductRow.sku)
                .join(OrderItemRow, OrderItemRow.order_id == OrderRow.id)
                .join(ProductRow, ProductRow.id == OrderItemRow.product_id)
                .where(OrderItemRow.id == item.id)
            )
        ).one()
        return Refund(
            refund_no=row.refund_no,
            order_no=order_no,
            item_sku=sku,
            amount_paise=row.amount_paise,
            reason=RefundReason(row.reason),
            status=RefundStatus(row.status),
            created_at=row.created_at,
        )

    async def _row(self, customer_no: str, order_no: str) -> OrderRow | None:
        query = (
            select(OrderRow)
            .join(CustomerRow)
            .where(OrderRow.order_no == order_no, CustomerRow.customer_no == customer_no)
            .options(*_LOAD)
        )
        return (await self._s.scalars(query)).one_or_none()

    async def _item(self, order_no: str, sku: str) -> OrderItemRow:
        query = (
            select(OrderItemRow)
            .join(OrderRow)
            .join(ProductRow)
            .where(OrderRow.order_no == order_no, ProductRow.sku == sku)
        )
        item = (await self._s.scalars(query)).one_or_none()
        if item is None:
            raise NotFoundError(f"item {sku} not found in order {order_no}")
        return item


class SqlIdempotencyStore:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, key: str) -> StoredResponse | None:
        row = await self._s.get(IdempotencyRow, key)
        return StoredResponse(row.request_hash, row.response) if row else None

    async def save(self, key: str, request_hash: str, body: dict[str, Any]) -> None:
        self._s.add(
            IdempotencyRow(
                key=key, request_hash=request_hash, response=body, created_at=datetime.now(UTC)
            )
        )


class SqlUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._session: AsyncSession | None = None

    @property
    def orders(self) -> SqlOrderRepository:
        return SqlOrderRepository(self._active())

    @property
    def idempotency(self) -> SqlIdempotencyStore:
        return SqlIdempotencyStore(self._active())

    def _active(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("unit of work used outside 'async with'")
        return self._session

    async def __aenter__(self) -> Self:
        self._session = self._sessions()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._active()
        await session.rollback()  # no-op after commit
        await session.close()
        self._session = None

    async def commit(self) -> None:
        await self._active().commit()


def to_order(row: OrderRow) -> Order:
    refunds = tuple(
        Refund(
            refund_no=r.refund_no,
            order_no=row.order_no,
            item_sku=item.product.sku,
            amount_paise=r.amount_paise,
            reason=RefundReason(r.reason),
            status=RefundStatus(r.status),
            created_at=r.created_at,
        )
        for item in row.items
        for r in item.refunds
    )
    return Order(
        order_no=row.order_no,
        customer_no=row.customer.customer_no,
        status=OrderStatus(row.status),
        payment_method=row.payment_method,
        placed_at=row.placed_at,
        shipping_fee_paise=row.shipping_fee_paise,
        items=tuple(_item(i) for i in row.items),
        shipment=_shipment(row.shipment),
        refunds=refunds,
    )


def _item(row: OrderItemRow) -> OrderItem:
    p = row.product
    product = Product(p.sku, p.name, p.category, p.is_accessory, p.warranty_months)
    return OrderItem(product, row.qty, row.unit_price_paise, row.refunded_paise)


def _shipment(row: ShipmentRow | None) -> Shipment | None:
    if row is None:
        return None
    events = tuple(
        ScanEvent(ShipmentStatus(e.status), e.location, e.scanned_at) for e in row.events
    )
    return Shipment(
        row.carrier,
        row.awb,
        ShipmentStatus(row.status),
        row.promised_date,
        row.delivered_at,
        events,
    )
