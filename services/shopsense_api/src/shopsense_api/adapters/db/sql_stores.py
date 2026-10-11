"""SQL adapters for customer memory and the policy rules table (PostgreSQL, shopsense DB)."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shopsense_api.adapters.db.shopsense_tables import (
    CustomerProfileRow,
    OutboxRow,
    PolicyDocumentRow,
    PolicyRuleRow,
    TicketHistoryRow,
)
from shopsense_api.application.ports.outbox import OutboxItem
from shopsense_api.domain.memory.model import (
    Channel,
    CustomerPreferences,
    RefundMethod,
    TicketOutcome,
    TicketRecord,
)
from shopsense_api.domain.policy.model import (
    Evidence,
    Outcome,
    PolicyDocument,
    PolicyRule,
    RuleKind,
)
from shopsense_api.domain.ticket.enums import IssueType, Language, Sentiment


class SqlMemoryStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def recent_tickets(self, customer_no: str, limit: int) -> list[TicketRecord]:
        stmt = (
            select(TicketHistoryRow)
            .where(TicketHistoryRow.customer_no == customer_no)
            .order_by(TicketHistoryRow.resolved_on.desc(), TicketHistoryRow.ticket_no.desc())
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = (await session.scalars(stmt)).all()
        return [_record(row) for row in rows]

    async def add_ticket(self, record: TicketRecord) -> None:
        row = TicketHistoryRow(
            customer_no=record.customer_no,
            ticket_no=record.ticket_no,
            issue_type=record.issue_type.value,
            order_no=record.order_no,
            outcome=record.outcome.value,
            sentiment=record.sentiment.value if record.sentiment else None,
            resolved_on=record.resolved_on,
            summary=record.summary,
        )
        async with self._sessions.begin() as session:
            session.add(row)

    async def preferences(self, customer_no: str) -> CustomerPreferences | None:
        async with self._sessions() as session:
            row = await session.get(CustomerProfileRow, customer_no)
        if row is None:
            return None
        return CustomerPreferences(
            language=Language(row.language),
            refund_method=RefundMethod(row.refund_method),
            channel=Channel(row.channel),
        )

    async def set_preferences(self, customer_no: str, prefs: CustomerPreferences) -> None:
        row = CustomerProfileRow(
            customer_no=customer_no,
            language=prefs.language.value,
            refund_method=prefs.refund_method.value,
            channel=prefs.channel.value,
        )
        async with self._sessions.begin() as session:
            await session.merge(row)


class SqlPolicyStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def document_hashes(self) -> dict[str, str]:
        async with self._sessions() as session:
            rows = (await session.execute(select(PolicyDocumentRow))).scalars().all()
        return {row.doc_id: row.content_hash for row in rows}

    async def rules(self) -> list[PolicyRule]:
        async with self._sessions() as session:
            rows = (await session.execute(select(PolicyRuleRow))).scalars().all()
        return [_rule(row) for row in rows]

    async def save_document(self, doc: PolicyDocument) -> None:
        header = PolicyDocumentRow(
            doc_id=doc.doc_id,
            title=doc.title,
            version=doc.version,
            effective_date=doc.effective_date,
            content_hash=doc.content_hash,
            ingested_at=datetime.now(UTC),
        )
        rules = [_rule_row(r) for s in doc.sections for r in s.rules]
        async with self._sessions.begin() as session:
            await session.merge(header)
            await session.execute(delete(PolicyRuleRow).where(PolicyRuleRow.doc_id == doc.doc_id))
            session.add_all(rules)


def _record(row: TicketHistoryRow) -> TicketRecord:
    return TicketRecord(
        customer_no=row.customer_no,
        ticket_no=row.ticket_no,
        issue_type=IssueType(row.issue_type),
        order_no=row.order_no,
        outcome=TicketOutcome(row.outcome),
        sentiment=Sentiment(row.sentiment) if row.sentiment else None,
        resolved_on=row.resolved_on,
        summary=row.summary,
    )


def _rule(row: PolicyRuleRow) -> PolicyRule:
    return PolicyRule(
        rule_id=row.rule_id,
        kind=RuleKind(row.kind),
        applies_to=dict(row.applies_to),
        window_days=row.window_days,
        outcome=Outcome(row.outcome),
        overrides=tuple(row.overrides),
        evidence=Evidence(row.evidence),
        doc_id=row.doc_id,
        section_id=row.section_id,
    )


def _rule_row(rule: PolicyRule) -> PolicyRuleRow:
    return PolicyRuleRow(
        rule_id=rule.rule_id,
        doc_id=rule.doc_id,
        section_id=rule.section_id,
        kind=rule.kind.value,
        applies_to=dict(rule.applies_to),
        window_days=rule.window_days,
        outcome=rule.outcome.value,
        overrides=list(rule.overrides),
        evidence=rule.evidence.value,
    )


class SqlOutboxStore:
    """Approved writes waiting to be sent (M7-6). Enqueue is idempotent on the key."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def enqueue(self, item: OutboxItem) -> None:
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            if await session.get(OutboxRow, item.key) is not None:
                return
            session.add(_outbox_row(item, now))

    async def get(self, key: str) -> OutboxItem | None:
        async with self._sessions() as session:
            row = await session.get(OutboxRow, key)
        return _outbox_item(row) if row is not None else None

    async def pending(self, limit: int) -> list[OutboxItem]:
        stmt = (
            select(OutboxRow)
            .where(OutboxRow.status == "pending")
            .order_by(OutboxRow.created_at)
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = (await session.scalars(stmt)).all()
        return [_outbox_item(row) for row in rows]

    async def for_ticket(self, ticket_id: str) -> list[OutboxItem]:
        stmt = select(OutboxRow).where(OutboxRow.ticket_id == ticket_id)
        async with self._sessions() as session:
            rows = (await session.scalars(stmt)).all()
        return [_outbox_item(row) for row in rows]

    async def update(self, item: OutboxItem) -> None:
        async with self._sessions.begin() as session:
            row = await session.get(OutboxRow, item.key)
            if row is None:
                raise KeyError(item.key)
            row.status = item.status
            row.attempts = item.attempts
            row.last_error = item.last_error
            row.result = dict(item.result)
            row.updated_at = datetime.now(UTC)


def _outbox_row(item: OutboxItem, now: datetime) -> OutboxRow:
    return OutboxRow(
        key=item.key,
        ticket_id=item.ticket_id,
        action=item.action,
        payload=dict(item.payload),
        status=item.status,
        attempts=item.attempts,
        last_error=item.last_error,
        result=dict(item.result),
        created_at=now,
        updated_at=now,
    )


def _outbox_item(row: OutboxRow) -> OutboxItem:
    return OutboxItem(
        key=row.key,
        ticket_id=row.ticket_id,
        action=row.action,
        payload=dict(row.payload),
        status=row.status,
        attempts=row.attempts,
        last_error=row.last_error,
        result=dict(row.result),
    )
