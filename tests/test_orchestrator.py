r"""Pins the orchestrator's call shape and its derived lineage (spec §5.1-§5.4, §11).

Settings-at-import rule: CALL_CONFIG and PROMPT_VERSION are computed once, at import,
from the frozen settings. Patching backend.config.settings reaches nothing in
orchestrator.py. Patching backend.orchestrator.settings reaches only call-time reads
(summarize), never these two constants. Prefer scripting the fake client over
patching settings.

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
from collections.abc import Callable
from pathlib import Path

import pytest

from backend.config import settings
from backend.orchestrator import (
    CALL_CONFIG,
    CORRECTION_TEMPLATE,
    PROMPT_VERSION,
    SUMMARY_TOOL,
    SYSTEM_PROMPT,
    CallConfig,
    _derive_prompt_version,
)
from backend.schemas import SOAPNoteDraft

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
