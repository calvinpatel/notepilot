"""The spine: the pipeline's data contract (spec §4).

Imports only the standard library and pydantic: nothing from this app, no
vendor SDK, no web framework. The pipeline layers import it. clinical/ does
not; it works on plain strings.

ClaimDraft and SOAPNoteDraft are the model's contract. SOAPNoteDraft's JSON
schema IS the tool's input schema, so any change to either draft type's fields
or descriptions is prompt text the model reads. It changes PROMPT_VERSION and
breaks the tool-schema snapshot on purpose. Descriptions state shape
(verbatim, contiguous, one fact), never clinical rules; those live in the
system prompt.

New pipeline data shapes go here. The only shapes defined elsewhere are HTTP
edge shapes in api.py and check-internal shapes in evals/registry.py
(spec §13).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Section = Literal["S", "O", "A", "P"]
# whitespace is empty at this boundary, for text (L86) as for quote (L25)
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


# --- what the LLM emits: the tool contract -----------------------------------


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an invented field is the §5.4 retry

    text: NonBlankStr = Field(description="One clinical fact.")
    section: Section
    # a quote, not an offset; stripped at the boundary (L25)
    source_quote: NonBlankStr = Field(description="Verbatim; one contiguous span of the input.")


class SOAPNoteDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimDraft]


# --- what the orchestrator threads out -----------------------------------------


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)  # L89: `usage += ...` rebinds via __add__

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


class RunMetadata(BaseModel):
    model: str
    prompt_version: str
    usage: TokenUsage  # L13: summed across all validation attempts
    validation_attempts: int = Field(ge=1)  # L89


class SummarizationResult(BaseModel):
    draft: SOAPNoteDraft
    metadata: RunMetadata
