"""Pins the /summarize input boundary and its error paths (spec §9.1, §9.4, §9.8;
L53, L69, L70, L73, L76, L79, L87).

Every request goes through the default TestClient (raise_server_exceptions=True). The
catch-all turns any Exception raised inside the app into a 500, so a 500 alone proves
nothing: every 500 test asserts its own backend.api log line. An autouse fixture overrides
get_client with an EMPTY-script FakeLLMClient; a test that reaches the model without
installing its own script fails loudly on the fake's unscripted-call guard instead of
building a real client. The guard fails through pytest.fail, a BaseException that
`except Exception` can't swallow, so the catch-all can't turn a forgotten script into a
500 a test could pass on.

Logging tests call caplog.set_level(logging.DEBUG): under pytest the root logger sits at
WARNING. Sentinel scans read caplog.text, every captured record as rendered, exc_info
included (L53); positive checks filter "backend.api" records through getMessage() (L79).
Sentinels go in values, never keys.
"""

import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Final

import httpx2
import pytest
from anthropic.types import Message
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.types import Message as ASGIMessage

from backend.api import CatchAllMiddleware, RequestIdMiddleware, SummarizeResponse, app
from backend.config import Settings, settings
from backend.orchestrator import PROMPT_VERSION, get_client
from tests.fakes import FakeLLMClient, tool_use_message

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent

# Planted inside raw_text as a VALUE (L53): the one string that must reach neither a body
# nor a log line. Shorter than the content lengths the tests build around it.
SENTINEL: Final = "sentinel-7f3a"
VALID_INPUT: Final[dict[str, object]] = {
    "claims": [{"text": "fact-1", "section": "S", "source_quote": "quote-1"}]
}
RID_RE: Final = re.compile(r"[0-9a-f]{32}")  # uuid4().hex (L73)

Installer = Callable[[Sequence[Message | Exception]], FakeLLMClient]


@pytest.fixture(autouse=True)
def install_fake() -> Iterator[Installer]:
    """Overrides get_client for every test; restores the prior overrides on the way out.

    Starts with an EMPTY script: a test that reaches the model without installing its own
    fails on the fake's unscripted-call guard, never by building a real client.
    """
    prior = dict(app.dependency_overrides)

    def install(script: Sequence[Message | Exception]) -> FakeLLMClient:
        fake = FakeLLMClient(script)
        app.dependency_overrides[get_client] = lambda: fake
        return fake

    install([])
    try:
        yield install
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prior)


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


# --- the happy path and the wire shape (§9.1; L76, L87) ------------------------------


def test_happy_path_returns_draft_and_metadata(client: TestClient, install_fake: Installer) -> None:
    fake = install_fake([tool_use_message(VALID_INPUT, input_tokens=123, output_tokens=456)])
    raw = "  " + "x" * (settings.min_input_chars + 10) + "  "  # content clears min; padded
    response = client.post("/summarize", json={"raw_text": raw})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"draft", "metadata"}  # L76: exactly the phase-1 edge shape
    assert body["draft"] == VALID_INPUT
    assert body["metadata"]["model"] == settings.model
    assert body["metadata"]["prompt_version"] == PROMPT_VERSION
    assert body["metadata"]["usage"] == {"input_tokens": 123, "output_tokens": 456}
    assert body["metadata"]["validation_attempts"] == 1
    assert len(fake.messages.calls) == 1
    assert fake.messages.calls[0].messages[0]["content"] == raw  # L87: never mutated


def test_response_model_is_the_edge_shape() -> None:
    assert _route().response_model is SummarizeResponse  # L76: never SummarizationResult
    assert SummarizeResponse.__module__ == "backend.api"  # §13: an HTTP edge shape


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
    assert response.status_code == 422
    assert SENTINEL not in response.text  # L53, L70: the paste never comes back
    body = response.json()
    rid = body.get("request_id")  # .get: an absent key must fail the shape assert below
    assert body == {"error": "input_invalid", "request_id": rid}  # §9.4: one shape
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
    patched = Settings(min_input_chars=40)
    assert patched.min_input_chars != settings.min_input_chars
    monkeypatch.setattr("backend.api.settings", patched)
    install_fake([_decoy()])
    response = client.post("/summarize", json={"raw_text": "x" * length})
    assert response.status_code == status


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
    assert response.status_code == 500
    assert MESSAGE_SENTINEL not in response.text  # L53, L69: never the message
    assert CAUSE_SENTINEL not in response.text  # nor the chained cause
    body = response.json()
    rid = body.get("request_id")  # .get: an absent key must fail the shape assert below
    assert body == {"error": "internal_error", "request_id": rid}  # §9.4: one shape
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
    # The inherited environment, plus the repo root on PYTHONPATH: `-c` puts the cwd on
    # sys.path only when PYTHONSAFEPATH is unset.
    existing = os.environ.get("PYTHONPATH")
    env = {
        **os.environ,
        "PYTHONPATH": str(_REPO_ROOT) + (os.pathsep + existing if existing else ""),
    }
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    last = (completed.stderr.splitlines() or [""])[-1]  # empty stderr fails at the regex
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} WARNING backend\.api code=c request_id=r",
        last,
    )
