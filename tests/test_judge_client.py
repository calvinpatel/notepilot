"""Pins the judge's client: call shape, derived lineage, one call per pair, and get_judge (§8.2,
§9.1; L312-L314, L318, L319).

Settings-at-import rule, as in test_orchestrator.py: JUDGE_CALL_CONFIG and JUDGE_VERSION are
computed once, at import. Patching backend.judge_client.settings reaches only call-time reads:
the model, the timeout, and the concurrency, all read by entailment.

No test pins JUDGE_VERSION's value or the prompt's text: a prompt edit is allowed and versions
itself (invariant 15); spec fidelity is checked at review. The user message's form is pinned,
since the probe measured that form (L313).
"""

import functools
import inspect
import logging
import re
from collections.abc import Callable
from typing import Final

import pytest
from anthropic.types import Message, StopReason

from backend.config import Settings, settings
from backend.evals.checks import clause_text
from backend.evals.runner import run_checks
from backend.judge_client import (
    ENTAILMENT_TOOL,
    JUDGE_CALL_CONFIG,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_VERSION,
    AnthropicJudge,
    JudgeCallConfig,
    JudgeOutputError,
    _derive_judge_version,
    _JudgeMessages,
    _user_message,
    _Verdict,
    _Verdicts,
    get_judge,
)
from backend.orchestrator import anthropic_client
from backend.schemas import ClinicalClaim, Severity, SOAPNote, TokenUsage
from tests.fakes import CHECKS_CONFIG, FakeJudgeClient, text_message, tool_use_message

# --- the call config and the tool (§8.2; L313) ------------------------------------------------


def test_judge_call_config_is_exactly_the_spec_dict() -> None:
    assert JUDGE_CALL_CONFIG == {
        "tool_choice": {
            "type": "tool",
            "name": ENTAILMENT_TOOL["name"],
            "disable_parallel_tool_use": True,
        },
        "max_tokens": 128,  # L313
        "thinking": {"type": "disabled"},  # invariant 3
        "output_config": {"effort": "low"},  # invariant 3
    }


def _keys(node: object, *path: str) -> set[str]:
    """The keys, or the items, of the schema node at path."""
    for key in path:
        assert isinstance(node, dict)
        node = node[key]
    assert isinstance(node, dict | list)
    return {str(k) for k in node}


def test_the_verdict_models_read_what_the_tool_schema_allows() -> None:
    schema = ENTAILMENT_TOOL["input_schema"]
    items = ("properties", "verdicts", "items")
    assert set(_Verdicts.model_fields) == _keys(schema, "properties") == _keys(schema, "required")
    assert (
        set(_Verdict.model_fields)
        == _keys(schema, *items, "properties")
        == _keys(schema, *items, "required")
    )


def test_the_user_message_is_the_probes_form() -> None:
    # L313: a JSON array of one pair numbered 0, non-ASCII sent as itself
    assert _user_message("Pt on 500 µg", 'Says "fine"') == (
        '[{"pair": 0, "claim": "Pt on 500 µg", "source": "Says \\"fine\\""}]'
    )


# --- JUDGE_VERSION: derived, never declared (L313, invariant 15) --------------------------------

_HASHED_MESSAGE: Final = _user_message("{claim}", "{source} µg")


def _baseline() -> str:
    return _derive_judge_version(
        system=JUDGE_SYSTEM_PROMPT,
        tool=ENTAILMENT_TOOL,
        call=JUDGE_CALL_CONFIG,
        message=_HASHED_MESSAGE,
    )


def test_judge_version_is_12_lowercase_hex() -> None:
    assert re.fullmatch(r"[0-9a-f]{12}", JUDGE_VERSION)


def test_judge_version_equals_the_derivation() -> None:
    assert JUDGE_VERSION == _baseline()


def _call_with_other_max_tokens() -> str:
    call = JudgeCallConfig(
        tool_choice=JUDGE_CALL_CONFIG["tool_choice"],
        max_tokens=JUDGE_CALL_CONFIG["max_tokens"] + 1,
        thinking=JUDGE_CALL_CONFIG["thinking"],
        output_config=JUDGE_CALL_CONFIG["output_config"],
    )
    return _derive_judge_version(
        system=JUDGE_SYSTEM_PROMPT, tool=ENTAILMENT_TOOL, call=call, message=_HASHED_MESSAGE
    )


def _tool_with_other_description() -> str:
    tool = ENTAILMENT_TOOL.copy()
    tool["description"] = "other"
    return _derive_judge_version(
        system=JUDGE_SYSTEM_PROMPT, tool=tool, call=JUDGE_CALL_CONFIG, message=_HASHED_MESSAGE
    )


