"""Persistence (spec §9.5, §9.6): the notes table, and the sink that writes a note to it.

An edge module (§13): the pipeline never imports it and never reads the database (invariant
8). persist() runs as a background task after the response, in a session of its own (§9.6),
from a factory get_sessions() hands the route per request, None with persistence off (L343).
A failed write is logged by type and frames, never by message (L342): a database's own error
text can echo the row, the paste included.
"""

import functools
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.config import settings
from backend.schemas import EvalReport, RunMetadata, SOAPNote
from backend.tracebacks import format_frames

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class NoteRecord(Base):
    """A relational envelope of lineage, with the note and its report whole as JSONB (§9.5).

    Every column is NOT NULL. The judge's version rides in the report, which names it, so it
    has no column of its own (L336, L344).
    """

    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)  # minted in the route (§9.1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    raw_text: Mapped[str] = mapped_column(Text)
    model_used: Mapped[str]
    prompt_version: Mapped[str]
    checks_version: Mapped[str]  # L57: verdicts stay readable across a lexicon change
    input_tokens: Mapped[int]  # summed across validation attempts (L13)
    output_tokens: Mapped[int]
    validation_attempts: Mapped[int]  # L57
    judge_input_tokens: Mapped[int]  # L7: the second call's cost
    judge_output_tokens: Mapped[int]
    production_critical_passed: Mapped[bool]  # one note's verdict, never a rate (§9.5)
    note: Mapped[dict[str, Any]] = mapped_column(JSONB)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)


def note_record(
    note_id: uuid.UUID, raw_text: str, note: SOAPNote, report: EvalReport, metadata: RunMetadata
) -> NoteRecord:
    """The row persist() writes: lineage from the metadata and the report, payloads whole."""
    return NoteRecord(
        id=note_id,
        raw_text=raw_text,
        model_used=metadata.model,
        prompt_version=metadata.prompt_version,
        checks_version=report.checks_version,
        input_tokens=metadata.usage.input_tokens,
        output_tokens=metadata.usage.output_tokens,
        validation_attempts=metadata.validation_attempts,
        judge_input_tokens=report.judge_usage.input_tokens,
        judge_output_tokens=report.judge_usage.output_tokens,
        production_critical_passed=report.all_critical_passed,
        note=note.model_dump(mode="json"),
        report=report.model_dump(mode="json"),
    )


@functools.cache
def _sessions() -> async_sessionmaker[AsyncSession]:
    """One engine per process (§9.8's pool), built on first use, never at import (L343).

    Only get_sessions calls it, with persist_enabled on, so boot has checked database_url
    (L341). hide_parameters keeps a row's values out of SQLAlchemy's error text.
    """
    if settings.database_url is None:
        raise RuntimeError("database_url is unset")
    engine = create_async_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    return async_sessionmaker(engine, expire_on_commit=False)


def get_sessions() -> async_sessionmaker[AsyncSession] | None:
    """The session factory when settings.persist_enabled, else None (§9.6, L343).

    Read per request at the edge, as get_judge is (L318); the function object is the override
    key route tests replace.
    """
    return _sessions() if settings.persist_enabled else None


async def persist(
    sessions: async_sessionmaker[AsyncSession] | None,
    note_id: uuid.UUID,
    raw_text: str,
    note: SOAPNote,
    report: EvalReport,
    metadata: RunMetadata,
) -> None:
    """Write one note in a session of its own (§9.6); never raise (invariant 8)."""
    if sessions is None:
        return
    try:
        async with sessions() as session:
            session.add(note_record(note_id, raw_text, note, report, metadata))
            await session.commit()
    except Exception as exc:  # the sink's boundary: nothing reaches the user or uvicorn (L342)
        logger.error(
            "persist_failed note_id=%s exc_type=%s frames=%s",
            note_id,
            type(exc).__name__,
            format_frames(exc),
        )
