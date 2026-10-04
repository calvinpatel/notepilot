r"""Pins the orchestrator: call shape, derived lineage, and the summarize loop (§5.1-§5.4, §11).

Settings-at-import rule: CALL_CONFIG and PROMPT_VERSION are computed once, at import,
from the frozen settings. Patching backend.config.settings reaches nothing in
orchestrator.py. Patching backend.orchestrator.settings reaches only call-time reads:
get_client's first call (then cached for the process) and summarize — never
these two constants. Prefer scripting the fake client over patching settings.

No test pins PROMPT_VERSION's value or the prompt's text: a prompt edit is allowed and
versions itself (invariant 15); spec fidelity is checked at review.

The tool-schema snapshot is never written by a test. Regenerate it, after a reviewed
change to ClaimDraft or SOAPNoteDraft, with exactly:

    uv run python -c 'import json; from pathlib import Path; \
        from backend.orchestrator import SUMMARY_TOOL; \
        p = Path("tests/snapshots/tool_schema.json"); \
        p.parent.mkdir(parents=True, exist_ok=True); \
        p.write_text(json.dumps(SUMMARY_TOOL["input_schema"], sort_keys=True, indent=2) + "\n")'
"""

import functools
import json
import re
import string
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Final, get_args

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, MessageParam, StopReason, ToolResultBlockParam
from pydantic import SecretStr, ValidationError

from backend.config import Settings, settings
from backend.orchestrator import (
    CALL_CONFIG,
    CORRECTION_TEMPLATE,
    PROMPT_VERSION,
    SUMMARY_TOOL,
    SYSTEM_PROMPT,
    TRUNCATION_STOPS,
    CallConfig,
    LLMClient,
    ModelOutputError,
    OrchestratorError,
    OutputTruncatedError,
    _derive_prompt_version,
    get_client,
    summarize,
)
from backend.schemas import RunMetadata, SOAPNoteDraft, TokenUsage
from tests.fakes import FakeLLMClient, RecordedCall, text_message, tool_use_message

_SNAPSHOT = Path(__file__).parent / "snapshots" / "tool_schema.json"


# --- the call config (§5.2; L75, L82, L94) -----------------------------------------


def test_tool_choice_forces_summary_tool() -> None:
    tool_choice = CALL_CONFIG["tool_choice"]
    assert tool_choice["type"] == "tool"
    assert tool_choice["name"] == SUMMARY_TOOL["name"]
    assert tool_choice["disable_parallel_tool_use"] is True  # L75


def test_system_prompt_names_the_tool() -> None:
    assert SUMMARY_TOOL["name"] in SYSTEM_PROMPT


def test_call_config_is_exactly_the_spec_dict() -> None:
    assert CALL_CONFIG == {
        "tool_choice": {
            "type": "tool",
            "name": SUMMARY_TOOL["name"],
            "disable_parallel_tool_use": True,
        },
        "max_tokens": settings.max_output_tokens,  # L94
        "extra_body": {"temperature": 0},  # L82, invariant 3
    }


# --- the tool schema is the spine (§5.1, §11) --------------------------------------


def test_input_schema_is_derived_from_the_spine() -> None:
    assert SUMMARY_TOOL["input_schema"] == SOAPNoteDraft.model_json_schema()


def test_tool_schema_snapshot() -> None:
    # Any change to ClaimDraft/SOAPNoteDraft is a reviewed diff here AND a new PROMPT_VERSION.
    assert _SNAPSHOT.is_file(), f"missing snapshot {_SNAPSHOT}; see module docstring"
    assert json.loads(_SNAPSHOT.read_text()) == SUMMARY_TOOL["input_schema"]


# --- the correction template (§5.4) --------------------------------------------------


def test_correction_template_has_exactly_one_field_errors() -> None:
    # `is not None`, not truthiness: a positional `{}` parses as '' and must count.
    parsed = string.Formatter().parse(CORRECTION_TEMPLATE)
    fields = [name for _, name, _, _ in parsed if name is not None]
    assert fields == ["errors"]


# --- PROMPT_VERSION: derived, never declared (§5.4, L15, invariant 15) ----------------


def _baseline() -> str:
    return _derive_prompt_version(
        system=SYSTEM_PROMPT,
        tool=SUMMARY_TOOL,
        correction=CORRECTION_TEMPLATE,
        call=CALL_CONFIG,
    )


def test_prompt_version_is_12_lowercase_hex() -> None:
    assert re.fullmatch(r"[0-9a-f]{12}", PROMPT_VERSION)


