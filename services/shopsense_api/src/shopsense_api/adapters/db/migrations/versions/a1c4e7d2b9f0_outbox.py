"""outbox for approved writes (M7)

Revision ID: a1c4e7d2b9f0
Revises: f26aa4ae2f75
Create Date: 2026-10-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c4e7d2b9f0"
down_revision: str | Sequence[str] | None = "f26aa4ae2f75"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_items",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(op.f("ix_outbox_items_ticket_id"), "outbox_items", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_outbox_items_status"), "outbox_items", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_outbox_items_status"), table_name="outbox_items")
    op.drop_index(op.f("ix_outbox_items_ticket_id"), table_name="outbox_items")
    op.drop_table("outbox_items")
