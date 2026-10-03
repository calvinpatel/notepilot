"""Pins the /summarize input boundary and its first error path (spec §9.1, §9.4, §9.8;
L53, L70, L73, L76, L79, L87).

Every request goes through the default TestClient (raise_server_exceptions=True), so an
exception inside the app reaches the test as an exception, never as a 500 it could pass on.
An autouse fixture overrides get_client with an EMPTY-script FakeLLMClient; a test that
reaches the model without installing its own script fails loudly on the fake's
unscripted-call guard instead of building a real client.

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

from backend.api import RequestIdMiddleware, SummarizeResponse, app
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

Installer = Callable[[Sequence[Message]], FakeLLMClient]


@pytest.fixture(autouse=True)
def install_fake() -> Iterator[Installer]:
    """Overrides get_client for every test; restores the prior overrides on the way out.

    Starts with an EMPTY script: a test that reaches the model without installing its own
    fails on the fake's unscripted-call guard, never by building a real client.
    """
    prior = dict(app.dependency_overrides)

    def install(script: Sequence[Message]) -> FakeLLMClient:
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


def test_request_id_middleware_is_the_only_user_middleware() -> None:
    classes: list[object] = [m.cls for m in app.user_middleware]
    assert classes == [RequestIdMiddleware]


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