def test_prompt_version_equals_the_derivation() -> None:
    assert PROMPT_VERSION == _baseline()


def _tool_with_other_description() -> str:
    tool = SUMMARY_TOOL.copy()
    tool["description"] = "other"
    return _derive_prompt_version(
        system=SYSTEM_PROMPT, tool=tool, correction=CORRECTION_TEMPLATE, call=CALL_CONFIG
    )


def _call_with_other_max_tokens() -> str:
    call = CallConfig(
        tool_choice=CALL_CONFIG["tool_choice"],
        max_tokens=CALL_CONFIG["max_tokens"] + 1,
        extra_body=CALL_CONFIG["extra_body"],
    )
    return _derive_prompt_version(
        system=SYSTEM_PROMPT, tool=SUMMARY_TOOL, correction=CORRECTION_TEMPLATE, call=call
    )


# Typed builders keyed by input name: one perturbation each, no **{name: value} call.
_PERTURBED: dict[str, Callable[[], str]] = {
    "system": lambda: _derive_prompt_version(
        system=SYSTEM_PROMPT + " ",
        tool=SUMMARY_TOOL,
        correction=CORRECTION_TEMPLATE,
        call=CALL_CONFIG,
    ),
    "tool": _tool_with_other_description,
    "correction": lambda: _derive_prompt_version(
        system=SYSTEM_PROMPT,
        tool=SUMMARY_TOOL,
        correction=CORRECTION_TEMPLATE + " ",
        call=CALL_CONFIG,
    ),
    "call": _call_with_other_max_tokens,
}


@pytest.mark.parametrize("name", list(_PERTURBED))
def test_prompt_version_changes_when_each_input_changes(name: str) -> None:
    assert _PERTURBED[name]() != _baseline()


def test_prompt_version_ignores_key_order() -> None:
    reordered = CallConfig(
        extra_body=CALL_CONFIG["extra_body"],
        max_tokens=CALL_CONFIG["max_tokens"],
        tool_choice=CALL_CONFIG["tool_choice"],
    )
    assert (
        _derive_prompt_version(
            system=SYSTEM_PROMPT,
            tool=SUMMARY_TOOL,
            correction=CORRECTION_TEMPLATE,
            call=reordered,
        )
        == _baseline()
    )


# --- the seam (§5.2, §5.5; L74, L77, L78) ---------------------------------------------


@pytest.fixture
def fresh_client_cache() -> Iterator[None]:
    # Only the two get_client tests use this: the cache is process-wide (L78), so a client
    # built under one test's settings must never be the one another test observes.
    get_client.cache_clear()
    yield
    get_client.cache_clear()


@pytest.mark.usefixtures("fresh_client_cache")
def test_get_client_is_cached() -> None:
    client = get_client()
    assert client is get_client()  # L78
    assert isinstance(client, AsyncAnthropic)  # also narrows: attribute access needs no cast


@pytest.mark.usefixtures("fresh_client_cache")
def test_get_client_wires_settings_not_ambient_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Non-defaults on purpose: at defaults the conftest key equals the ambient key and
    # sdk_transport_retries equals the SDK's own default of 2, so dropping api_key= or
    # max_retries= would change nothing observable. setenv last: Settings() reads the env.
    patched = Settings(
        anthropic_api_key=SecretStr("settings-key"), llm_timeout_s=17.0, sdk_transport_retries=5
    )
    monkeypatch.setattr("backend.orchestrator.settings", patched)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-key")
    client = get_client()
    assert isinstance(client, AsyncAnthropic)
    assert client.api_key == "settings-key"  # L77
    assert client.timeout == 17.0  # L54
    assert client.max_retries == 5  # L5


async def _create(client: LLMClient, msgs: list[MessageParam]) -> Message:
    # The call summarize makes, used by the tests that exercise the fake directly; mypy
    # checks CallConfig's value types against the Protocol here as in summarize (L83).
    return await client.messages.create(
        model=settings.model,
        system=SYSTEM_PROMPT,
        tools=[SUMMARY_TOOL],
        messages=msgs,
        **CALL_CONFIG,
    )


