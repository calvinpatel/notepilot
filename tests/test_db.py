"""Pins persistence (spec §9.5, §9.6; L342-L345): the row a note becomes, the sink that never
raises and never logs a message, and the session factory read per request.

The database tests take conftest's db_sessions, a Postgres that TEST_DATABASE_URL names
(L345); the rest need no database.
"""

import logging
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import Settings
from backend.db import NoteRecord, _sessions, get_sessions, note_record, persist
from backend.grounding import ground
from backend.schemas import (
    ClaimDraft,
    EvalReport,
    EvalResult,
    RunMetadata,
    Severity,
    SOAPNote,
    SOAPNoteDraft,
    TokenUsage,
)
from tests.fakes import checks_config_with

# A paste-shaped sentinel: if it ever reaches a log line, a test below names the leak (L342).
_PASTE = "Pt Jane Roe MRN 4417 reports chest pain since this morning."
_CONFIG = checks_config_with()


def _note() -> SOAPNote:
    draft = SOAPNoteDraft(
        claims=[
            ClaimDraft(
                text="Chest pain since this morning",
                section="S",
                source_quote="chest pain since this morning",
            )
        ]
    )
    return ground(draft, _PASTE, config=_CONFIG)


def _report(*, judge_version: str | None = None, critical_failed: bool = False) -> EvalReport:
    results = [
        EvalResult(check="drug_in_quote", severity=Severity.CRITICAL, passed=not critical_failed)
    ]
    return EvalReport(
        results=results,
        checks_run=frozenset({"drug_in_quote"}),
        checks_version="c" * 12,
        judge_usage=TokenUsage(input_tokens=33, output_tokens=44),
        checks_config=_CONFIG,
        judge_version=judge_version,
    )


# Every number distinct, so a swapped column can't pass.
_METADATA = RunMetadata(
    model="model-id-1",
    prompt_version="p" * 12,
    usage=TokenUsage(input_tokens=11, output_tokens=22),
    validation_attempts=2,
)


def _failures(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "backend.db"]


# --- the row: lineage beside the payloads (§9.5; L57, L344) ---------------------------


def test_the_record_carries_the_notes_lineage_and_payloads() -> None:
    note_id, note, report = uuid.uuid4(), _note(), _report()
    record = note_record(note_id, _PASTE, note, report, _METADATA)
    assert (record.id, record.raw_text) == (note_id, _PASTE)
    assert (record.model_used, record.prompt_version) == ("model-id-1", "p" * 12)
    assert record.checks_version == "c" * 12
    assert (record.input_tokens, record.output_tokens, record.validation_attempts) == (11, 22, 2)
    assert (record.judge_input_tokens, record.judge_output_tokens) == (33, 44)
    assert record.production_critical_passed is True
    assert record.note == note.model_dump(mode="json")
    assert record.report == report.model_dump(mode="json")


def test_a_judged_notes_judge_rides_in_its_stored_report() -> None:
    # L344: no column of its own (L336); the stored report names the judge that judged.
    record = note_record(uuid.uuid4(), _PASTE, _note(), _report(judge_version="j" * 12), _METADATA)
    assert record.report["judge_version"] == "j" * 12
    assert "judge_version" not in NoteRecord.__table__.columns


def test_a_failed_critical_check_is_the_records_verdict() -> None:
    record = note_record(uuid.uuid4(), _PASTE, _note(), _report(critical_failed=True), _METADATA)
    assert record.production_critical_passed is False


# --- the sink: never raises, logs a type and frames only (§9.6, invariant 8; L342) -----


@pytest.mark.anyio
async def test_persist_without_sessions_writes_and_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    await persist(None, uuid.uuid4(), _PASTE, _note(), _report(), _METADATA)
    assert _failures(caplog) == []


class _WriteFailed(Exception):
    """Test-local (CLAUDE.md): nothing but this test's session raises it."""


class _CommitFails(AsyncSession):
    """A session whose commit fails the way Postgres's own error text reads: with the row."""

    async def commit(self) -> None:
        raise _WriteFailed(f"new row violates a check: Failing row contains ({_PASTE})")


