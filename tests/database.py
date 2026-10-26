"""The tests' database (spec §11; L345, L346): emptied, then migrated as the app's would be.

Functions over a synchronous Connection, for an async engine's run_sync: Alembic's commands
are synchronous, and env.py runs them on the connection handed in (L346). Imports nothing
from backend, so conftest can import it before the env setup matters.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, text

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def alembic_config(connection: Connection | None = None) -> Config:
    """The committed alembic.ini, with a test's own connection when it has one."""
    config = Config(str(ALEMBIC_INI))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def reset(connection: Connection) -> None:
    """Drop everything in the schema, tables an earlier run's model built included."""
    connection.execute(text("DROP SCHEMA public CASCADE"))
    connection.execute(text("CREATE SCHEMA public"))


def migrate(connection: Connection, revision: str = "head") -> None:
    command.upgrade(alembic_config(connection), revision)


def downgrade(connection: Connection, revision: str = "base") -> None:
    command.downgrade(alembic_config(connection), revision)