@pytest.mark.anyio
async def test_fake_binds_to_the_seam_and_records_a_copy() -> None:
    scripted = tool_use_message({"claims": []})
    fake = FakeLLMClient([scripted])
    client: LLMClient = fake
    msgs: list[MessageParam] = [{"role": "user", "content": "synthetic encounter text"}]
    result = await _create(client, msgs)
    msgs.append({"role": "assistant", "content": "appended after the call"})
    msgs[0]["content"] = "mutated after the call"
    (call,) = fake.messages.calls
    assert len(call.messages) == 1  # a copy of the list, not the caller's list
    assert call.messages[0]["content"] == "synthetic encounter text"  # a deep copy, not shallow
    assert call.extra_body == {"temperature": 0}  # L82, invariant 3
    assert call.tool_choice == CALL_CONFIG["tool_choice"]
    assert call.max_tokens == CALL_CONFIG["max_tokens"]
    assert result is scripted


@pytest.mark.anyio
async def test_fake_exhausted_script_raises_and_still_records() -> None:
    fake = FakeLLMClient([tool_use_message({"claims": []})])
    client: LLMClient = fake
    msgs: list[MessageParam] = [{"role": "user", "content": "synthetic encounter text"}]
    await _create(client, msgs)
    with pytest.raises(pytest.fail.Exception, match="unscripted"):
        await _create(client, msgs)
    assert len(fake.messages.calls) == 2


class _Scripted(Exception):
    """A test-owned exception type: the fake must raise the scripted object itself."""


@pytest.mark.anyio
async def test_fake_raises_a_scripted_exception_and_records_the_call() -> None:
    scripted = _Scripted("scripted failure")
    fake = FakeLLMClient([scripted])
    client: LLMClient = fake
    msgs: list[MessageParam] = [{"role": "user", "content": "synthetic encounter text"}]
    with pytest.raises(_Scripted) as info:
        await _create(client, msgs)
    assert info.value is scripted  # the object itself, not a copy or a wrapper
    assert len(fake.messages.calls) == 1  # recorded before the raise


# --- the summarize loop (§5.4; L12, L13, L14, L49, L53, L88, L97) --------------------

RAW: Final = "synthetic encounter text"
# Planted as a field VALUE: `loc` carries keys even with include_input=False, so only a value
# can tell the correction the model sees (L53) apart from a log-safe rendering.
SENTINEL: Final = "sentinel-7f3a"
VALID_INPUT: Final[dict[str, object]] = {
    "claims": [{"text": "fact-1", "section": "S", "source_quote": "quote-1"}]
}
INVALID_INPUT: Final[dict[str, object]] = {
    "claims": [{"text": "fact-1", "section": SENTINEL, "source_quote": "quote-1"}]
}
_valid = functools.partial(tool_use_message, VALID_INPUT)
_invalid = functools.partial(tool_use_message, INVALID_INPUT)

# L97: every StopReason value has one decided path. These need no branch: pause_turn needs
# server tools and stop_sequence needs stop sequences, and this call sends neither; end_turn
# and tool_use fall through to the block lookup.
FALL_THROUGH_STOPS: Final[frozenset[StopReason]] = frozenset(
    {"tool_use", "end_turn", "stop_sequence", "pause_turn"}
)

# What the gated response carries: a valid block, an invalid one, or none. The invalid script
# adds a decoy second response, which a mutant that retries instead of failing fast returns
# as a success.
_GATED_SCRIPTS: Final[dict[str, Callable[[StopReason], list[Message]]]] = {
    "valid": lambda stop: [_valid(stop_reason=stop, input_tokens=11, output_tokens=7)],
    "invalid": lambda stop: [
        _invalid(stop_reason=stop, input_tokens=11, output_tokens=7),
        _valid(tool_use_id="toolu_fake_2"),
    ],
    "none": lambda stop: [
        text_message("no tool call", stop_reason=stop, input_tokens=11, output_tokens=7)
    ],
}


def _assert_call_config(call: RecordedCall) -> None:
    assert call.extra_body == {"temperature": 0}  # L82, invariant 3
    assert call.tool_choice == CALL_CONFIG["tool_choice"]  # L75


def _only_tool_result(msg: MessageParam) -> ToolResultBlockParam:
    """The one tool_result block of a correction message (§5.4's API contract)."""
    assert msg["role"] == "user"
    content = msg["content"]
    assert not isinstance(content, str)
    blocks = list(content)
    assert len(blocks) == 1
    (block,) = blocks
    assert isinstance(block, dict)
    assert block["type"] == "tool_result"
    return block