def _sessions_whose_commit_fails() -> async_sessionmaker[AsyncSession]:
    # The commit raises before the session touches its engine, so nothing connects.
    engine = create_async_engine("postgresql+asyncpg://localhost:1/none", hide_parameters=True)
    return async_sessionmaker(engine, class_=_CommitFails)


@pytest.mark.anyio
async def test_a_failed_write_logs_its_type_and_frames_never_its_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    note_id = uuid.uuid4()
    await persist(_sessions_whose_commit_fails(), note_id, _PASTE, _note(), _report(), _METADATA)
    (record,) = _failures(caplog)
    assert record.levelno == logging.ERROR
    assert record.getMessage().startswith(
        f"persist_failed note_id={note_id} exc_type=_WriteFailed frames="
    )
    assert "backend/db.py:" in record.getMessage()
    assert _PASTE not in caplog.text
    assert record.exc_info is None


@pytest.mark.anyio
async def test_an_unreachable_database_is_logged_and_swallowed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    # Port 1 refuses at once: the sink's own failure path, no database needed.
    engine = create_async_engine("postgresql+asyncpg://localhost:1/none", hide_parameters=True)
    try:
        await persist(
            async_sessionmaker(engine), uuid.uuid4(), _PASTE, _note(), _report(), _METADATA
        )
    finally:
        await engine.dispose()
    (record,) = _failures(caplog)
    assert record.getMessage().startswith("persist_failed note_id=")
    assert _PASTE not in caplog.text


# --- the factory: read per request, built once (§9.6; L343) ---------------------------


@pytest.fixture
def fresh_sessions_cache() -> Iterator[None]:
    _sessions.cache_clear()
    yield
    _sessions.cache_clear()


@pytest.mark.usefixtures("fresh_sessions_cache")
def test_get_sessions_is_none_with_persistence_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.db.settings", Settings.model_validate({"persist_enabled": False}))
    assert get_sessions() is None


@pytest.mark.usefixtures("fresh_sessions_cache")
def test_get_sessions_builds_one_factory_whose_engine_hides_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Building the engine connects to nothing, so no database is needed here.
    url = "postgresql+asyncpg://localhost/notepilot_unused"
    monkeypatch.setattr(
        "backend.db.settings",
        Settings.model_validate({"persist_enabled": True, "database_url": url}),
    )
    sessions = get_sessions()
    assert sessions is not None
    assert get_sessions() is sessions  # one engine per process (§9.8's pool)
    assert sessions.kw["bind"].sync_engine.hide_parameters is True


# --- against the database (L345) ------------------------------------------------------


@pytest.mark.anyio
async def test_a_persisted_note_reads_back_whole(
    db_sessions: async_sessionmaker[AsyncSession],
) -> None:
    note_id, note, report = uuid.uuid4(), _note(), _report(judge_version="j" * 12)
    await persist(db_sessions, note_id, _PASTE, note, report, _METADATA)
    async with db_sessions() as session:
        row = (
            await session.execute(select(NoteRecord).where(NoteRecord.id == note_id))
        ).scalar_one()
    assert row.raw_text == _PASTE
    assert (row.checks_version, row.report["judge_version"]) == ("c" * 12, "j" * 12)
    assert (row.input_tokens, row.output_tokens, row.validation_attempts) == (11, 22, 2)
    assert (row.judge_input_tokens, row.judge_output_tokens) == (33, 44)
    assert row.note == note.model_dump(mode="json")
    assert row.report == report.model_dump(mode="json")
    assert row.created_at.tzinfo is not None  # timestamptz (L344)


@pytest.mark.anyio
async def test_a_duplicate_id_is_logged_and_swallowed(
    db_sessions: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    note_id = uuid.uuid4()
    for _ in range(2):
        await persist(db_sessions, note_id, _PASTE, _note(), _report(), _METADATA)
    async with db_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(NoteRecord)) == 1
    (record,) = _failures(caplog)
    assert "exc_type=IntegrityError" in record.getMessage()
    assert _PASTE not in caplog.text
