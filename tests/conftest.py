"""Env setup that must run before any test imports backend, the hypothesis profile, the
async-backend pin, the lexicon-table guard, the registry fixture, the client-cache fixture,
and the database fixtures.

Settings is built at import time (spec §10).
"""

import os
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

import pytest
from hypothesis import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from backend.evals.registry import Check

# config.py skips .env when this is set, so local and CI test runs see identical settings
os.environ["NOTEPILOT_IGNORE_DOTENV"] = "1"
# assignment, not setdefault: a key exported in your shell must never reach tests
os.environ["ANTHROPIC_API_KEY"] = "test-dummy-key"


# The free tier is deterministic (spec §11, invariant 20). Hypothesis loads its own "ci"
# profile on GitHub Actions and a randomized one elsewhere; this one loads everywhere, so
# local runs and CI draw the same examples, with no wall-clock deadline to flake on.
settings.register_profile("deterministic", derandomize=True, deadline=None)
settings.load_profile("deterministic")


# Pins the anyio plugin's backend to asyncio.
# Why override: the plugin's default anyio_backend is parametrized over every importable
# backend, so installing trio would silently double every async test.
# Why session scope, not the plugin's module scope: a future module- or session-scoped
# async fixture can never hit ScopeMismatch on this pin.
# Mode stays the plugin default (strict): every async test carries @pytest.mark.anyio, and
# under pytest 9 an unmarked async test fails loudly, so a forgotten marker can't pass.
# Activation rule: async tests never request anyio_backend as a parameter. The plugin
# dispatches on funcargs, so requesting it activates the runner by itself and makes the
# marker redundant.
@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def lexicon_tables_unchanged() -> Iterator[None]:
    """L257: the suite leaves every lexicon table as it found it, checked after the last test.

    The tables stay mutable types (§7's lexicons.py imports nothing), so a test that writes to
    one would leak into every test after it. Imported here, not at the top, so the env setup
    above runs before any backend import.
    """
    from tests.guards import lexicon_digest

    before = lexicon_digest()
    yield
    assert lexicon_digest() == before, "a test wrote to a lexicon table (L257)"


@pytest.fixture
def registry() -> Iterator[dict[str, Check]]:
    """REGISTRY, emptied for the test and restored after it.

    In place, not rebound: a module that imported REGISTRY by name holds this same dict.
    Imported here, not at the top, so the env setup above runs before any backend import.
    """
    from backend.evals.registry import REGISTRY

    saved = dict(REGISTRY)
    REGISTRY.clear()
    yield REGISTRY
    REGISTRY.clear()
    REGISTRY.update(saved)


@pytest.fixture
def fresh_client_cache() -> Iterator[None]:
    """The one client's cache, cleared around a test that builds the client (L78, L319).

    The cache is process-wide, so a client built under one test's settings must never be
    the one another test observes. Imported here, not at the top, so the env setup above runs
    before any backend import.
    """
    from backend.orchestrator import anthropic_client

    anthropic_client.cache_clear()
    yield
    anthropic_client.cache_clear()


# The database tests (spec §11; L345, L346). TEST_DATABASE_URL names a Postgres the tests may empty:
# never a setting and never .env, so no test can reach the app's own database. Unset, the
# tests that need it skip, unless NOTEPILOT_REQUIRE_DB is "1" (CI), where they fail instead.
@pytest.fixture
def db_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    if os.environ.get("NOTEPILOT_REQUIRE_DB") == "1":
        pytest.fail("NOTEPILOT_REQUIRE_DB is 1 and TEST_DATABASE_URL is unset (L345)")
    pytest.skip("TEST_DATABASE_URL is unset: the database tests need a Postgres (L345)")


@pytest.fixture
async def db_sessions(db_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A session factory on the test database, emptied and migrated to head (L346).

    Emptied, not migrated in place: an earlier run's schema, a model-built table included,
    would otherwise meet the migration. Imported here, not at the top, so the env setup above
    runs before any backend import.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.database import migrate, reset

    engine = create_async_engine(db_url, hide_parameters=True)
    async with engine.begin() as conn:
        await conn.run_sync(reset)
        await conn.run_sync(migrate)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
