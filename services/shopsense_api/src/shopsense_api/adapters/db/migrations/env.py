"""Alembic environment. Migrations run through shopsense_api.adapters.db.migrate, which passes
an open connection; there is no alembic.ini or URL in the repo."""

from alembic import context

from shopsense_api.adapters.db.shopsense_tables import ShopSenseBase

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("run migrations via shopsense_api.adapters.db.migrate")

context.configure(connection=connection, target_metadata=ShopSenseBase.metadata, compare_type=True)
with context.begin_transaction():
    context.run_migrations()