# Typed builders keyed by input name: one perturbation each, no **{name: value} call.
_PERTURBED: dict[str, Callable[[], str]] = {
    "system": lambda: _derive_judge_version(
        system=JUDGE_SYSTEM_PROMPT + " ",
        tool=ENTAILMENT_TOOL,
        call=JUDGE_CALL_CONFIG,
        message=_HASHED_MESSAGE,
    ),
    "tool": _tool_with_other_description,
    "call": _call_with_other_max_tokens,
    "message": lambda: _derive_judge_version(
        system=JUDGE_SYSTEM_PROMPT,
        tool=ENTAILMENT_TOOL,
        call=JUDGE_CALL_CONFIG,
        message=_HASHED_MESSAGE + " ",
    ),
}


@pytest.mark.parametrize("name", list(_PERTURBED))
def test_judge_version_changes_when_each_input_changes(name: str) -> None:
    assert _PERTURBED[name]() != _baseline()


# --- the seam (§8.2; L74, L314) -----------------------------------------------------------------


def test_judge_seam_is_summarizes_keywords_and_a_timeout() -> None:
    # L314: the judge's timeout is per request, on its own seam; no sampling parameter (L181)
    keywords = set(inspect.signature(_JudgeMessages.create).parameters) - {"self"}
    assert keywords == {
        "model",
        "system",
        "tools",
        "messages",
        "tool_choice",
        "max_tokens",
        "thinking",
        "output_config",
        "timeout",
    }


# --- entailment: one call per pair (L312, L313) -------------------------------------------------

_reply = functools.partial(tool_use_message, name=ENTAILMENT_TOOL["name"])


