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
validation error goes back to the model as an is_error tool_result. Truncation,
a refusal, or a missing tool block would reproduce itself, so all three fail
fast. Transport retries (429/5xx) belong to the SDK, not this loop.

PROMPT_VERSION is derived from everything the model is conditioned on: the
system prompt, tool schema, correction template, and call config. Editing any
of them changes it; it is never bumped by hand.

Exception messages are static strings. The chained ValidationError (__cause__)
carries model-emitted text, so callers log these errors by .code only, never
with exc_info (spec §9.4, §9.8).
"""

import functools
import hashlib
import json
from collections.abc import Iterable
from typing import ClassVar, Final, Protocol, TypedDict

from anthropic import AsyncAnthropic
from anthropic.types import (
    Message,
    MessageParam,
    ModelParam,
    StopReason,
    TextBlockParam,
    ToolChoiceParam,
    ToolChoiceToolParam,
    ToolParam,
    ToolUnionParam,
)
from pydantic import ValidationError

from backend.config import settings
from backend.schemas import RunMetadata, SOAPNoteDraft, SummarizationResult, TokenUsage

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


# --- the failure domain (§5.4, §9.4; L14, L49, L88) ---------------------------------


class OrchestratorError(Exception):
    """Base: the orchestrator could not hand over a valid draft."""

    code: ClassVar[str] = "orchestrator_error"

    def __init__(self, msg: str, *, usage: TokenUsage) -> None:
        super().__init__(msg)
        self.usage = usage  # L49: failed calls cost money too


class ModelOutputError(OrchestratorError):
    """The model is the problem (no block, a refusal, or invalid after retries) -> 502."""

    code = "model_output_invalid"


class OutputTruncatedError(ModelOutputError):
    """stop_reason in TRUNCATION_STOPS on an input the route already accepted (§9.1).

    Not the client's fault (L14): the output/input ratio in config, or model verbosity -> 502.
    """

    code = "output_truncated"


# L88: both cut the output mid-emission. A context-window stop with a partial tool block
# would otherwise fail validation and "retry" with a LARGER context: invariant 16's
# identical-failure spend, made worse. Unreachable at sane max_input_chars; closed anyway.
TRUNCATION_STOPS: Final[frozenset[StopReason]] = frozenset(
    {"max_tokens", "model_context_window_exceeded"}
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


# --- the loop (§5.4; L12, L13, L53, L97) ---------------------------------------------


async def summarize(raw_text: str, *, client: LLMClient) -> SummarizationResult:
    """One forced tool call, validated at the boundary; the model corrects its own errors (§5.4).

    Returns a schema-valid draft with its RunMetadata, or raises an OrchestratorError subclass
    carrying the usage spent, failed attempts included (L49). Retries only when the next
    request differs from the last (invariant 16): a validation error goes back as an is_error
    tool_result; truncation (L88), a refusal (L97), and a missing block fail fast.
    """
    messages: list[MessageParam] = [{"role": "user", "content": raw_text}]  # L83
    usage = TokenUsage()
    last_error: ValidationError | None = None

    for attempt in range(1, settings.max_validation_retries + 2):
        resp = await client.messages.create(
            model=settings.model,
            system=SYSTEM_PROMPT,
            tools=[SUMMARY_TOOL],
            messages=messages,
            **CALL_CONFIG,
        )
        # L13: every attempt is paid for, so the sum lands before any gate can raise.
        usage += TokenUsage(
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens
        )

        if resp.stop_reason in TRUNCATION_STOPS:
            # Identical request at temperature=0 -> near-identical truncation. Fail fast.
            raise OutputTruncatedError("output truncated", usage=usage)

        if resp.stop_reason == "refusal":
            # L97: any block was cut off and is never validated -> nothing in `messages`
            # changes -> an identical request. Fail fast.
            raise ModelOutputError("refusal under forced tool_choice", usage=usage)

        tool_block = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_block is None:
            # Nothing in `messages` changed -> an identical non-answer. Fail fast.
            raise ModelOutputError("no tool_use block under forced tool_choice", usage=usage)

        try:  # L12: the try wraps model_validate and nothing else
            draft = SOAPNoteDraft.model_validate(tool_block.input)
        except ValidationError as e:
            # NOT an identical retry: the model now sees its own error. Worth spending.
            # L53: the correction carries the model's output back to the model, so the
            # input stays in; include_input=False is for log lines, which never see this.
            last_error = e
            messages += [
                {"role": "assistant", "content": resp.content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "is_error": True,
                            "content": CORRECTION_TEMPLATE.format(
                                errors=e.errors(include_url=False)
                            ),
                        }
                    ],
                },
            ]
            continue

        # Outside the try (L12): a bug building metadata is OUR error, never fed back to the
        # model as ITS mistake.
        return SummarizationResult(
            draft=draft,
            metadata=RunMetadata(
                model=settings.model,
                prompt_version=PROMPT_VERSION,
                usage=usage,
                validation_attempts=attempt,
            ),
        )

    raise ModelOutputError(
        f"invalid after {settings.max_validation_retries + 1} attempts", usage=usage
    ) from last_error
