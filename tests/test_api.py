"""Pins the /summarize HTTP boundary: its input, its judge, its error bodies, and its log lines
(spec §9.1, §9.4, §9.6, §9.8; L14, L53, L54, L69, L70, L71, L73, L76, L79, L80, L87, L98, L99,
L166, L318, L347, L350).

Every request goes through the default TestClient (raise_server_exceptions=True). The
catch-all turns any Exception raised inside the app into a 500, so a 500 alone proves
nothing: every 500 test asserts its own backend.api log line. An autouse fixture overrides
get_client with an EMPTY-script FakeLLMClient; a test that reaches the model without
installing its own script fails loudly on the fake's unscripted-call guard instead of
building a real client. The guard fails through pytest.fail, a BaseException that
`except Exception` can't swallow, so the catch-all can't turn a forgotten script into a 500
a test could pass on. The same fixture overrides get_judge, get_sessions, and get_budget with
None, pins the rate limit off, and empties the limiter's counts, so no test reaches a judge,
a database, a budget, or a limit it didn't install, whatever JUDGE_ENABLED, PERSIST_ENABLED,
DAILY_TOKEN_BUDGET, or RATE_LIMIT the shell exports.

Logging tests call caplog.set_level(logging.DEBUG): under pytest the root logger sits at
WARNING. Sentinel scans read caplog.text, every captured record as rendered, exc_info
included (L53); positive checks filter "backend.api" records through getMessage() (L79).
Sentinels go in values, never keys.

PHASE_1_REACH and NOT_UNTIL_PHASE_3 list §9.4's outcomes by phase (L73). Phase 3's admission
reaches the second (L350), so test_reach_is_exactly_the_declared_outcomes checks the two
together against the outcomes the error tests declare.
"""

import asyncio
import logging
import re
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, NamedTuple
from uuid import UUID

import httpx2
import pytest
from anthropic import (
    AnthropicError,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    OverloadedError,
    RateLimitError,
)
from anthropic.types import Message
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.types import Message as ASGIMessage

from backend.api import (
    BudgetExhaustedError,
    CatchAllMiddleware,
    DailyTokenBudget,
    RequestIdMiddleware,
    SummarizeResponse,
    _budget,
    app,
    get_budget,
    limiter,
)
from backend.config import Settings, settings
from backend.db import NoteRecord, get_sessions
from backend.evals.checks import clause_text
from backend.evals.judge import Judge
from backend.evals.registry import REGISTRY, Check, CheckFn, Finding, register_check
from backend.evals.runner import CHECKS_VERSION
from backend.grounding import ground
from backend.judge_client import AnthropicJudge, _user_message, get_judge
from backend.orchestrator import PROMPT_VERSION, OrchestratorError, get_client
from backend.schemas import (
    ChecksConfig,
    EvalCase,
    Severity,
    SOAPNote,
    SOAPNoteDraft,
    TokenUsage,
)
from tests.fakes import (
    FakeJudge,
    FakeJudgeClient,
    FakeLLMClient,
    entail_all_but,
    text_message,
    tool_use_message,
)
from tests.fresh import run_fresh

# Planted inside raw_text as a VALUE (L53): the paste, which must reach neither a body nor a
# log line. Shorter than the content lengths the tests build around it.
SENTINEL: Final = "sentinel-7f3a"
VALID_INPUT: Final[dict[str, object]] = {
    "claims": [{"text": "fact-1", "section": "S", "source_quote": "quote-1"}]
}
RID_RE: Final = re.compile(r"[0-9a-f]{32}")  # uuid4().hex (L73)


class _Outcome(NamedTuple):
    """One §9.4 row as the client sees it: the status and the body's code."""

    status: int
    code: str


# L73: the §9.4 rows phase 1 can reach, as (status, code) pairs because 503 alone names two
# codes; and the two that wait for phase 3. Framework codes (L80) are in neither set.
PHASE_1_REACH: Final[frozenset[_Outcome]] = frozenset(
    {
        _Outcome(422, "input_invalid"),
        _Outcome(502, "output_truncated"),
        _Outcome(502, "model_output_invalid"),
        _Outcome(503, "upstream_busy"),
        _Outcome(504, "upstream_timeout"),
        _Outcome(502, "upstream_error"),
        _Outcome(500, "internal_error"),
    }
)
NOT_UNTIL_PHASE_3: Final[frozenset[_Outcome]] = frozenset(
    {_Outcome(429, "rate_limited"), _Outcome(503, "budget_exhausted")}
)
# The outcomes the 422, 500, and admission tests assert, as constants those tests read.
_INPUT_INVALID: Final = _Outcome(422, "input_invalid")
_INTERNAL_ERROR: Final = _Outcome(500, "internal_error")
_RATE_LIMITED: Final = _Outcome(429, "rate_limited")
_BUDGET_EXHAUSTED: Final = _Outcome(503, "budget_exhausted")

Installer = Callable[[Sequence[Message | Exception]], FakeLLMClient]


@pytest.fixture(autouse=True)
def install_fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[Installer]:
    """Overrides get_client, get_judge, get_sessions, and get_budget for every test, pins the
    rate limit off, and empties the limiter's counts; restores the prior overrides after.

    Starts with an EMPTY script: a test that reaches the model without installing its own
    fails on the fake's unscripted-call guard, never by building a real client. The judge is
    None until a test installs one (L318), and so are the sessions (L347) and the budget
    (L350); the rate limit is None until a test sets one.
    """
    prior = dict(app.dependency_overrides)

    def install(script: Sequence[Message | Exception]) -> FakeLLMClient:
        fake = FakeLLMClient(script)
        app.dependency_overrides[get_client] = lambda: fake
        return fake

    install([])
    app.dependency_overrides[get_judge] = lambda: None
    app.dependency_overrides[get_sessions] = lambda: None
    app.dependency_overrides[get_budget] = lambda: None
    _set_rate_limit(monkeypatch, None)
    limiter.reset()
    try:
        yield install
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prior)
        limiter.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _content(n: int) -> str:
    """n non-whitespace characters, the sentinel in front."""
    assert n >= len(SENTINEL)
    return SENTINEL + "x" * (n - len(SENTINEL))


def _decoy() -> Message:
    # A valid response for tests that must NOT reach the model: a mutant that lets the
    # input through dies at the status assertion, not at the fake's unscripted-call guard.
    return tool_use_message(VALID_INPUT)


def _route() -> APIRoute:
    return next(r for r in app.routes if isinstance(r, APIRoute) and r.path == "/summarize")