def _verdict(
    entailed: bool,
    *,
    stop_reason: StopReason = "tool_use",
    input_tokens: int = 10,
    output_tokens: int = 20,
) -> Message:
    """A reply carrying one well-formed verdict for the call's one pair."""
    return _reply(
        {"verdicts": [{"pair": 0, "entailed": entailed}]},
        stop_reason=stop_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


PAIRS: Final = [
    ("Metformin 500 mg bid", "Continue metformin 500 mg bid"),
    ("Vitamin B12 1000 µg daily", "B12 1000 µg PO daily"),
]


@pytest.mark.anyio
async def test_each_pair_is_one_call_with_the_pinned_request() -> None:
    fake = FakeJudgeClient(
        {
            _user_message(*PAIRS[0]): _verdict(True, input_tokens=11, output_tokens=7),
            _user_message(*PAIRS[1]): _verdict(False, input_tokens=13, output_tokens=5),
        }
    )
    judge = AnthropicJudge(fake)
    assert await judge.entailment(PAIRS) == [True, False]
    assert judge.usage == TokenUsage(input_tokens=24, output_tokens=12)
    first, second = fake.messages.calls
    assert [c.messages for c in (first, second)] == [
        [{"role": "user", "content": _user_message(*PAIRS[0])}],
        [{"role": "user", "content": _user_message(*PAIRS[1])}],
    ]
    for call in (first, second):
        assert call.model == settings.model
        assert call.system == JUDGE_SYSTEM_PROMPT
        assert call.tools == [ENTAILMENT_TOOL]
        assert call.tool_choice == JUDGE_CALL_CONFIG["tool_choice"]
        assert call.max_tokens == JUDGE_CALL_CONFIG["max_tokens"]
        assert call.thinking == {"type": "disabled"}
        assert call.output_config == {"effort": "low"}
        assert call.timeout == settings.judge_timeout_s


@pytest.mark.anyio
async def test_no_pairs_make_no_call() -> None:
    fake = FakeJudgeClient({})
    assert await AnthropicJudge(fake).entailment([]) == []
    assert fake.messages.calls == []


@pytest.mark.anyio
async def test_settings_wire_the_model_the_timeout_and_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Non-defaults, so a hard-coded value or a missing semaphore changes what's observed.
    patched = Settings.model_validate(
        {"model": "model-id-patched", "judge_timeout_s": 7.5, "judge_concurrency": 2}
    )
    monkeypatch.setattr("backend.judge_client.settings", patched)
    pairs = [(f"claim {i}", f"source {i}") for i in range(5)]
    fake = FakeJudgeClient({_user_message(*p): _verdict(True) for p in pairs})
    assert await AnthropicJudge(fake).entailment(pairs) == [True] * 5
    assert len(fake.messages.calls) == 5
    assert {(c.model, c.timeout) for c in fake.messages.calls} == {("model-id-patched", 7.5)}
    assert fake.messages.peak_in_flight == 2  # L314: judge_concurrency caps the note's calls


# What each unusable reply raises (L313). A truncated or refused reply carries a well-formed
# verdict, so a client that skips those gates returns it instead of raising.
_UNUSABLE: Final[dict[str, tuple[Message, str]]] = {
    "max_tokens": (_verdict(True, stop_reason="max_tokens"), "verdict truncated"),
    "context-window": (
        _verdict(True, stop_reason="model_context_window_exceeded"),
        "verdict truncated",
    ),
    "refusal": (_verdict(True, stop_reason="refusal"), "refusal under forced tool_choice"),
    "no-block": (text_message("entailed"), "no tool_use block under forced tool_choice"),
    "no-verdicts": (_reply({}), "tool input invalid"),
    "bool-pair": (_reply({"verdicts": [{"pair": False, "entailed": True}]}), "tool input invalid"),
    "int-verdict": (_reply({"verdicts": [{"pair": 0, "entailed": 1}]}), "tool input invalid"),
    "extra-key": (
        _reply({"verdicts": [{"pair": 0, "entailed": True, "reason": "restated"}]}),
        "tool input invalid",
    ),
    "wrong-pair": (
        _reply({"verdicts": [{"pair": 1, "entailed": True}]}),
        "verdicts don't answer the pair sent",
    ),
    "two-verdicts": (
        _reply({"verdicts": [{"pair": 0, "entailed": True}, {"pair": 0, "entailed": False}]}),
        "verdicts don't answer the pair sent",
    ),
    "none-given": (_reply({"verdicts": []}), "verdicts don't answer the pair sent"),
}


@pytest.mark.anyio
@pytest.mark.parametrize("reply", list(_UNUSABLE))
async def test_an_unusable_reply_raises_after_its_usage_is_counted(reply: str) -> None:
    message, error = _UNUSABLE[reply]
    fake = FakeJudgeClient({_user_message(*PAIRS[0]): message})
    judge = AnthropicJudge(fake)
    with pytest.raises(JudgeOutputError) as exc:
        await judge.entailment(PAIRS[:1])
    assert type(exc.value) is JudgeOutputError
    assert str(exc.value) == error
    assert judge.usage == TokenUsage(
        input_tokens=message.usage.input_tokens, output_tokens=message.usage.output_tokens
    )  # L13: counted before the reply is read
    assert len(fake.messages.calls) == 1  # no correction turn


class _CallFailed(Exception):
    """A test-local stand-in for a call that failed (a timeout, a transport error)."""


@pytest.mark.anyio
async def test_a_failed_call_cancels_the_notes_pending_calls_and_raises_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # L312: fail closed. One call waits, one fails, and one is queued behind the cap of 2;
    # the failure frees a place, so the queued one may start before it's cancelled (measured).
    monkeypatch.setattr(
        "backend.judge_client.settings", Settings.model_validate({"judge_concurrency": 2})
    )
    waits, fails, queued = (("claim a", "a"), ("claim b", "b"), ("claim c", "c"))
    failure = _CallFailed()
    fake = FakeJudgeClient(
        {_user_message(*fails): failure, _user_message(*queued): _verdict(True)},
        hang=[_user_message(*waits)],
    )
    judge = AnthropicJudge(fake)
    with pytest.raises(_CallFailed) as exc:
        await judge.entailment([waits, fails, queued])
    assert exc.value is failure  # the call's own exception, never a group around it
    sent = {call.messages[0]["content"] for call in fake.messages.calls}
    assert _user_message(*waits) in fake.messages.cancelled
    assert set(fake.messages.cancelled) == sent - {_user_message(*fails)}  # none answered
    assert judge.usage == TokenUsage()  # nothing came back, so nothing counted


@pytest.mark.anyio
async def test_a_failed_call_errors_the_check_and_its_log_names_the_calls_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # L311, L312: the check errors, a WARNING; the log line names the failed call's type,
    # which a group around it would hide
    caplog.set_level(logging.DEBUG)
    raw = "Continue metformin 500 mg bid."
    quote = "Continue metformin 500 mg bid"
    claim = ClinicalClaim(
        id=0,
        text="Metformin 500 mg bid",
        section="P",
        source_quote=quote,
        source_span=(raw.index(quote), raw.index(quote) + len(quote)),
    )
    clause = clause_text(claim, raw)
    assert clause is not None
    fake = FakeJudgeClient({_user_message(claim.text, clause): _CallFailed()})
    report = await run_checks(
        SOAPNote(claims=(claim,)),
        raw,
        mode="production",
        config=CHECKS_CONFIG,
        judge=AnthropicJudge(fake),
    )
    (result,) = [r for r in report.results if r.check == "text_entailment_judge"]
    assert (result.passed, result.errored, result.severity) == (False, True, Severity.WARNING)
    assert "check=text_entailment_judge exc_type=_CallFailed " in caplog.text


# --- get_judge: the route's judge, on the one client (§9.1; L78, L318, L319) ------------------


@pytest.mark.usefixtures("fresh_client_cache")
def test_get_judge_builds_a_new_judge_on_the_one_client_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Non-default: judge_enabled is False unless set
    monkeypatch.setattr(
        "backend.judge_client.settings", Settings.model_validate({"judge_enabled": True})
    )
    judge = get_judge()
    assert isinstance(judge, AnthropicJudge)
    assert judge._client is anthropic_client()  # L319: the client summarize uses
    assert judge.usage == TokenUsage()
    assert judge.version == JUDGE_VERSION  # L336: what a report it judges names
    assert get_judge() is not judge  # never cached: a judge's usage is one report's (L7)


def test_get_judge_is_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.judge_client.settings", Settings.model_validate({"judge_enabled": False})
    )
    assert get_judge() is None
