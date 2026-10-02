r"""Pins the orchestrator's call shape and its derived lineage (spec §5.1-§5.4, §11).

Settings-at-import rule: CALL_CONFIG and PROMPT_VERSION are computed once, at import,
from the frozen settings. Patching backend.config.settings reaches nothing in
orchestrator.py. Patching backend.orchestrator.settings reaches only call-time reads:
get_client's first call (then cached for the process) and, from 3c, summarize — never
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

import json
import re
import string
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, MessageParam
from pydantic import SecretStr

from backend.config import Settings, settings
from backend.orchestrator import (
    CALL_CONFIG,
    CORRECTION_TEMPLATE,
    PROMPT_VERSION,
    SUMMARY_TOOL,
    SYSTEM_PROMPT,
    CallConfig,
    LLMClient,
    _derive_prompt_version,
    get_client,
)
from backend.schemas import SOAPNoteDraft
from tests.fakes import FakeLLMClient, tool_use_message

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
    # The first place mypy checks CallConfig's value types against the Protocol (L83);
    # until summarize lands in 3c, this call IS that check.
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
    with pytest.raises(AssertionError, match="unscripted"):
        await _create(client, msgs)
    assert len(fake.messages.calls) == 2
