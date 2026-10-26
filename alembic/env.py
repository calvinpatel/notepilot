"""Alembic's migration environment (spec §9.8, D3; L346).

The database is settings.database_url, never alembic.ini, which is committed and would carry
the password. A test hands in a connection of its own (config.attributes["connection"]): it
migrates the database it may empty, inside its own event loop, and the suite's logging stays
as it was. `alembic upgrade --sql` prints PostgreSQL and touches no database.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import settings
from backend.db import Base

config = context.config


def _migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _migrate_database(url: str) -> None:
    engine = create_async_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_migrate)
    finally:
        await engine.dispose()


def _run_offline() -> None:
    context.configure(dialect_name="postgresql", target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _migrate(connection)
        return
    if settings.database_url is None:
        raise RuntimeError("database_url is unset: alembic migrates the app's database (§9.8)")
    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    asyncio.run(_migrate_database(settings.database_url.get_secret_value()))


if context.is_offline_mode():
    _run_offline()
else:
    _run_online()
