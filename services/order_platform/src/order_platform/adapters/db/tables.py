"""SQLAlchemy tables (LLD-3). ORM rows never leave this package; repositories map them
to domain objects."""

import os
import time
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uuid7() -> uuid.UUID:
    """Time-ordered UUID (RFC 9562 v7): 48-bit ms timestamp + random bits."""
    value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    value = (value & ~(0xF << 76)) | (0x7 << 76)
    value = (value & ~(0x3 << 62)) | (0x2 << 62)
    return uuid.UUID(int=value)


class Base(DeclarativeBase):
    pass


class CustomerRow(Base):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    customer_no: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(32))
    city: Mapped[str] = mapped_column(String(64))
    tier: Mapped[str] = mapped_column(String(16))
    abuse_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductRow(Base):
    __tablename__ = "products"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    sku: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32))
    is_accessory: Mapped[bool] = mapped_column(Boolean, default=False)
    price_paise: Mapped[int] = mapped_column(BigInteger)
    warranty_months: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("price_paise >= 0", name="ck_products_price"),)


class OrderRow(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    order_no: Mapped[str] = mapped_column(String(16), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    payment_method: Mapped[str] = mapped_column(String(32))
    shipping_fee_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    customer: Mapped[CustomerRow] = relationship()
    items: Mapped[list["OrderItemRow"]] = relationship(back_populates="order")
    shipment: Mapped["ShipmentRow | None"] = relationship(back_populates="order")
    __table_args__ = (CheckConstraint("shipping_fee_paise >= 0", name="ck_orders_fee"),)


class OrderItemRow(Base):
    __tablename__ = "order_items"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price_paise: Mapped[int] = mapped_column(BigInteger)
    refunded_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    order: Mapped[OrderRow] = relationship(back_populates="items")
    product: Mapped[ProductRow] = relationship()
    refunds: Mapped[list["RefundRow"]] = relationship(back_populates="item")
    __table_args__ = (
        UniqueConstraint("order_id", "product_id"),
        CheckConstraint("qty > 0", name="ck_items_qty"),
        CheckConstraint(
            "refunded_paise >= 0 AND refunded_paise <= unit_price_paise * qty",
            name="ck_items_refund_within_paid",
        ),
    )


class ShipmentRow(Base):
    __tablename__ = "shipments"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    carrier: Mapped[str] = mapped_column(String(32))
    awb: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24))
    promised_date: Mapped[date] = mapped_column(Date)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order: Mapped[OrderRow] = relationship(back_populates="shipment")
    events: Mapped[list["ShipmentEventRow"]] = relationship(order_by="ShipmentEventRow.scanned_at")


class ShipmentEventRow(Base):
    __tablename__ = "shipment_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id"), index=True)
    status: Mapped[str] = mapped_column(String(24))
    location: Mapped[str] = mapped_column(String(64))
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RefundRow(Base):
    __tablename__ = "refunds"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    refund_no: Mapped[str] = mapped_column(String(24), unique=True)
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id"), index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    grant_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    item: Mapped[OrderItemRow] = relationship(back_populates="refunds")
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_refunds_amount"),)


class ReplacementRow(Base):
    __tablename__ = "replacements"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    replacement_no: Mapped[str] = mapped_column(String(24), unique=True)
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id"), index=True)
    reason: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    grant_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdempotencyRow(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
