"""shopsense database tables (LLD-3, M3 subset). ORM rows never leave this package."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ShopSenseBase(DeclarativeBase):
    pass


class TicketHistoryRow(ShopSenseBase):
    __tablename__ = "ticket_history"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_no: Mapped[str] = mapped_column(String(16), index=True)
    ticket_no: Mapped[str] = mapped_column(String(24), unique=True)
    issue_type: Mapped[str] = mapped_column(String(40))
    order_no: Mapped[str | None] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(24))
    sentiment: Mapped[str | None] = mapped_column(String(16))
    resolved_on: Mapped[date] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(String(240))


class CustomerProfileRow(ShopSenseBase):
    __tablename__ = "customer_profiles"
    customer_no: Mapped[str] = mapped_column(String(16), primary_key=True)
    language: Mapped[str] = mapped_column(String(16))
    refund_method: Mapped[str] = mapped_column(String(24))
    channel: Mapped[str] = mapped_column(String(16))


class PolicyDocumentRow(ShopSenseBase):
    __tablename__ = "policy_documents"
    doc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer)
    effective_date: Mapped[date] = mapped_column(Date)
    content_hash: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PolicyRuleRow(ShopSenseBase):
    __tablename__ = "policy_rules"
    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    doc_id: Mapped[str] = mapped_column(ForeignKey("policy_documents.doc_id"), index=True)
    section_id: Mapped[str] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(32))
    applies_to: Mapped[dict[str, Any]] = mapped_column(JSONB)
    window_days: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(24))
    overrides: Mapped[list[str]] = mapped_column(JSONB)
    evidence: Mapped[str] = mapped_column(String(8))


class OutboxRow(ShopSenseBase):
    __tablename__ = "outbox_items"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), index=True)
    attempts: Mapped[int] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(String(300))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
