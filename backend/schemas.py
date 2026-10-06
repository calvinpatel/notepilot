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

ClinicalClaim and SOAPNote are what grounding builds from a draft (§4.1).
Both are frozen and hold tuples, so a flag can't be assigned or appended after
construction (D6, L6).

New pipeline data shapes go here. The only shapes defined elsewhere are HTTP
edge shapes in api.py and check-internal shapes in evals/registry.py
(spec §13).
"""

from enum import Enum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

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


# --- what grounding produces: the source of truth -----------------------------


class SafetyFlag(str, Enum):  # noqa: UP042 — §4.1's form; StrEnum changes str()
    UNSUPPORTED = "unsupported"  # the quote grounds nowhere: likely fabrication
    PARAPHRASED = "paraphrased"  # matched only fuzzily: drifted, low confidence


class ClinicalClaim(ClaimDraft):
    # D6, enforced (L6): frozen blocks assignment, and tuples block in-place mutation.
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int  # required: without grounding there is no enriched claim (§4.1)
    source_span: tuple[int, int] | None = None  # half-open [start, end) into the raw text
    grounding_score: float | None = None  # L8
    flags: tuple[SafetyFlag, ...] = ()  # grounding's to write (D6)


class SOAPNote(BaseModel):
    model_config = ConfigDict(frozen=True)

    claims: tuple[ClinicalClaim, ...]

    def by_section(self, section: Section) -> list[ClinicalClaim]:
        """Display-time grouping. Section is a rendering concern, not a storage one."""
        return [c for c in self.claims if c.section == section]


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


# --- what evals produce (§4.2) ------------------------------------------------


class Severity(str, Enum):  # noqa: UP042 — §4.2's form; StrEnum changes str()
    CRITICAL = "critical"  # patient-harm potential
    WARNING = "warning"
    INFO = "info"


class EvalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    check: str  # the check's registered name (§8.7)
    severity: Severity
    passed: bool
    errored: bool = False  # L43: the check crashed or timed out
    detail: str = ""
    claim_ids: tuple[int, ...] = ()  # the claims it's about; () = note-level (§9.7)

    @model_validator(mode="after")
    def _errored_never_passes(self) -> Self:
        if self.errored and self.passed:
            raise ValueError("an errored check cannot pass")
        return self


class EvalReport(BaseModel):
    results: list[EvalResult]
    checks_run: frozenset[str]  # L44: what was selected, so "didn't run" isn't "didn't fire"
    checks_version: str  # L45
    judge_usage: TokenUsage = Field(default_factory=TokenUsage)  # L7

    @property
    def critical_results(self) -> list[EvalResult]:
        return [r for r in self.results if r.severity is Severity.CRITICAL]

    # mypy rejects decorators stacked on @property; the ignore is pydantic's documented form
    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_critical_passed(self) -> bool:
        """The note's verdict, serialized with the results it summarizes (L102).

        bool(crits) is the vacuous-truth guard: all() over no CRITICAL result is True, and
        that must not read as safe (invariant 12). An errored CRITICAL has passed=False, so
        a crash reads as a failure.
        """
        crits = self.critical_results
        return bool(crits) and all(r.passed for r in crits)


Species = Literal["fidelity", "detection", "control"]


class EvalCase(BaseModel):
    """A synthetic fixture carrying its own answer key (§4.2, §8.5). Zero real PHI."""

    model_config = ConfigDict(extra="forbid")  # L103: a misspelled key is a load error

    id: str
    species: Species  # L9: the author's intent, explicit
    raw_text: str
    draft: SOAPNoteDraft | None = None  # L42: set = an injected case (§8.5)
    trap: str | None  # what's deliberately dangerous; None = a control
    expected_flags: list[str] = Field(default_factory=list)  # the checks that should fire

    @model_validator(mode="after")
    def _species_matches_answer_key(self) -> Self:
        if (self.species == "detection") != bool(self.expected_flags):
            raise ValueError("detection traps, and only they, carry expected_flags")
        if (self.species == "control") != (self.trap is None):
            raise ValueError("controls, and only they, have trap=None")
        if self.species == "fidelity" and self.draft is not None:
            raise ValueError("a fidelity trap tests the MODEL; it cannot inject a draft")
        return self
