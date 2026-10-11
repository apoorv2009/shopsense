"""Alembic environment. Migrations run through order_platform.adapters.db.migrate, which
passes an open (sync-adapted) connection; there is no alembic.ini or URL in the repo."""

from alembic import context

from order_platform.adapters.db.tables import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("run migrations via order_platform.adapters.db.migrate")

context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
with context.begin_transaction():
    context.run_migrations()
