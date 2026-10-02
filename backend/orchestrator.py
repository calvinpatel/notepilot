"""Raw encounter text -> SummarizationResult, via one forced Anthropic tool call.

EDGE adapter (spec §0). Anthropic's message format appears here and in
judge_client.py, nowhere else; everything handed inward is a spine type. No
FastAPI import: api.py applies Depends(get_client). LLMClient is the typed seam
that both AsyncAnthropic and the test fake satisfy; get_client builds the real
client once per process.

summarize() returns a schema-valid draft with its RunMetadata, or raises an
OrchestratorError subclass carrying the TokenUsage spent so far, failed
attempts included. It never returns a partial draft.

It retries only when the next request differs from the last (spec §5.4). A
validation error goes back to the model as an is_error tool_result. Truncation
or a missing tool block would reproduce itself, so both fail fast. Transport
retries (429/5xx) belong to the SDK, not this loop.

PROMPT_VERSION is derived from everything the model is conditioned on: the
system prompt, tool schema, correction template, and call config. Editing any
of them changes it; it is never bumped by hand.

Exception messages can carry model-emitted clinical text, so callers log these
errors by .code only (spec §9.4, §9.8).
"""

import functools
import hashlib
import json
from collections.abc import Iterable
from typing import Final, Protocol, TypedDict

from anthropic import AsyncAnthropic
from anthropic.types import (
    Message,
    MessageParam,
    ModelParam,
    TextBlockParam,
    ToolChoiceParam,
    ToolChoiceToolParam,
    ToolParam,
    ToolUnionParam,
)

from backend.config import settings
from backend.schemas import SOAPNoteDraft

# Verbatim from spec §5.3 (D7, L20, L50). The opening backslash keeps the value free of a
# leading newline; the closing quotes sit on the last prompt line, so no trailing one.
SYSTEM_PROMPT: Final[str] = """\
You are a clinical documentation assistant. You are a scribe, not a consultant:
you record what the encounter says, and you never add clinical judgment of your
own. Convert the encounter into a SOAP note by calling emit_soap_note.

RULES
• Every claim MUST include a verbatim source_quote copied exactly from the input.
  If you cannot quote it, do not include the claim.
• Each source_quote is ONE contiguous span of the input. Never stitch two
  passages together. Prefer the shortest span that fully supports the claim.
• One clinical fact per claim. "Started amoxicillin 500 mg TID for 10 days" is
  one claim; "started amoxicillin, follow up in 2 weeks, denies fever" is three.
• Never infer, assume, or add facts not present in the source.
• Preserve negation and absence exactly as written: "denies", "no", "NKDA",
  "discontinued". A negated finding is a finding; do not drop it and do not
  flip it.
• Preserve certainty exactly as written: "likely", "possible", "r/o", "vs",
  "consistent with". Never turn a hedged statement into a definite one.
• When uncertain, OMIT — except safety-critical facts, which are ALWAYS carried
  forward: allergies and NKDA, and every medication started, stopped, or
  changed at this visit. Omitting a dangerous fact does not make a note safer;
  it hides the danger from the person signing it.

SECTIONS (set each claim's `section` field)
• S — Subjective: what the patient reports (symptoms, history, complaints),
  including the patient's own guesses about what is wrong.
• O — Objective:  measurable findings (vitals, exam, labs)
• A — Assessment: diagnoses or clinical impressions THE CLINICIAN stated,
  including differentials, with their stated certainty. Never generate an
  assessment the clinician did not state. If none was stated, emit no A claims.
• P — Plan:       orders, medications, follow-up"""

# §5.1 (L83): typed, so mypy checks it against the LLMClient Protocol (§5.5). The spine's
# JSON schema IS the tool contract; a change to ClaimDraft is a reviewed snapshot diff (§11).
SUMMARY_TOOL: Final[ToolParam] = {
    "name": "emit_soap_note",
    "description": "Return the structured SOAP summary of the encounter.",
    "input_schema": SOAPNoteDraft.model_json_schema(),
}

# §5.4: travels back to the model through the tool_result channel, never to a log (L53).
CORRECTION_TEMPLATE: Final[str] = (
    "Validation failed: {errors}. Call emit_soap_note again with input that satisfies the schema."
)


class SamplingBody(TypedDict):
    """§5.2 (L82): wire fields the SDK (>= 1.0) no longer types; typed on our side."""

    temperature: float


class CallConfig(TypedDict):
    """§5.2 (L83): `**CALL_CONFIG` is checked key-by-key against the Protocol."""

    tool_choice: ToolChoiceToolParam
    max_tokens: int
    extra_body: SamplingBody


# §5.2 (L15): everything that shapes the output, in one block (L75), hashed into
# PROMPT_VERSION. Read once at import from the frozen settings.
CALL_CONFIG: Final[CallConfig] = {
    "tool_choice": {
        "type": "tool",
        "name": SUMMARY_TOOL["name"],
        "disable_parallel_tool_use": True,  # L75: the §5.4 loop answers one block
    },
    "max_tokens": settings.max_output_tokens,  # L94
    "extra_body": {"temperature": 0},  # L82: invariant 3, on the wire
}


def _derive_prompt_version(
    *, system: str, tool: ToolParam, correction: str, call: CallConfig
) -> str:
    """Spec §5.4's expression (L15): everything the model is conditioned on, hashed."""
    payload = {"system": system, "tool": tool, "correction": correction, "call": call}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


# Derived, never declared (invariant 15). The model id is its own lineage field.
PROMPT_VERSION: Final[str] = _derive_prompt_version(
    system=SYSTEM_PROMPT,
    tool=SUMMARY_TOOL,
    correction=CORRECTION_TEMPLATE,
    call=CALL_CONFIG,
)


# --- the seam (§5.5; L19, L74) -------------------------------------------------------


class _AsyncMessages(Protocol):
    """The one SDK method the orchestrator calls, as the SDK types it.

    Exactly the keywords the orchestrator passes, all required (L74): a fake that drops or
    renames one stops binding. Types come from the SDK's `create` overload for
    `stream: Literal[False]`. `extra_body` is `object` because the SDK's `Body` is `object`
    (private anthropic._types); CallConfig (§5.2, L82) carries the precise type on our side.
    Never `dict[str, object]`: a TypedDict is not a dict subtype, and `**CALL_CONFIG` would
    stop type-checking.
    """

    async def create(
        self,
        *,
        model: ModelParam,
        system: str | Iterable[TextBlockParam],
        tools: Iterable[ToolUnionParam],
        messages: Iterable[MessageParam],
        tool_choice: ToolChoiceParam,
        max_tokens: int,
        extra_body: object,
    ) -> Message: ...


class LLMClient(Protocol):
    """What AsyncAnthropic and the test fake both satisfy; mypy checks both sides (§5.5).

    `messages` is a read-only property, not a bare attribute: a bare Protocol attribute is
    settable, and the SDK's `messages` is a cached_property. Not @runtime_checkable: an
    isinstance would check that attributes exist, not their signatures.
    """

    @property
    def messages(self) -> _AsyncMessages: ...


@functools.cache
def get_client() -> LLMClient:
    """One AsyncAnthropic per process (L78); key passed, never ambient (L77); no FastAPI (L95).

    For api.py's Depends(get_client) (§9.1): the cached function object is the override key.
    Settings are read here, on first call. Construction makes no network call.
    """
    return AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        timeout=settings.llm_timeout_s,
        max_retries=settings.sdk_transport_retries,
    )