# --- the happy path and the wire shape (§9.1; L76, L87, L166) ------------------------

# VALID_INPUT's quote behind leading whitespace: its span is an offset into the exact paste,
# so a stripped paste shifts it. The content clears min_input_chars.
GROUNDED_PASTE: Final = "  quote-1 " + "x" * (settings.min_input_chars + 10) + "  "


def test_happy_path_returns_note_report_and_metadata(
    client: TestClient, install_fake: Installer
) -> None:
    fake = install_fake([tool_use_message(VALID_INPUT, input_tokens=123, output_tokens=456)])
    response = client.post("/summarize", json={"raw_text": GROUNDED_PASTE})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"note_id", "note", "report", "metadata"}  # L166: the 2a edge shape
    assert UUID(body["note_id"]).version == 4
    (claim,) = body["note"]["claims"]
    fields = ("id", "text", "section", "source_quote", "source_span", "flags")
    assert [claim[f] for f in fields] == [0, "fact-1", "S", "quote-1", [2, 9], []]
    report = body["report"]
    # production runs the checks that need neither an answer key nor a judge (§8.7)
    assert set(report["checks_run"]) == {
        name for name, c in REGISTRY.items() if not (c.requires_reference or c.needs_judge)
    }
    assert {"must_preserve", "must_not_add"}.isdisjoint(report["checks_run"])
    assert report["checks_version"] == CHECKS_VERSION
    assert report["all_critical_passed"] is True  # the verdict travels with the report (L102)
    assert report["judge_usage"] == {"input_tokens": 0, "output_tokens": 0}  # no judge (L7)
    assert report["checks_config"] == settings.checks_config().model_dump()  # L334
    assert report["judge_version"] is None  # L336: no judge
    assert body["metadata"]["model"] == settings.model
    assert body["metadata"]["prompt_version"] == PROMPT_VERSION
    assert body["metadata"]["usage"] == {"input_tokens": 123, "output_tokens": 456}
    assert body["metadata"]["validation_attempts"] == 1
    assert len(fake.messages.calls) == 1
    assert fake.messages.calls[0].messages[0]["content"] == GROUNDED_PASTE  # L87: never mutated


def _record_into(
    seen: list[tuple[SOAPNote, str, EvalCase | None, ChecksConfig]],
) -> CheckFn:
    def record(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
    ) -> list[Finding]:
        seen.append((note, raw_text, case, config))
        return []

    return record


def _judged_clean(
    note: SOAPNote,
    raw_text: str,
    case: EvalCase | None = None,
    *,
    config: ChecksConfig,
    judge: Judge,
) -> list[Finding]:
    return []


def test_route_checks_the_note_it_returns_against_the_exact_paste(
    client: TestClient, install_fake: Installer, registry: dict[str, Check]
) -> None:
    # registry is emptied for the test, so the route selects among these three alone
    seen: list[tuple[SOAPNote, str, EvalCase | None, ChecksConfig]] = []
    register_check(name="recorder", severity=Severity.WARNING)(_record_into(seen))
    register_check(name="reference", severity=Severity.WARNING, requires_reference=True)(
        _record_into(seen)
    )
    register_check(name="judged", severity=Severity.WARNING, needs_judge=True)(_judged_clean)
    install_fake([tool_use_message(VALID_INPUT)])
    body = client.post("/summarize", json={"raw_text": GROUNDED_PASTE}).json()
    assert set(body["report"]["checks_run"]) == {"recorder"}  # production mode, no judge
    ((note, raw_text, case, config),) = seen
    assert note.model_dump(mode="json") == body["note"]
    assert raw_text == GROUNDED_PASTE  # L87: never stripped
    assert case is None
    assert config == settings.checks_config()  # L187: built at the edge, from settings


# --- the judge in the route (§9.1, §14; invariant 7; L318) ------------------------------


def test_route_hands_get_judges_judge_to_the_checks(
    client: TestClient, install_fake: Installer
) -> None:
    # L318: with a judge, production mode selects the judged check, and the report carries
    # the judge's usage (L7) and its version (L336)
    judge = FakeJudge(
        usage=TokenUsage(input_tokens=7, output_tokens=3), script=entail_all_but("fact-1")
    )
    app.dependency_overrides[get_judge] = lambda: judge
    install_fake([tool_use_message(VALID_INPUT)])
    report = client.post("/summarize", json={"raw_text": GROUNDED_PASTE}).json()["report"]
    assert "text_entailment_judge" in report["checks_run"]
    (judged,) = [r for r in report["results"] if r["check"] == "text_entailment_judge"]
    assert (judged["severity"], judged["passed"], judged["claim_ids"]) == ("warning", False, [0])
    assert report["judge_usage"] == {"input_tokens": 7, "output_tokens": 3}
    assert report["judge_version"] == judge.version
    assert [[text for text, _ in call] for call in judge.calls] == [["fact-1"]]


def _critical(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in body["report"]["results"] if r["severity"] == "critical"]