@pytest.mark.anyio
async def test_happy_path_returns_draft_and_metadata() -> None:
    fake = FakeLLMClient([_valid(input_tokens=11, output_tokens=7)])
    result = await summarize(RAW, client=fake)
    assert result.draft == SOAPNoteDraft.model_validate(VALID_INPUT)
    assert result.metadata.model == settings.model
    assert result.metadata.prompt_version == PROMPT_VERSION
    assert result.metadata.validation_attempts == 1
    assert result.metadata.usage == TokenUsage(input_tokens=11, output_tokens=7)
    (call,) = fake.messages.calls  # one call, and exactly §5.2's request
    assert call.model == settings.model
    assert call.system == SYSTEM_PROMPT
    assert call.tools == [SUMMARY_TOOL]
    assert call.max_tokens == CALL_CONFIG["max_tokens"]
    assert call.messages == [{"role": "user", "content": RAW}]
    _assert_call_config(call)


@pytest.mark.anyio
async def test_validation_retry_answers_the_tool_use_id() -> None:
    first = _invalid(tool_use_id="toolu_fake_1")
    fake = FakeLLMClient([first, _valid(tool_use_id="toolu_fake_2")])
    result = await summarize(RAW, client=fake)
    assert result.metadata.validation_attempts == 2
    call_1, call_2 = fake.messages.calls
    assert call_1.messages == [{"role": "user", "content": RAW}]
    assert len(call_2.messages) == 3
    assert call_2.messages[0] == {"role": "user", "content": RAW}
    assert call_2.messages[1] == {"role": "assistant", "content": first.content}
    block = _only_tool_result(call_2.messages[2])
    assert block["tool_use_id"] == "toolu_fake_1"  # answers attempt 1's block
    assert block.get("is_error") is True
    correction = block.get("content")
    assert isinstance(correction, str)
    assert correction.startswith("Validation failed:")
    assert SENTINEL in correction  # L53: the model sees its own output; input stays in
    _assert_call_config(call_1)
    _assert_call_config(call_2)


@pytest.mark.anyio
async def test_usage_is_summed_on_success() -> None:
    fake = FakeLLMClient(
        [
            _invalid(input_tokens=11, output_tokens=7),
            _valid(input_tokens=13, output_tokens=5, tool_use_id="toolu_fake_2"),
        ]
    )
    result = await summarize(RAW, client=fake)
    assert len(fake.messages.calls) == 2
    assert result.metadata.usage == TokenUsage(input_tokens=24, output_tokens=12)  # L13


@pytest.mark.anyio
async def test_usage_is_summed_on_truncation_after_a_retry() -> None:
    fake = FakeLLMClient(
        [
            _invalid(input_tokens=11, output_tokens=7),
            _valid(
                stop_reason="max_tokens",
                input_tokens=13,
                output_tokens=5,
                tool_use_id="toolu_fake_2",
            ),
        ]
    )
    with pytest.raises(OutputTruncatedError) as exc:
        await summarize(RAW, client=fake)
    assert len(fake.messages.calls) == 2
    # L49: the failed attempt is paid for too
    assert exc.value.usage == TokenUsage(input_tokens=24, output_tokens=12)


@pytest.mark.anyio
@pytest.mark.parametrize("block", list(_GATED_SCRIPTS))
@pytest.mark.parametrize("stop_reason", sorted(TRUNCATION_STOPS))
async def test_truncation_fails_fast(stop_reason: StopReason, block: str) -> None:
    fake = FakeLLMClient(_GATED_SCRIPTS[block](stop_reason))
    with pytest.raises(OutputTruncatedError) as exc:
        await summarize(RAW, client=fake)
    assert type(exc.value) is OutputTruncatedError
    assert str(exc.value) == "output truncated"
    assert exc.value.code == "output_truncated"
    assert len(fake.messages.calls) == 1  # fail fast: nothing in `messages` would change
    assert exc.value.usage == TokenUsage(input_tokens=11, output_tokens=7)


@pytest.mark.anyio
@pytest.mark.parametrize("block", list(_GATED_SCRIPTS))
async def test_refusal_fails_fast(block: str) -> None:
    fake = FakeLLMClient(_GATED_SCRIPTS[block]("refusal"))
    with pytest.raises(ModelOutputError) as exc:
        await summarize(RAW, client=fake)
    assert type(exc.value) is ModelOutputError
    # L97: its own message, so a refusal never reaches 502 by way of the missing-block
    # branch (L73), whatever the response carries
    assert str(exc.value) == "refusal under forced tool_choice"
    assert exc.value.code == "model_output_invalid"
    assert len(fake.messages.calls) == 1
    assert exc.value.usage == TokenUsage(input_tokens=11, output_tokens=7)


