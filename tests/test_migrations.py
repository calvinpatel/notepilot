"""Pins the migrations (spec §9.8, §11; L346): head builds exactly the model's schema, base
takes it away, and the command line migrates nothing without a database_url.

The database tests take conftest's db_url, a Postgres the tests may empty (L345).
"""

import io
from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, inspect
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.config import Settings
from backend.db import Base
from tests.database import alembic_config, downgrade, migrate, reset


@pytest.fixture
async def engine(db_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(db_url, hide_parameters=True)
    async with engine.begin() as conn:
        await conn.run_sync(reset)
    try:
        yield engine
    finally:
        await engine.dispose()


def _drift(connection: Connection) -> list[object]:
    return list(compare_metadata(MigrationContext.configure(connection), Base.metadata))


def _tables(connection: Connection) -> set[str]:
    return set(inspect(connection).get_table_names())


@pytest.mark.anyio
async def test_head_builds_exactly_the_models_schema(engine: AsyncEngine) -> None:
    # L346: the migration and NoteRecord can't drift apart unseen.
    async with engine.begin() as conn:
        await conn.run_sync(migrate)
        assert await conn.run_sync(_drift) == []


@pytest.mark.anyio
async def test_base_takes_the_notes_table_away(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(migrate)
        assert "notes" in await conn.run_sync(_tables)
        await conn.run_sync(downgrade)
        assert "notes" not in await conn.run_sync(_tables)


def test_the_command_line_migrates_nothing_without_a_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No connection handed in, so env.py reads settings, as `alembic upgrade head` would.
    monkeypatch.setattr("backend.config.settings", Settings.model_validate({"database_url": None}))
    with pytest.raises(RuntimeError, match="database_url is unset"):
        command.upgrade(alembic_config(), "head")


def test_offline_mode_prints_postgresql_and_touches_no_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.config.settings", Settings.model_validate({"database_url": None}))
    out = io.StringIO()
    config = alembic_config()
    config.output_buffer = out
    command.upgrade(config, "head", sql=True)
    sql = out.getvalue()
    assert "CREATE TABLE notes" in sql
    # PostgreSQL's spellings: another dialect renders these columns as CHAR(32) and DATETIME
    assert "id UUID NOT NULL" in sql
    assert "created_at TIMESTAMP WITH TIME ZONE" in sql