def test_a_judge_timeout_errors_its_check_and_the_note_returns(
    client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    # §14, invariant 7: a judge that times out errors its WARNING alone; the note returns, and
    # the CRITICAL results are a run's without the judge. The real APITimeoutError on purpose:
    # the app maps it to 504 (§9.4), and a judge's must never reach that handler.
    caplog.set_level(logging.DEBUG)
    install_fake([tool_use_message(VALID_INPUT), tool_use_message(VALID_INPUT)])
    off = client.post("/summarize", json={"raw_text": GROUNDED_PASTE}).json()
    draft = SOAPNoteDraft.model_validate(VALID_INPUT)
    (claim,) = ground(draft, GROUNDED_PASTE, config=settings.checks_config()).claims
    clause = clause_text(claim, GROUNDED_PASTE)
    assert clause is not None
    judge_client = FakeJudgeClient({_user_message(claim.text, clause): _timeout_error()})
    app.dependency_overrides[get_judge] = lambda: AnthropicJudge(judge_client)
    response = client.post("/summarize", json={"raw_text": GROUNDED_PASTE})
    assert response.status_code == 200
    on = response.json()
    assert on["note"] == off["note"]
    (judged,) = [r for r in on["report"]["results"] if r["check"] == "text_entailment_judge"]
    assert (judged["severity"], judged["passed"], judged["errored"]) == ("warning", False, True)
    assert _critical(on) == _critical(off)
    assert on["report"]["all_critical_passed"] is off["report"]["all_critical_passed"] is True
    assert len(judge_client.messages.calls) == 1
    assert "check=text_entailment_judge exc_type=APITimeoutError " in caplog.text
    assert "upstream_timeout" not in caplog.text
    assert CAUSE_SENTINEL not in caplog.text  # invariant 19: frames only, never the cause


def test_response_model_is_the_edge_shape() -> None:
    assert _route().response_model is SummarizeResponse  # L76: never SummarizationResult
    assert SummarizeResponse.__module__ == "backend.api"  # §13: an HTTP edge shape


# --- persistence in the route (§9.6, §14; invariant 8; L347) ---------------------------


@pytest.mark.anyio
async def test_a_summarized_note_is_in_its_row_after_the_response(
    client: TestClient, install_fake: Installer, db_sessions: async_sessionmaker[AsyncSession]
) -> None:
    # §14's integration test. The row is read in a session of the test's own, after the
    # request: persist's session is its own too (§9.6), never the request's.
    install_fake([tool_use_message(VALID_INPUT, input_tokens=123, output_tokens=456)])
    app.dependency_overrides[get_sessions] = lambda: db_sessions
    response = client.post("/summarize", json={"raw_text": GROUNDED_PASTE})
    assert response.status_code == 200
    body = response.json()
    async with db_sessions() as session:
        row = await session.get(NoteRecord, UUID(body["note_id"]))
    assert row is not None
    assert row.raw_text == GROUNDED_PASTE  # the exact paste, as the spans index it (L87)
    assert (row.note, row.report) == (body["note"], body["report"])
    metadata = body["metadata"]
    assert (row.model_used, row.prompt_version) == (metadata["model"], metadata["prompt_version"])
    assert (row.input_tokens, row.output_tokens) == (123, 456)


def test_a_failed_write_still_answers_200_and_logs_no_paste(
    client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    # Invariant 8: a database that refuses at once (port 1) costs the user nothing. NullPool
    # keeps nothing open, so the engine needs no disposing.
    caplog.set_level(logging.DEBUG)
    install_fake([tool_use_message(VALID_INPUT)])
    engine = create_async_engine(
        "postgresql+asyncpg://localhost:1/none", hide_parameters=True, poolclass=pool.NullPool
    )
    app.dependency_overrides[get_sessions] = lambda: async_sessionmaker(engine)
    response = client.post("/summarize", json={"raw_text": GROUNDED_PASTE})
    assert response.status_code == 200
    (record,) = [r for r in caplog.records if r.name == "backend.db"]
    note_id = response.json()["note_id"]
    assert record.getMessage().startswith(f"persist_failed note_id={note_id} exc_type=")
    assert GROUNDED_PASTE not in caplog.text


# --- 422 input_invalid: the INPUT is the problem (§9.4; L53, L70, L73, L79, L87) -----

# Each rejected input carries the sentinel inside raw_text. Typed builders keyed by case
# name (the test_orchestrator pattern): the malformed-JSON case sends raw bytes.
_REJECTED: Final[dict[str, Callable[[TestClient], httpx2.Response]]] = {
    "oversized": lambda c: c.post(
        "/summarize", json={"raw_text": _content(settings.max_input_chars + 1)}
    ),
    "undersized": lambda c: c.post(
        "/summarize", json={"raw_text": _content(settings.min_input_chars - 1)}
    ),
    # L87: total length within the bounds, content shorter than min
    "whitespace-padded": lambda c: c.post(
        "/summarize",
        json={
            "raw_text": " " * settings.min_input_chars
            + _content(settings.min_input_chars - 1)
            + " " * settings.min_input_chars
        },
    ),
    "malformed-json": lambda c: c.post(
        "/summarize",
        content=('{"raw_text": "' + SENTINEL).encode(),
        headers={"content-type": "application/json"},
    ),
}


@pytest.mark.parametrize("case", list(_REJECTED))
def test_rejected_input_is_422_without_echo(
    case: str, client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    fake = install_fake([_decoy()])
    response = _REJECTED[case](client)
    assert response.status_code == _INPUT_INVALID.status
    assert SENTINEL not in response.text  # L53, L70: the paste never comes back
    body = response.json()
    rid = body.get("request_id")  # .get: an absent key must fail the shape assert below
    assert body == {"error": _INPUT_INVALID.code, "request_id": rid}  # §9.4: one shape
    assert RID_RE.fullmatch(rid)  # L73: uuid4().hex
    assert fake.messages.calls == []  # rejected before any spend
    assert SENTINEL not in caplog.text  # L53: rendered records, exc_info included
    ours = [
        r
        for r in caplog.records
        if r.name == "backend.api"
        and "code=input_invalid" in r.getMessage()
        and f"request_id={rid}" in r.getMessage()
    ]
    assert len(ours) == 1  # L70, L79: logged by code, fields rendered in the message
    assert ours[0].levelno == logging.WARNING


# --- the bounds (§9.1, §10) ------------------------------------------------------------


def test_max_input_chars_boundary_accepted(client: TestClient, install_fake: Installer) -> None:
    """Exactly max_input_chars is accepted: max_length is inclusive (pydantic).

    max_length is evaluated at import, so the boundary is pinned only at the default value:
    a hard-coded literal equal to the default would pass. The same accepted limit as
    CALL_CONFIG's max_tokens in test_orchestrator.
    """
    fake = install_fake([_decoy()])
    response = client.post("/summarize", json={"raw_text": "x" * settings.max_input_chars})
    assert response.status_code == 200
    assert len(fake.messages.calls) == 1  # the decoy was reached


@pytest.mark.parametrize(
    ("length", "status"), [(40, 200), (39, 422)], ids=["40-accepted", "39-rejected"]
)
def test_min_input_chars_is_read_at_call_time(
    length: int,
    status: int,
    client: TestClient,
    install_fake: Installer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A non-default value on purpose (the test_orchestrator precedent): at the default, a
    # literal equal to it would change nothing observable. The guard reads settings at call
    # time, unlike max_length (test_max_input_chars_boundary_accepted).
    patched = Settings.model_validate({"min_input_chars": 40})
    assert patched.min_input_chars != settings.min_input_chars
    monkeypatch.setattr("backend.api.settings", patched)
    install_fake([_decoy()])
    response = client.post("/summarize", json={"raw_text": "x" * length})
    assert response.status_code == status


# --- admission: the rate limit, then the reservation (§9.4, §9.8; L350) -----------------

# One request's reservation: what admit charges, read from settings as admit reads it.
_RESERVATION: Final = settings.max_request_tokens
# TEST-NET-1 (RFC 5737): addresses reserved for documentation, so no real client's.
_CLIENT_A: Final = ("192.0.2.1", 50000)
_CLIENT_B: Final = ("192.0.2.2", 50000)


def _set_rate_limit(monkeypatch: pytest.MonkeyPatch, limit: str | None) -> None:
    """The route's rate limit for this test; admit reads it per request."""
    monkeypatch.setattr("backend.api.settings", settings.model_copy(update={"rate_limit": limit}))


class _UtcClock:
    """The budget's clock, set by the test: its day turns over with no sleep."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _EpochClock:
    """A settable time.time: slowapi's window and the 429's Retry-After both read it."""

    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _install_budget(cap: int, clock: Callable[[], datetime] | None = None) -> DailyTokenBudget:
    """A fresh counter for this test, as get_budget's; the default clock is a fixed noon."""
    budget = DailyTokenBudget(cap, clock or _UtcClock(datetime(2026, 10, 27, 12, tzinfo=UTC)))
    app.dependency_overrides[get_budget] = lambda: budget
    return budget


def _summarize(client: TestClient) -> httpx2.Response:
    # A paste that clears min_input_chars, with the sentinel in it (L53).
    return client.post("/summarize", json={"raw_text": _content(settings.min_input_chars + 10)})


def _assert_refused(
    response: httpx2.Response, outcome: _Outcome, caplog: pytest.LogCaptureFixture
) -> None:
    """§9.4's one shape, a Retry-After, no paste, and one admission_refused line (L79)."""
    assert response.status_code == outcome.status
    assert SENTINEL not in response.text  # L53
    body = response.json()
    rid = body.get("request_id")  # .get: an absent key must fail the shape assert below
    assert body == {"error": outcome.code, "request_id": rid}
    assert RID_RE.fullmatch(rid)
    retry_after = response.headers["Retry-After"]
    assert retry_after.isdigit()
    assert SENTINEL not in caplog.text
    line = f"admission_refused code={outcome.code} request_id={rid} retry_after={retry_after}"
    ours = [r for r in caplog.records if r.name == "backend.api" and r.getMessage() == line]
    assert len(ours) == 1
    assert ours[0].levelno == logging.WARNING


def test_a_request_over_its_rate_limit_is_429_and_reserves_nothing(
    client: TestClient, install_fake: Installer, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The limit is checked before the reservation (L350): measured, a limit checked after it
    # let a client over its limit drain the cap. Room for three reservations, so a 429 that
    # reserved would turn the fourth request into a 503, and leave no room for the fifth.
    _set_rate_limit(monkeypatch, "2/minute")
    _install_budget(3 * _RESERVATION)
    fake = install_fake([_decoy() for _ in range(3)])
    statuses = [_summarize(client).status_code for _ in range(4)]
    assert statuses == [200, 200, _RATE_LIMITED.status, _RATE_LIMITED.status]
    _set_rate_limit(monkeypatch, None)
    assert _summarize(client).status_code == 200  # the third reservation was still free
    assert len(fake.messages.calls) == 3


def test_rate_limited_has_the_one_shape_and_is_logged_by_code(
    client: TestClient,
    install_fake: Installer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    _set_rate_limit(monkeypatch, "1/minute")
    fake = install_fake([_decoy()])
    assert _summarize(client).status_code == 200
    _assert_refused(_summarize(client), _RATE_LIMITED, caplog)
    assert len(fake.messages.calls) == 1  # refused before any spend


def test_rate_limited_retry_after_counts_down_to_the_windows_reset(
    client: TestClient, install_fake: Installer, monkeypatch: pytest.MonkeyPatch
) -> None:
    # time.time frozen: slowapi's window opens at the first request and resets 60 s later.
    clock = _EpochClock(1_800_000_000.0)
    monkeypatch.setattr(time, "time", clock)
    _set_rate_limit(monkeypatch, "1/minute")
    install_fake([_decoy(), _decoy()])
    assert _summarize(client).status_code == 200
    assert _summarize(client).headers["Retry-After"] == "60"
    clock.now += 59.25
    assert _summarize(client).headers["Retry-After"] == "1"  # 0.75 s left, rounded up
    clock.now += 0.75
    assert _summarize(client).status_code == 200  # the window has reset


def test_the_rate_limit_is_per_client(
    install_fake: Installer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_rate_limit(monkeypatch, "1/minute")
    install_fake([_decoy(), _decoy()])
    first, second = TestClient(app, client=_CLIENT_A), TestClient(app, client=_CLIENT_B)
    assert [_summarize(first).status_code for _ in range(2)] == [200, _RATE_LIMITED.status]
    assert _summarize(second).status_code == 200  # a bucket of its own


def test_no_rate_limit_unless_one_is_set(
    client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    # The fixture leaves the limit unset: slowapi is never asked, so it logs nothing either.
    caplog.set_level(logging.DEBUG)
    install_fake([_decoy() for _ in range(3)])
    assert [_summarize(client).status_code for _ in range(3)] == [200, 200, 200]
    assert [r.getMessage() for r in caplog.records if r.name == "slowapi"] == []


def test_the_budget_admits_what_it_can_reserve_and_no_more(
    client: TestClient, install_fake: Installer
) -> None:
    # One token short of four reservations: three fit, the fourth doesn't.
    _install_budget(4 * _RESERVATION - 1)
    fake = install_fake([_decoy() for _ in range(3)])
    statuses = [_summarize(client).status_code for _ in range(4)]
    assert statuses == [200, 200, 200, _BUDGET_EXHAUSTED.status]
    assert len(fake.messages.calls) == 3


def test_budget_exhausted_has_the_one_shape_and_is_logged_by_code(
    client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    _install_budget(_RESERVATION)
    fake = install_fake([_decoy()])
    assert _summarize(client).status_code == 200
    _assert_refused(_summarize(client), _BUDGET_EXHAUSTED, caplog)
    assert len(fake.messages.calls) == 1  # refused before any spend


def test_the_budget_resets_at_utc_midnight(client: TestClient, install_fake: Installer) -> None:
    # Exactly one reservation's room: the first request fits, the second waits for midnight.
    clock = _UtcClock(datetime(2026, 10, 27, 23, 59, 59, 250_000, tzinfo=UTC))
    _install_budget(_RESERVATION, clock)
    install_fake([_decoy(), _decoy()])
    assert _summarize(client).status_code == 200
    refused = _summarize(client)
    assert refused.status_code == _BUDGET_EXHAUSTED.status
    assert refused.headers["Retry-After"] == "1"  # 0.75 s to midnight, rounded up
    clock.now = datetime(2026, 10, 28, tzinfo=UTC)
    assert _summarize(client).status_code == 200


def test_a_rejected_paste_reserves_nothing(client: TestClient, install_fake: Installer) -> None:
    # admit takes the validated request (L350): measured, a dependency that didn't take it ran
    # even when the body failed validation.
    _install_budget(_RESERVATION)
    install_fake([_decoy()])
    oversized = {"raw_text": _content(settings.max_input_chars + 1)}
    assert client.post("/summarize", json=oversized).status_code == _INPUT_INVALID.status
    assert _summarize(client).status_code == 200  # the one reservation was still free


def test_a_failed_request_keeps_its_reservation(
    client: TestClient, install_fake: Installer
) -> None:
    # No refund (§9.8): the cap charges the reservation, not what the call used.
    _install_budget(_RESERVATION)
    install_fake([_timeout_error(), _decoy()])
    assert _summarize(client).status_code == 504
    assert _summarize(client).status_code == _BUDGET_EXHAUSTED.status


@pytest.mark.anyio
async def test_gathered_requests_never_reserve_past_the_cap(install_fake: Installer) -> None:
    # Eight at once against room for three: three are admitted, and only three reach the model.
    _install_budget(3 * _RESERVATION)
    fake = install_fake([_decoy() for _ in range(8)])
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://testserver") as http:
        responses = await asyncio.gather(
            *(http.post("/summarize", json={"raw_text": GROUNDED_PASTE}) for _ in range(8))
        )
    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200] * 3 + [_BUDGET_EXHAUSTED.status] * 5
    assert len(fake.messages.calls) == 3


@pytest.mark.anyio
async def test_get_budget_builds_the_processs_one_counter_from_the_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Called directly: route tests override it. A cap of two reservations, not a default.
    monkeypatch.setattr(
        "backend.api.settings", settings.model_copy(update={"daily_token_budget": None})
    )
    assert get_budget() is None
    budgeted = settings.model_copy(
        update={"max_validation_retries": 0, "daily_token_budget": 2 * _RESERVATION}
    )
    monkeypatch.setattr("backend.api.settings", budgeted)
    _budget.cache_clear()
    try:
        budget = get_budget()
        assert budget is not None
        assert get_budget() is budget  # one counter per process (L343's pattern)
        await budget.reserve(_RESERVATION)
        await budget.reserve(_RESERVATION)
        with pytest.raises(BudgetExhaustedError):
            await budget.reserve(1)
    finally:
        _budget.cache_clear()


# --- request ids and the middleware stack (L73) ----------------------------------------


def test_request_ids_differ_per_request(client: TestClient) -> None:
    short = {"raw_text": _content(settings.min_input_chars - 1)}
    first = client.post("/summarize", json=short).json()["request_id"]
    second = client.post("/summarize", json=short).json()["request_id"]
    assert first != second  # minted per request, not per process


def test_user_middleware_order() -> None:
    # Outermost first. The order is invisible through any body: both middlewares share
    # scope["state"], so a catch-all registered OUTSIDE the request-id middleware still finds
    # the id by the time an exception reaches it. Only the stack itself can pin it.
    classes: list[object] = [m.cls for m in app.user_middleware]
    assert classes == [RequestIdMiddleware, CatchAllMiddleware]


# --- 500 internal_error: the catch-all (§9.4, §9.8; L53, L69, L73, L79) ----------------

# Planted in an exception, not the paste: the message and the chained cause are the two
# strings the 500 path must keep out of the body and every log record (L69). Distinct from
# SENTINEL and from each other, so a failing assertion names which leak it caught.
MESSAGE_SENTINEL: Final = "sentinel-msg-4c21"
CAUSE_SENTINEL: Final = "sentinel-cause-9e07"
# A fixed id for the ASGI-level tests, where no RequestIdMiddleware runs.
_FIXED_RID: Final = "0123456789abcdef0123456789abcdef"
_UNHANDLED_RE: Final = re.compile(
    r"unhandled_exception code=internal_error request_id=(?P<rid>[0-9a-f]{32}) "
    r"exc_type=_Unexpected frames=(?P<frames>\S+)"
)


class _Unexpected(Exception):
    """Never a builtin: a hard-coded exc_type literal must not be able to match the name."""


def _chained_unexpected() -> _Unexpected:
    """A FRESH instance per call: raising writes __traceback__, so no instance is shared."""
    exc = _Unexpected(MESSAGE_SENTINEL)
    exc.__cause__ = ValueError(CAUSE_SENTINEL)
    return exc


def test_unhandled_exception_is_500_logged_by_structure(
    client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    fake = install_fake([_chained_unexpected()])
    response = client.post("/summarize", json={"raw_text": "x" * (settings.min_input_chars + 10)})
    assert response.status_code == _INTERNAL_ERROR.status
    assert MESSAGE_SENTINEL not in response.text  # L53, L69: never the message
    assert CAUSE_SENTINEL not in response.text  # nor the chained cause
    body = response.json()
    rid = body.get("request_id")  # .get: an absent key must fail the shape assert below
    assert body == {"error": _INTERNAL_ERROR.code, "request_id": rid}  # §9.4: one shape
    assert RID_RE.fullmatch(rid)  # L73
    assert len(fake.messages.calls) == 1  # recorded, then raised
    assert MESSAGE_SENTINEL not in caplog.text  # L69: no str(exc), no exc_info
    assert CAUSE_SENTINEL not in caplog.text  # L69: no chained cause
    ours = [
        r
        for r in caplog.records
        if r.name == "backend.api" and "code=internal_error" in r.getMessage()
    ]
    assert len(ours) == 1  # L79: logged by code, fields rendered in the message
    assert ours[0].levelno == logging.ERROR
    match = _UNHANDLED_RE.fullmatch(ours[0].getMessage())
    assert match
    assert match["rid"] == rid
    frames = match["frames"].split(">")
    # a repo frame (the route), an installed one (FastAPI's routing, after site-packages),
    # and the fake's raise as the innermost entry
    assert any(
        f.startswith("backend/api.py:") and f.endswith(":summarize_endpoint") for f in frames
    )
    assert any(f.startswith("fastapi/routing.py:") for f in frames)  # after site-packages
    assert re.fullmatch(r"tests/fakes\.py:\d+:create", frames[-1])  # innermost last


def test_forgotten_script_fails_loudly(client: TestClient) -> None:
    # The autouse EMPTY script. The guard fails through pytest.fail, a BaseException: the
    # catch-all's `except Exception` can't turn a forgotten script into a 500 this test
    # could pass on.
    with pytest.raises(pytest.fail.Exception, match="unscripted create call #1"):
        client.post("/summarize", json={"raw_text": "x" * (settings.min_input_chars + 10)})


# The catch-all's other two branches, driven at the ASGI level: no route can raise after the
# response has started, and nothing in the app raises during lifespan.


async def _drive(middleware: ASGIApp, scope: Scope) -> tuple[list[ASGIMessage], Exception | None]:
    """One ASGI call through `middleware`: what it sent, and the Exception that escaped.

    Catches Exception only, so pytest.fail still propagates.
    """
    sent: list[ASGIMessage] = []

    async def receive() -> ASGIMessage:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    try:
        await middleware(scope, receive, send)
    except Exception as exc:
        return sent, exc
    return sent, None


@pytest.mark.anyio
async def test_catch_all_after_response_start_logs_and_returns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Past this middleware, ServerErrorMiddleware re-raises and the server logs exc_info,
    # message and chained cause included: the only L69-safe move is to log and return.
    caplog.set_level(logging.DEBUG)

    async def starts_then_raises(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise _chained_unexpected()

    scope: Scope = {"type": "http", "state": {"request_id": _FIXED_RID}}
    sent, escaped = await _drive(CatchAllMiddleware(starts_then_raises), scope)
    assert escaped is None  # never re-raised
    assert [m["type"] for m in sent] == ["http.response.start"]  # nothing sent after it
    assert MESSAGE_SENTINEL not in caplog.text
    assert CAUSE_SENTINEL not in caplog.text
    ours = [
        r
        for r in caplog.records
        if r.name == "backend.api"
        and "code=internal_error" in r.getMessage()
        and f"request_id={_FIXED_RID}" in r.getMessage()
    ]
    assert len(ours) == 1


@pytest.mark.anyio
async def test_catch_all_passes_non_http_scopes_through() -> None:
    exc = _chained_unexpected()

    async def raises(scope: Scope, receive: Receive, send: Send) -> None:
        raise exc

    sent, escaped = await _drive(CatchAllMiddleware(raises), {"type": "lifespan"})
    assert escaped is exc  # untouched: the object itself, not handled, not wrapped
    assert sent == []


# --- framework errors in the one shape (§9.4; L73, L79, L80, L98) -----------------------


@dataclass(frozen=True)
class _FrameworkCase:
    send: Callable[[TestClient], httpx2.Response]
    status: int
    code: str
    allow: str | None  # the exception's Allow header, which RFC 9110 requires on a 405 (L98)


_FRAMEWORK: Final[dict[str, _FrameworkCase]] = {
    "not-found": _FrameworkCase(lambda c: c.get("/nope"), 404, "not_found", None),
    "method-not-allowed": _FrameworkCase(
        lambda c: c.get("/summarize"), 405, "method_not_allowed", "POST"
    ),
    # A JSON body that is not valid UTF-8. FastAPI raises it as an HTTPException(400), not a
    # RequestValidationError: json.loads fails with UnicodeDecodeError, not JSONDecodeError,
    # so the body never reaches validation. The handler's default branch.
    "unparseable-body": _FrameworkCase(
        lambda c: c.post(
            "/summarize",
            content=b'{"raw_text": "\xff"}',
            headers={"content-type": "application/json"},
        ),
        400,
        "http_error",
        None,
    ),
}


@pytest.mark.parametrize("case", list(_FRAMEWORK))
def test_framework_error_has_the_one_shape(
    case: str, client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    fake = install_fake([_decoy()])
    expected = _FRAMEWORK[case]
    response = expected.send(client)
    assert response.status_code == expected.status
    body = response.json()
    rid = body.get("request_id")  # .get: an absent key must fail the shape assert below
    assert body == {"error": expected.code, "request_id": rid}  # §9.4: one shape, never detail
    assert RID_RE.fullmatch(rid)  # L73
    assert response.headers.get("allow") == expected.allow  # L98: the exception's headers
    assert fake.messages.calls == []  # rejected before any spend
    message = f"framework_error code={expected.code} status={expected.status} request_id={rid}"
    ours = [r for r in caplog.records if r.name == "backend.api" and r.getMessage() == message]
    assert len(ours) == 1  # L79: the whole line, so an extra field fails here
    assert ours[0].levelno == logging.WARNING


# --- 502 model output failures (§9.4; L14, L53, L73, L79) --------------------------------

# Planted in the model's output as a VALUE (L53): beside the paste, the string the 502 path
# must keep out of the body and every log record. Distinct from every other sentinel, so a
# failing assertion names which leak it caught.
MODEL_SENTINEL: Final = "sentinel-model-3b8e"
# VALID_INPUT's claim plus a stray key whose VALUE is the sentinel. The schema forbids extra
# keys, so the ValidationError chained to the final ModelOutputError carries it as input_value.
_INVALID_INPUT: Final[dict[str, object]] = {
    "claims": [
        {"text": "fact-1", "section": "S", "source_quote": "quote-1", "stray": MODEL_SENTINEL}
    ]
}


def _retries_exhausted() -> list[Message]:
    """Every attempt invalid, max_validation_retries + 1 of them, with distinct tool_use_ids."""
    attempts = settings.max_validation_retries + 1
    invalid = [
        tool_use_message(_INVALID_INPUT, tool_use_id=f"toolu_fake_{i}")
        for i in range(1, attempts + 1)
    ]
    return [*invalid, _decoy()]


@dataclass(frozen=True)
class _ModelOutputCase:
    script: Callable[[], list[Message]]
    calls: int  # create calls the orchestrator makes before it gives up
    status: int
    code: str


# Every script ends in a decoy: an orchestrator that kept going returns 200 and dies at the
# status assertion, not at the fake's unscripted-call guard.
# L73: model_output_invalid is reached twice (no tool block; a refusal with no tool block), so
# the refusal path is pinned behavior, not an accident of the missing-block branch.
_MODEL_OUTPUT: Final[dict[str, _ModelOutputCase]] = {
    "truncated": _ModelOutputCase(
        lambda: [tool_use_message(VALID_INPUT, stop_reason="max_tokens"), _decoy()],
        1,
        502,
        "output_truncated",
    ),
    "no-tool-block": _ModelOutputCase(
        lambda: [text_message("no tool call"), _decoy()], 1, 502, "model_output_invalid"
    ),
    "refusal-no-tool-block": _ModelOutputCase(
        lambda: [text_message("refused", stop_reason="refusal"), _decoy()],
        1,
        502,
        "model_output_invalid",
    ),
    "retries-exhausted": _ModelOutputCase(
        _retries_exhausted, settings.max_validation_retries + 1, 502, "model_output_invalid"
    ),
}


@pytest.mark.parametrize("case", list(_MODEL_OUTPUT))
def test_model_output_failure_is_502_by_code(
    case: str, client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    expected = _MODEL_OUTPUT[case]
    fake = install_fake(expected.script())
    response = client.post("/summarize", json={"raw_text": _content(settings.min_input_chars + 10)})
    assert response.status_code == expected.status
    assert SENTINEL not in response.text  # L53: the paste never comes back
    assert MODEL_SENTINEL not in response.text  # L53: nor the model's output, via the cause
    body = response.json()
    rid = body.get("request_id")  # .get: an absent key must fail the shape assert below
    assert body == {"error": expected.code, "request_id": rid}  # §9.4: the exception's own code
    assert RID_RE.fullmatch(rid)  # L73
    assert len(fake.messages.calls) == expected.calls  # 1 when it fails fast; else retries + 1
    assert SENTINEL not in caplog.text  # L53: rendered records, exc_info included
    assert MODEL_SENTINEL not in caplog.text  # L53: a chained ValidationError never renders
    message = f"model_output_failure code={expected.code} request_id={rid}"
    ours = [r for r in caplog.records if r.name == "backend.api" and r.getMessage() == message]
    assert len(ours) == 1  # L79: the whole line, so an extra field fails here
    assert ours[0].levelno == logging.WARNING


# --- upstream failures, attributed by status (§9.4; L54, L71, L99) -----------------------

# The SDK builds a status error's message from the body, so the body is how upstream text
# would reach str(exc). Planted in the body; distinct from every other sentinel.
BODY_SENTINEL: Final = "sentinel-body-5d1c"
# One sentinel per surface the builders below plant text in (L53): the paste in the request,
# upstream's text in the message and the body, the transport's in the chained cause.
_SDK_SENTINELS: Final = (SENTINEL, MESSAGE_SENTINEL, BODY_SENTINEL, CAUSE_SENTINEL)
_MESSAGES_URL: Final = "https://api.anthropic.com/v1/messages"


def _sdk_request() -> httpx2.Request:
    """The request an SDK error carries: its content is the whole paste."""
    return httpx2.Request(
        "POST", _MESSAGES_URL, json={"messages": [{"role": "user", "content": SENTINEL}]}
    )


def _status_error[E: APIStatusError](
    cls: type[E], status: int, *, retry_after: str | None = None
) -> E:
    """A FRESH `cls` built with the SDK's own constructor over a real response with `status`.

    The sentinels sit in the message, the body, the response content, and the request content:
    where a real one carries upstream text and the paste.
    """
    body = {"type": "error", "error": {"type": "api_error", "message": BODY_SENTINEL}}
    headers = {} if retry_after is None else {"retry-after": retry_after}
    response = httpx2.Response(status, headers=headers, json=body, request=_sdk_request())
    return cls(MESSAGE_SENTINEL, response=response, body=body)


def _timeout_error() -> APITimeoutError:
    """OUR client's timeout, chained to the transport's exception as the SDK chains it."""
    exc = APITimeoutError(request=_sdk_request())
    exc.__cause__ = httpx2.ReadTimeout(CAUSE_SENTINEL)
    return exc


def _connection_error() -> APIConnectionError:
    """A connection failure that is not a timeout, chained as the SDK chains it."""
    exc = APIConnectionError(message=MESSAGE_SENTINEL, request=_sdk_request())
    exc.__cause__ = httpx2.ConnectError(CAUSE_SENTINEL)
    return exc


@dataclass(frozen=True)
class _UpstreamCase:
    build: Callable[[], Exception]
    status: int
    code: str
    level: int
    field: str  # the log line's last field: upstream_status=N or exc_type=Name
    retry_after: str | None = None  # the header the response must carry, or None for absent


_UPSTREAM: Final[dict[str, _UpstreamCase]] = {
    # RateLimitError's own handler, with Retry-After both ways.
    "rate-limit-retry-after": _UpstreamCase(
        lambda: _status_error(RateLimitError, 429, retry_after="17"),
        503,
        "upstream_busy",
        logging.WARNING,
        "upstream_status=429",
        "17",
    ),
    "rate-limit": _UpstreamCase(
        lambda: _status_error(RateLimitError, 429),
        503,
        "upstream_busy",
        logging.WARNING,
        "upstream_status=429",
    ),
    # The status handler's rows use the class the SDK's factory builds for each status, except
    # the base-class 429, which it never builds (L99: the handler is total).
    "status-429": _UpstreamCase(
        lambda: _status_error(APIStatusError, 429),
        503,
        "upstream_busy",
        logging.WARNING,
        "upstream_status=429",
    ),
    "overloaded-529": _UpstreamCase(
        lambda: _status_error(OverloadedError, 529),
        503,
        "upstream_busy",
        logging.WARNING,
        "upstream_status=529",
    ),
    # L99: Retry-After stays on RateLimitError's row; the status handler forwards no headers.
    "overloaded-529-retry-after": _UpstreamCase(
        lambda: _status_error(OverloadedError, 529, retry_after="17"),
        503,
        "upstream_busy",
        logging.WARNING,
        "upstream_status=529",
        None,
    ),
    "status-399": _UpstreamCase(
        lambda: _status_error(APIStatusError, 399),
        502,
        "upstream_error",
        logging.WARNING,
        "upstream_status=399",
    ),
    # L255: 408 and 409 are an intermediary's, retried by the SDK as transient
    "request-timeout-408": _UpstreamCase(
        lambda: _status_error(APIStatusError, 408),
        502,
        "upstream_error",
        logging.WARNING,
        "upstream_status=408",
    ),
    "conflict-409": _UpstreamCase(
        lambda: _status_error(ConflictError, 409),
        502,
        "upstream_error",
        logging.WARNING,
        "upstream_status=409",
    ),
    "bad-request-400": _UpstreamCase(
        lambda: _status_error(BadRequestError, 400),
        500,
        "internal_error",
        logging.ERROR,
        "upstream_status=400",
    ),
    "authentication-401": _UpstreamCase(
        lambda: _status_error(AuthenticationError, 401),
        500,
        "internal_error",
        logging.ERROR,
        "upstream_status=401",
    ),
    "status-499": _UpstreamCase(
        lambda: _status_error(APIStatusError, 499),
        500,
        "internal_error",
        logging.ERROR,
        "upstream_status=499",
    ),
    "internal-500": _UpstreamCase(
        lambda: _status_error(InternalServerError, 500),
        502,
        "upstream_error",
        logging.WARNING,
        "upstream_status=500",
    ),
    "internal-503": _UpstreamCase(
        lambda: _status_error(InternalServerError, 503),
        502,
        "upstream_error",
        logging.WARNING,
        "upstream_status=503",
    ),
    # L99: an upstream 504 is upstream's error, never our client's timeout.
    "internal-504": _UpstreamCase(
        lambda: _status_error(InternalServerError, 504),
        502,
        "upstream_error",
        logging.WARNING,
        "upstream_status=504",
    ),
    "internal-600": _UpstreamCase(
        lambda: _status_error(InternalServerError, 600),
        502,
        "upstream_error",
        logging.WARNING,
        "upstream_status=600",
    ),
    # L71: APITimeoutError subclasses APIConnectionError, so the pair pins the 504 handler.
    "timeout": _UpstreamCase(
        _timeout_error,
        504,
        "upstream_timeout",
        logging.WARNING,
        "exc_type=APITimeoutError",
    ),
    "connection": _UpstreamCase(
        _connection_error,
        502,
        "upstream_error",
        logging.WARNING,
        "exc_type=APIConnectionError",
    ),
}


@pytest.mark.parametrize("case", list(_UPSTREAM))
def test_upstream_failure_is_attributed(
    case: str, client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    expected = _UPSTREAM[case]
    fake = install_fake([expected.build()])
    response = client.post("/summarize", json={"raw_text": _content(settings.min_input_chars + 10)})
    assert response.status_code == expected.status
    assert [s for s in _SDK_SENTINELS if s in response.text] == []  # L53: none of the four
    body = response.json()
    rid = body.get("request_id")  # .get: an absent key must fail the shape assert below
    assert body == {"error": expected.code, "request_id": rid}  # §9.4: one shape
    assert RID_RE.fullmatch(rid)  # L73
    assert response.headers.get("retry-after") == expected.retry_after  # L99: forwarded or absent
    assert len(fake.messages.calls) == 1  # recorded, then raised; transport retries are the SDK's
    assert [s for s in _SDK_SENTINELS if s in caplog.text] == []  # L53: rendered records
    message = f"upstream_failure code={expected.code} request_id={rid} {expected.field}"
    ours = [r for r in caplog.records if r.name == "backend.api" and r.getMessage() == message]
    # The whole line: on its own it tells the status handler's 500 from the catch-all's 500,
    # whose body is the same.
    assert len(ours) == 1
    assert ours[0].levelno == expected.level


# --- unclaimed base classes fall to the catch-all (§9.4; L69) -----------------------------


@dataclass(frozen=True)
class _UnclaimedCase:
    build: Callable[[], Exception]
    exc_type: str  # what the 500 line's exc_type field must say


# Each row is the class just above a handler's registration. Nothing raises it today, so a
# registration widened to it would change no other test; §9.4's last row decides it: 500,
# logged by structure.
_UNCLAIMED: Final[dict[str, _UnclaimedCase]] = {
    "orchestrator-error": _UnclaimedCase(
        lambda: OrchestratorError(MESSAGE_SENTINEL, usage=TokenUsage(), validation_attempts=1),
        "OrchestratorError",
    ),
    "anthropic-error": _UnclaimedCase(lambda: AnthropicError(MESSAGE_SENTINEL), "AnthropicError"),
}


@pytest.mark.parametrize("case", list(_UNCLAIMED))
def test_unclaimed_base_class_is_500_by_structure(
    case: str, client: TestClient, install_fake: Installer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    expected = _UNCLAIMED[case]
    fake = install_fake([expected.build()])
    response = client.post("/summarize", json={"raw_text": "x" * (settings.min_input_chars + 10)})
    assert response.status_code == _INTERNAL_ERROR.status
    assert MESSAGE_SENTINEL not in response.text  # L53, L69: never the message
    body = response.json()
    rid = body.get("request_id")  # .get: an absent key must fail the shape assert below
    assert body == {"error": _INTERNAL_ERROR.code, "request_id": rid}  # §9.4: one shape
    assert RID_RE.fullmatch(rid)  # L73
    assert len(fake.messages.calls) == 1  # recorded, then raised
    assert MESSAGE_SENTINEL not in caplog.text  # L69: no str(exc), no exc_info
    ours = [
        r
        for r in caplog.records
        if r.name == "backend.api" and r.getMessage().startswith("unhandled_exception ")
    ]
    assert len(ours) == 1  # L69: the catch-all's one line
    assert ours[0].levelno == logging.ERROR
    assert re.fullmatch(
        rf"unhandled_exception code=internal_error request_id={rid} "
        rf"exc_type={expected.exc_type} frames=\S+",
        ours[0].getMessage(),
    )


# --- the reach list (§9.4; L73, L350) -------------------------------------------------------


def test_reach_is_exactly_the_declared_outcomes() -> None:
    """Every reachable §9.4 row is the declared outcome of an error test, and no more (L73).

    Declared, not observed: the outcomes come from the case tables and the constants the
    single-outcome tests read. Equality, not a superset: an outcome outside the lists is a
    later phase's code, built early. Phase 3's admission reaches NOT_UNTIL_PHASE_3 (L350).
    """
    declared = {_INPUT_INVALID, _INTERNAL_ERROR, _RATE_LIMITED, _BUDGET_EXHAUSTED}
    declared |= {_Outcome(c.status, c.code) for c in _MODEL_OUTPUT.values()}
    declared |= {_Outcome(c.status, c.code) for c in _UPSTREAM.values()}
    assert PHASE_1_REACH.isdisjoint(NOT_UNTIL_PHASE_3)
    assert declared == PHASE_1_REACH | NOT_UNTIL_PHASE_3


# --- logging configuration (§9.8, L79) ---------------------------------------------------


def test_logging_config_renders_fields_in_the_message() -> None:
    """The root logger is configured once in api.py, fields in the message (§9.8, L79).

    basicConfig is a no-op in-process under pytest (the root logger already carries pytest's
    handlers when backend is imported), so a subprocess is the only place the configuration
    is observable. The anthropic SDK configures the root logger first when ANTHROPIC_LOG is
    set, so this test fails in that shell by design.
    """
    script = "\n".join(
        [
            "import logging",
            "import backend.api",
            'logging.getLogger("backend.api").warning("code=%s request_id=%s", "c", "r")',
        ]
    )
    completed = run_fresh(script)
    assert completed.returncode == 0, completed.stderr
    last = (completed.stderr.splitlines() or [""])[-1]  # empty stderr fails at the regex
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} WARNING backend\.api code=c request_id=r",
        last,
    )