@pytest.mark.anyio
async def test_missing_tool_block_fails_fast() -> None:
    fake = FakeLLMClient([text_message("no tool call", input_tokens=11, output_tokens=7)])
    with pytest.raises(ModelOutputError) as exc:
        await summarize(RAW, client=fake)
    # end_turn is not a cut: never OutputTruncatedError
    assert type(exc.value) is ModelOutputError
    assert str(exc.value) == "no tool_use block under forced tool_choice"
    assert len(fake.messages.calls) == 1
    assert exc.value.usage == TokenUsage(input_tokens=11, output_tokens=7)


@pytest.mark.anyio
async def test_retries_exhausted() -> None:
    n = settings.max_validation_retries + 1  # attempts, not retries (§5.4)
    script = [
        _invalid(input_tokens=11, output_tokens=7, tool_use_id=f"toolu_fake_{i}")
        for i in range(1, n + 1)
    ]
    # a decoy: a loop that runs one attempt too many returns it as a success
    script.append(_valid(tool_use_id=f"toolu_fake_{n + 1}"))
    fake = FakeLLMClient(script)
    with pytest.raises(ModelOutputError) as exc:
        await summarize(RAW, client=fake)
    assert len(fake.messages.calls) == n
    assert type(exc.value) is ModelOutputError
    assert SENTINEL not in str(exc.value)  # static message: model text stays in the cause (L53)
    assert str(exc.value) == f"invalid after {n} attempts"
    assert isinstance(exc.value.__cause__, ValidationError)  # the `from` chain (§5.4)
    # L49: every attempt was paid for, and the error carries the sum
    assert exc.value.usage == TokenUsage(input_tokens=11 * n, output_tokens=7 * n)


@pytest.mark.anyio
async def test_retry_count_and_model_wire_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Non-defaults on purpose (the precedent is test_get_client_wires_settings_not_ambient_env):
    # at the defaults, a hardcoded attempt count or the default id as a literal would change
    # nothing observable.
    patched = Settings(max_validation_retries=0, model="model-id-patched")
    monkeypatch.setattr("backend.orchestrator.settings", patched)
    fake = FakeLLMClient([_invalid(), _valid(tool_use_id="toolu_fake_2")])  # the second: a decoy
    with pytest.raises(ModelOutputError) as exc:
        await summarize(RAW, client=fake)
    (call,) = fake.messages.calls
    assert call.model == "model-id-patched"
    assert type(exc.value) is ModelOutputError
    assert str(exc.value) == "invalid after 1 attempts"


def _run_metadata_that_cannot_validate(**fields: object) -> RunMetadata:
    # A real spine ValidationError, never hand-built: RunMetadata itself rejects
    # validation_attempts=0 (L89). It stands in for a shape bug in OUR metadata.
    return RunMetadata.model_validate({**fields, "validation_attempts": 0})


@pytest.mark.anyio
async def test_metadata_error_is_not_fed_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.orchestrator.RunMetadata", _run_metadata_that_cannot_validate)
    # Decoys: a try widened over the return would feed OUR error back as the model's, retry
    # through every decoy, exhaust, and raise ModelOutputError instead.
    decoys = [
        _valid(tool_use_id=f"toolu_fake_{i}") for i in range(2, settings.max_validation_retries + 2)
    ]
    fake = FakeLLMClient([_valid(), *decoys])
    with pytest.raises(ValidationError) as exc:
        await summarize(RAW, client=fake)
    assert type(exc.value) is ValidationError  # unwrapped (L12)
    (err,) = exc.value.errors()
    assert err["loc"] == ("validation_attempts",)
    assert len(fake.messages.calls) == 1


def test_every_stop_reason_has_a_decided_path() -> None:
    # L97: an SDK that adds a stop reason fails here instead of falling through.
    refusal: frozenset[StopReason] = frozenset({"refusal"})
    assert set(get_args(StopReason)) == TRUNCATION_STOPS | refusal | FALL_THROUGH_STOPS
    assert not TRUNCATION_STOPS & refusal
    assert not TRUNCATION_STOPS & FALL_THROUGH_STOPS
    assert not refusal & FALL_THROUGH_STOPS


def test_error_codes_and_hierarchy() -> None:
    # §9.4 resolves handlers by MRO and reports by code: the contract api.py reads.
    assert issubclass(OutputTruncatedError, ModelOutputError)
    assert issubclass(ModelOutputError, OrchestratorError)
    assert OrchestratorError.code == "orchestrator_error"
    assert ModelOutputError.code == "model_output_invalid"
    assert OutputTruncatedError.code == "output_truncated"
