# PROJECT 01 — NotePilot

**A clinical-encounter → grounded, safety-checked SOAP summarizer.**
Flagship portfolio project. Status: **design locked.** Build state: §14's phase tags and
CLAUDE.md's "Current phase" line (L101).
**Spec version: v1.6.1** (patch — the loader imports the label readers, October 2026).
Supersedes v1.6.

> This document is the canonical build spec. It is the thing I build *against* and
> the thing a reviewer could read to understand the entire system end to end.
> Every field traces back to an origin; every check declares what it trusts; every
> layer's async and schema story agrees with its neighbors'.
>
> *However long — I arrive. However broken — I forge. So I return, and begin.* 🧱

**Where history lives.** This document states what the system *is*. How it got here —
each version's deltas, the `L#` ledger, and the `D#` decision records with their
reasoning — lives in `PROJECT_01_NOTEPILOT_CHANGELOG.md`. An `L#` or `D#` here is a
citation into that file.

**Versioning.** A *patch* (v1.x.y, L195) may fill a detail this spec leaves unspecified, or
resolve a conflict between two of its statements, citing both and naming which wins. A
*minor* revision (v1.x) is anything else: a changed decision, a new section, a new phase's
design. Every change lands with a changelog entry under the next `L#`.

---

## 0. How to read this

The system is five layers plus a shared clinical module. Data flows in one direction:

```
raw paste ─► orchestrator ─► grounding ─► evals ─► API/persistence ─► UI
             (LLM · edge)    (pure)       (pure + judge)  (FastAPI/PG · edge)  (React)
                                            ▲       ▲
         clinical/extract.py ───────────────┘       └─── Judge protocol ◄── judge_client.py (edge)
         (shared by the eval checks — across claim text, source span, and raw text)
```

**Domain vs edge (v1.3, L17).** *Domain* modules — `schemas.py`, `tracebacks.py`,
`grounding.py`, `clinical/`, `evals/` — know nothing about FastAPI, Postgres, or Anthropic,
and read no settings: a knob that decides a verdict is passed in (L187). *Edge* modules —
`orchestrator.py`, `judge_client.py`, `corpus.py` (L188), `api.py`, `db.py` — are adapters:
the only places a vendor's wire format may appear. Where the domain needs a network call
(the judge), it declares a `Protocol` and an edge module implements it. v1.2's "the domain
knows nothing about Anthropic" was false as written for the orchestrator and the judge;
this is the true version.

Read top to bottom: **principles → architecture → the data contract → each layer →
cross-cutting concerns → tests → build order.** The data contract (§4) is the
keystone; if you only internalize one section, internalize that one.

---

## 1. The product

A clinician pastes a messy encounter — rough notes or a raw transcript — and gets back:

1. a **clean, structured SOAP summary** (Subjective / Objective / Assessment / Plan),
2. **every claim linked to the exact source text** it came from (hover → highlight), and
3. an **automated safety pass** that flags anything dangerous — a dropped allergy, a
   hallucinated medication, a claim the source doesn't support, a contraindication.

They review, edit, sign off. That's the product. (v1.3, L1: v1 ships the *review*
surface; edit and sign-off persistence are v2 — §9.10, §15.)

It sits dead-center in the **ambient clinical documentation** category — one of the
highest-velocity spaces in health AI. (v1.3, L2: v1.2's market figure was unsourced and is
cut; any sizing number cites a primary source before it reaches the README.) The workflow
is one only someone with clinical training frames correctly.

It is a **documentation** product, not decision support: the model is a scribe, not a
consultant (D7, §5.3). It records what the clinician said; it never adds a judgment of
its own.

---

## 2. Why this project exists (the hiring thesis)

This single project is designed to prove **three things at once**, which is why it
replaces what would otherwise be two separate portfolio pieces:

| It must prove… | …and it does so via |
|---|---|
| I can **engineer real systems** (bridges the no-CS-degree gap) | full-stack app, real DB, clean module boundaries, tests, a thin composition-root API |
| I am **AI-engineer-coded** (the GenAI-SWE pattern) | structured LLM output, grounding, RAG cross-check, an eval harness, self-correction |
| I have a **moat a generalist can't replicate** | clinical judgment rendered as executable safety logic |

The moat is **not** the résumé line "ex-med-school." The moat is the eval layer (§8):
a test suite only a clinician can author. The moat gets the interview; the plumbing
(§9) gets me trusted.

**The sentence this whole project earns me, said out loud in the room:**

> "Every safety check is proven against injected traps on every commit, for free. Then
> N synthetic encounters, each run k times against the real model, measure what the model
> actually does: it preserves safety-critical facts in F% of fidelity traps, the pipeline
> surfaces C% of planted source dangers, clean notes stay clean S% of the time — and when
> the model does drop something, the live safety layer catches it X% of the time. When I
> change a prompt or drop to a cheaper model, I re-run it against the persisted run history
> and watch whether any of those four numbers regressed."

(v1.3, L3: v1.2's sentence said "catches X% of CRITICAL safety violations," and no field
computed it — `pass_rate` blended three species. The four numbers are `CorpusMetrics`,
§4.2 / §8.7. X counts a live CRITICAL alone, L206.)

That last clause — **evals as regression tests for a stochastic system, with lineage** —
is the frontier of production AI engineering.

---

## 3. North-star principles (the laws that recur in every layer)

These are not style preferences. Each one prevents a specific class of bug, and their
*consistency across all five layers* is itself the senior signal a reviewer reads.

1. **Judgment to the model, mechanics to code.** The LLM decides *what* to extract and
   *how* to bucket it. Deterministic code decides *where* it sits, *whether* it's valid,
   and *whether* it's safe. Every time you ask the LLM to do something code does better
   (count characters, find offsets, compare drug names), you add a failure mode for free.
2. **Dependencies point inward, at the schema.** `schemas.py` imports nothing and is
   imported by everything. The domain knows nothing about HTTP, Postgres, or Anthropic.
   Side-effects live at the edges; the core stays pure.
3. **Design for evaluability.** Shape the data so "is this output safe?" is a *function
   you can run*, not a vibe you assert. A served model's replies vary from run to run,
   and the pinned model accepts no sampling parameter to narrow them (L181) — so the eval
   design measures the variance instead of suppressing it, *by construction*: pass-rates
   over a corpus, k repeats per case (D11), never golden-output diffs. That tolerance is
   a design property, not an apology.
4. **Failure-to-ground is a signal, not an error.** A fabricated claim is the thing this
   product exists to catch. Flag it and continue; don't raise. (Contrast: an invalid
   *schema* IS an error and DOES raise — knowing which is which is the whole skill.)
5. **Scope discipline (watch the Volkswagen).** A V12 in a Volkswagen ships nothing.
   Every "real-system" refinement that isn't load-bearing for the MVP goes in the v2
   backlog (§15) — where it doubles as evidence I know the production-grade version and
   *chose* scope deliberately.
6. **Eliminate cheaply before judging expensively (v1.3, L4).** Every decision runs its
   cheapest sufficient test first and escalates only what that test can't settle: exact
   match before fuzzy (§6.1), deterministic checks before the judge (§8.2), injected drafts
   before paid corpus runs (§8.5). v1.2 embodied this everywhere and named it nowhere — and
   an unnamed principle is one a future edit breaks quietly.

### 3.1 Architectural invariants (L196)

The principles above are why; these are the properties the code keeps, and code that breaks
one is a bug. They are numbered for citation (the spec, CLAUDE.md, and code comments cite
them by number), and the numbers don't change. CLAUDE.md keeps each number and title, with
Claude Code's standing instruction where an invariant has one; the statement is here.

1. **Dependencies point inward at `schemas.py`; vendors stay at the edge.** `schemas.py`
   imports nothing; everything imports it. DOMAIN modules (`schemas.py`, `tracebacks.py`,
   `grounding.py`, `clinical/`, `evals/`) know nothing about FastAPI, Postgres, or
   Anthropic, and read no settings: a knob that decides a verdict is passed in (L187), and
   an AST test holds the line (L188). EDGE modules (`orchestrator.py`, `judge_client.py`,
   `corpus.py`, `api.py`, `db.py`) are adapters — the only places a vendor's wire format
   may appear. When the domain needs a network call it declares a `Protocol`
   (`evals/judge.py: Judge`) and an edge module implements it (§0, L17).
2. **Grounding is pure and makes zero LLM calls.** Deterministic string work only. Judgment
   to the model, mechanics to code — never ask the LLM to count characters, find offsets,
   or compare drug names.
3. **Every pipeline LLM call pins what shapes its output — summarize AND the judge.** Its
   tool choice, thinking, effort, and token budget live in one call config, hashed into its
   version (L15); nothing is left to an API default that can change with no diff in the
   repo. Forced `tool_choice` on the summarize call. No sampling parameters: the pinned
   model rejects them (L180), so variance is measured, not suppressed — repeats (D11) and
   the corpus design absorb it.
4. **Errors-as-values inside the pipeline; raise at boundaries.** An ungroundable claim is
   a *result* (`UNSUPPORTED` flag), not an exception. A model that can't produce a valid
   draft IS an exception at the orchestrator boundary: `OrchestratorError` →
   `ModelOutputError` → `OutputTruncatedError`, each carrying the `usage` it cost and its
   `validation_attempts` (L186); EAFP; `raise … from`. Once a valid draft exists, nothing
   reaches the user as an exception: grounding returns flags, checks fail closed, persist
   logs and swallows.
5. **Safety extraction scans the WHOLE note.** The S/O/A/P section is the model's judgment
   call, display-only. Any safety check that reads only one section is a bug.
6. **Flag ownership is a write boundary (D6), enforced by the types.** Grounding owns
   `ClinicalClaim.flags` (`UNSUPPORTED`, `PARAPHRASED`) and nothing else ever writes to it.
   `ClinicalClaim` and `SOAPNote` are frozen; `flags` and `claims` are tuples. Evals emit
   `EvalResult`s that *reference* claims via `claim_ids`; they consume grounding's flags,
   never re-derive them, never mutate a claim.
7. **LLM-as-judge is never the sole gate on a CRITICAL check.** The judge is WARNING-tier;
   a judge that errors or times out changes no CRITICAL verdict.
8. **Persistence is a sink.** `persist()` runs as a background task after the response is
   assembled, in its own session; a write failure is logged, never 500s the user. The
   pipeline never reads from the DB.
9. **Spans are half-open `[start, end)`** — Python slicing convention, always.
10. **No magic numbers.** Operational knobs → `config.py` (pydantic-settings). Clinical
    knowledge — including `NEGATION_WINDOW` — → `clinical/lexicons.py`.
11. **Corpus scoring consumes `expected_flags` via `case_verdict()`** (§8.7) — a tri-state:
    `passed` / `failed` / `not_applicable`. A fired expected flag is a PASS for a detection
    trap. An errored check never satisfies an expected flag (L43); an expected check that
    didn't run is `not_applicable`, never `failed` (L44).
12. **Empty never reads as safe.** `all_critical_passed` guards vacuous truth — zero
    CRITICAL results returns False. A check that raises inside `run_checks` becomes
    `EvalResult(passed=False, errored=True)` — never a skipped check, never a 500, never a
    magic `detail` string. The same law, other roads: an empty note from clinical input is
    a WARNING, not green; "not checked" never renders as "passed"; a metric over an empty
    denominator is `None`, not 1.0; a case scored on a report that ran no check is
    `not_applicable`, never `passed` (L117).
13. **`clinical/` imports nothing from the spine.** `extract.py` imports only
    `lexicons.py`; `lexicons.py` imports nothing (severities stored as plain strings).
    Extractors take plain strings and return multi-valued results; the checks run the same
    extractor over `claim.text`, the source span, and `raw_text`, and compare.
14. **Grounding proves the quote exists; the consistency family proves the text agrees with
    the SOURCE SPAN** — `raw_text[claim.source_span]`, never the model's `source_quote`
    (§6.4, L35). At Tier 3 the quote is the model's claim about the source; the span is the
    source. A Tier 1 exact match is not evidence the text is true.
15. **Lineage is derived, never declared.** `prompt_version` = hash(system prompt + tool
    schema + correction template + call config); `corpus_version` = hash(the model cases a
    run scores, L204);
    `checks_version` = hash(the `.py` files in `evals/` + `clinical/` + `grounding.py` +
    `schemas.py`, L114, L189), with the verdict knobs recorded whole beside it
    (`checks_config`, L187); `settings.model` = a pinned model id, never an alias (§5.5,
    L84 — dateless ids from the 4.6 generation on are pinned; never validate with a date
    regex); `git_dirty` recorded on every corpus run. A hand-bumped version string is a lie
    waiting for someone to forget.
16. **Retry only when the next request differs from the last.** Validation error → the
    model sees its mistake → retry (`max_validation_retries`, §5.4). `max_tokens` or a
    missing block → an identical request, which reproduces its cause (the budget, the
    input, the forced call), not an identical reply → fail fast (L183). Transport retries
    (429/5xx) are the SDK's (`sdk_transport_retries`, §5.2) — a different loop with a
    different name.
17. **The omission law (D17).** Every CRITICAL check documents, per input, what happens
    when the model omits that input — a docstring and a test. An omission that silences the
    check must be covered by another live check or declared a CI-only gap. A new CRITICAL
    check without its omission row is incomplete (§8.4).
18. **Scribe, not consultant (D7, L50).** The prompt never lets the model state a clinical
    judgment the clinician didn't: Assessment is clinician-stated, certainty verbatim,
    patient self-diagnosis is Subjective. "Omit when uncertain" never applies to
    safety-critical facts — allergies, NKDA, NKA, and every medication started, stopped, or
    changed at this visit (L191).
19. **PHI never leaves through the side doors.** Raw text, note content, and exception
    messages that may carry them never reach a log line or an HTTP body. Error bodies are
    `{error, request_id}`; `OrchestratorError` is logged by `code` without `exc_info`; a
    crashed check logs its name, type, and frames, never its message or `exc_info` (L113);
    validation errors are stringified with `include_input=False` (§9.4, §9.8). This is the
    runtime twin of "zero PHI in the repo."
20. **A test's tier is decided by what's stochastic in its path.** Injected cases
    (`EvalCase.draft` set) are deterministic and run free on every commit; model cases are
    paid. A danger the *model* creates (a fabrication, a flip) is tested by injecting it —
    never by a model case that hopes the model will make it (§8.5, L42).

---

## 4. The data contract — the spine ⭐ KEYSTONE

A clinical claim is **not a sentence**. It is an object that carries its own provenance.
The moment the summary is a block of text, citations die (nothing to point at), evals
die (can't check a blob), and the safety pass dies (nothing to attach a flag to).
**The structure *is* the product.**

### 4.1 The draft → enriched lifecycle

The atom changes shape as it moves through the system. The LLM emits a *draft*; grounding
and evals *enrich* it. One model cannot be both the LLM contract and the enriched result —
so the spine is a **family**, not a single class:

```python
from enum import Enum
from typing import Annotated, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

Section = Literal["S", "O", "A", "P"]

def _strip(value: object) -> object:  # L106: str.strip(), so blank here is what
    return value.strip() if isinstance(value, str) else value  # str.isspace() says (§6.2)

NonBlankStr = Annotated[str, StringConstraints(strict=True, min_length=1),
                        BeforeValidator(_strip)]
                                    # v1.3.2 (L86): whitespace is empty at this boundary —
                                    #   for the claim's text as for its quote (L25). The
                                    #   validator wraps the str schema, so a blank string
                                    #   still fails as string_too_short; strict, so bytes
                                    #   can't be decoded past the strip (L106)

# --- what the LLM emits: the tool contract -----------------------------------
class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")   # v1.3: promoted from CLAUDE.md. An invented
                                                #   field is a ValidationError → the §5.4
                                                #   retry; additionalProperties:false tells
                                                #   the model up front.
    text: NonBlankStr = Field(description="One clinical fact.")
    section: Section                  # the SINGLE encoding of section membership
    source_quote: NonBlankStr = Field(description="Verbatim; one contiguous span of the input.")
                                      # the LLM emits THIS, NOT an offset (models can't
                                      # count chars). v1.3 (L25): stripped at the boundary,
                                      # so "" AND "   " fail validation → retry.

class SOAPNoteDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[ClaimDraft]          # flat. section lives on the claim, nowhere else.

# --- what grounding produces: the internal + response source of truth ---------
class SafetyFlag(str, Enum):
    UNSUPPORTED  = "unsupported"      # quote grounds nowhere → likely fabrication
    PARAPHRASED  = "paraphrased"      # matched only fuzzily → drifted, low confidence

class ClinicalClaim(ClaimDraft):                           # inherits the draft fields
    model_config = ConfigDict(extra="forbid", frozen=True) # v1.3 (L6): D6, enforced
    id: int                                                # position in note.claims, stamped
                                                           #   by grounding — the anchor
                                                           #   every finding hangs on
    source_span: tuple[int, int] | None = None             # None = grounds nowhere; offsets
                                                           #   count code points (L177)
    grounding_score: float | None = None                   # the Tier 3 score whenever fuzzy
                                                           #   matching was evaluated — incl.
                                                           #   Tier 4 near-misses and numeric
                                                           #   demotions (v1.3, L8). None for
                                                           #   the exact tiers.
    flags: tuple[SafetyFlag, ...] = ()                     # grounding's ONLY (D6). A tuple,
                                                           #   so nothing downstream can
                                                           #   append to it.

class SOAPNote(BaseModel):
    model_config = ConfigDict(frozen=True)
    claims: tuple[ClinicalClaim, ...]

    def by_section(self, section: Section) -> list[ClinicalClaim]:
        """Display-time grouping. Section is a rendering concern, not a storage one."""
        return [c for c in self.claims if c.section == section]
```

**Field descriptions are structural, never clinical (v1.3, promoted from CLAUDE.md).** The
tool schema is prompt the model reads, so descriptions say *shape* — verbatim, contiguous,
one fact. Clinical rules (negation, certainty, allergies, D7) live in the system prompt
(§5.3). Both are covered by `PROMPT_VERSION` (§5.4), so edits are versioned automatically.

**DECISION D6 (v1.2, enforced v1.3) — flag ownership is a write boundary.**
`ClinicalClaim.flags` is grounding's, full stop. Evals never mutate a claim; they emit
`EvalResult`s that *reference* claims by `id` (`claim_ids`, §4.2). Two reasons: (1) the
enriched note is persisted and returned as-is — if evals also wrote to it, "what did
grounding say?" would be unrecoverable after the fact; (2) an eval finding can involve
several claims at once (an allergy claim *and* a prescription claim), which a per-claim flag
list can't express. The UI joins the two by `id` (§9.7, §9.10).

v1.2 called this "a write boundary, not just a naming convention" — and enforced nothing:
Pydantic models are mutable by default, so `claim.flags.append(...)` inside a check passed
every test. v1.3 (L6): `frozen=True` blocks attribute assignment, and `tuple` blocks
in-place mutation (`frozen` alone does not — a frozen model's list is still a list). "`id`
is stable because the note is immutable" is now true by construction.

**Why a family and not one model with optional fields (made explicit, v1.3).** A single
`Claim` carrying `source_span = None` and `flags = []` would (1) put `source_span` and
`flags` into the tool schema — inviting the model to emit offsets it can't count and to
vouch for itself with `flags: []` (and `extra="forbid"` can't help: those fields are
*declared*); and (2) make `source_span=None, flags=[]` mean "grounding never ran," with
nothing to distinguish it from a clean claim — a refactor that skipped `ground()` would
render every claim clean, which is invariant 12's failure at the type level. With the
family, `SOAPNote` requires `ClinicalClaim`, which requires `id`: a pipeline that skips
grounding cannot construct its return type. Illegal states, unrepresentable.

**Why flat (v1.1):** the prior shape carried `section` on every claim AND sorted claims
into four section-named lists — two encodings of one fact, and two encodings can
disagree (a claim with `section="P"` sitting in the `subjective` list was
representable, with no defined winner). One encoding, zero validators defending a
redundancy. Bonuses: the tool schema the model must satisfy gets simpler, the
degenerate empty note is one empty list, and §8.3's "iterate every claim" is just
`note.claims` — the whole-note safety law is now the *path of least resistance*
instead of a discipline.

**The honest one-spine claim:** *one schema family with a draft-to-enriched lifecycle —
the draft is the model contract, the enriched is the source of truth for citations,
persistence, and the API.* (Knowing an object's shape changes as it moves through a
system is a more senior thing to say than "one model, six jobs.")

### 4.2 The eval + run types

```python
from datetime import datetime
from pydantic import computed_field, model_validator

class Severity(str, Enum):
    CRITICAL = "critical"    # patient-harm potential
    WARNING  = "warning"
    INFO     = "info"

class TokenUsage(BaseModel):                # v1.3: one shape for every cost number
    model_config = ConfigDict(frozen=True)  # v1.3.2 (L89): `usage += …` rebinds via __add__
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(input_tokens=self.input_tokens + other.input_tokens,
                          output_tokens=self.output_tokens + other.output_tokens)

class EvalResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    check: str                              # stamped by @register_check (§8.7) — the
    severity: Severity                      #   check function never spells these itself
    passed: bool
    errored: bool = False                   # v1.3 (L43): the check crashed or timed out.
                                            #   Replaces v1.2's magic detail="check_error".
                                            #   Never passed; never satisfies an expected
                                            #   flag (§8.7).
    detail: str = ""
    claim_ids: tuple[int, ...] = ()         # which claims this finding is about.
                                            # () = note-level → the banner channel (§9.7).

    @model_validator(mode="after")
    def _errored_never_passes(self) -> "EvalResult":
        if self.errored and self.passed:
            raise ValueError("an errored check cannot pass")
        return self

class EvalReport(BaseModel):
    results: list[EvalResult]
    checks_run: frozenset[str]              # v1.3 (L44): what was SELECTED — lets the
                                            #   verdict tell "didn't fire" from "didn't run"
    checks_version: str                     # v1.3 (L45, L57): hash of the check code (§8.7)
    judge_usage: TokenUsage = Field(default_factory=TokenUsage)
                                            # v1.3 (L7): the judge's cost finally has a home.
                                            #   v1.2 declared RunMetadata.judge_* fields that
                                            #   nothing could ever write to.

    @property
    def critical_results(self) -> list[EvalResult]:
        return [r for r in self.results if r.severity is Severity.CRITICAL]

    @computed_field                         # L102: serialized, so the verdict crosses the
    @property                               #   wire with the results it summarizes (§9.3)
    def all_critical_passed(self) -> bool:
        crits = self.critical_results
        return bool(crits) and all(r.passed for r in crits)
        # bool(crits) is the vacuous-truth guard: all() over an empty list is True, and
        # "no CRITICAL check ran" must NEVER render as "safe". An errored CRITICAL has
        # passed=False, so a crash turns the note red (invariant 12).

PreserveKind = Literal["allergy", "medication", "dose", "finding", "diagnosis"]

class PreserveItem(BaseModel):              # DECISION D4: a typed expectation.
    model_config = ConfigDict(extra="forbid")   # L103, as on EvalCase
    text: str                               # L214: one reading, as its kind's extractor
                                            #   reads it: "PCN allergy", "metformin held"
    kind: PreserveKind                      # CRITICAL, lowered to WARNING for a dose, a
                                            #   dropped NKDA or NKA, a downgrade, or a
                                            #   reopened exclusion (§8.6, L217)
    present: bool = True                    # v1.3 (L36): findings carry polarity. "denies
                                            #   chest pain" is preserved as present=False; a
                                            #   note that flips it has NOT preserved it. On
                                            #   findings only, agreeing with the text (L219)

NotAddKind = Literal["medication", "finding", "diagnosis"]

class NotAddItem(BaseModel):                # v1.3 (L10): typed, like its mirror
    model_config = ConfigDict(extra="forbid")   # L103, as on EvalCase
    text: str
    kind: NotAddKind                        # routes to ONE extractor; findings match POSITIVE
                                            #   polarity only (L36) — a faithful "denies chest
                                            #   pain" is not an invented chest pain

Species = Literal["fidelity", "detection", "control"]

class EvalCase(BaseModel):                  # a synthetic fixture (zero real PHI)
    model_config = ConfigDict(extra="forbid")   # L103: a misspelled key is a load error. A
                                                #   typo'd `draft:` would otherwise leave
                                                #   draft=None: an injected case, run as a
                                                #   model case.
    id: str
    species: Species                        # v1.3 (L9): the author's intent, explicit
    raw_text: str
    draft: SOAPNoteDraft | None = None      # v1.3 (L42): an INJECTED case. The runner skips
                                            #   the model and grounds + checks this draft —
                                            #   deterministic, free, every commit (§8.5).
    trap: str | None                        # what's deliberately dangerous (None = control)
    must_preserve: list[PreserveItem] = Field(default_factory=list)
    must_not_add: list[NotAddItem] = Field(default_factory=list)
    expected_flags: list[str] = Field(default_factory=list)
                                            # checks that SHOULD fire — consumed by
                                            # case_verdict() (§8.7); validated against the
                                            # registry at load (§8.5)

    @model_validator(mode="after")
    def _species_matches_answer_key(self) -> "EvalCase":
        if (self.species == "detection") != bool(self.expected_flags):
            raise ValueError("detection traps, and only they, carry expected_flags")
        if (self.species == "control") != (self.trap is None):
            raise ValueError("controls, and only they, have trap=None")
        if self.species == "fidelity" and self.draft is not None:
            raise ValueError("a fidelity trap tests the MODEL; it cannot inject a draft")
        return self

class RunMetadata(BaseModel):               # threaded out of the orchestrator
    model: str                              # a PINNED model id, never an alias (§5.5, L84)
    prompt_version: str                     # hash of the full call config (§5.4)
    usage: TokenUsage                       # v1.3 (L13): summed across ALL validation
    validation_attempts: int = Field(ge=1)  #   attempts — a model that needs three tries
                                            #   must not look as cheap as one that needs one
    # v1.3 (L11): corpus_version and judge_* are gone from here. A per-run fact (the corpus)
    # lives on CorpusRunRecord; the judge's usage lives on EvalReport. Every field on this
    # model has a producer in phase 1.

class SummarizationResult(BaseModel):
    draft: SOAPNoteDraft
    metadata: RunMetadata

# --- corpus run lineage — the CI half of the regression thesis ----------------
CaseStatus = Literal["passed", "failed", "not_applicable"]

class CaseResult(BaseModel):                # ONE (case, repeat) pair
    case_id: str
    repeat: int = Field(ge=0)               # D11: 0 … corpus_repeats-1 (L212)
    species: Species
    status: CaseStatus                      # v1.3 (L44): not_applicable = an expected check
                                            #   wasn't selected this run (e.g. judge off), or
                                            #   (L117) no check ran at all. A case with an
                                            #   `error` is "failed" (L205)
    fired_checks: list[str]                 # fired (passed=False) and NOT errored
    missing_expected: list[str]             # expected_flags that did NOT fire
    unexpected_fired: list[str]             # fired but not expected, ALL severities — a
                                            #   diagnostic, not a gate
    usage: TokenUsage | None                # L186: summarize's, every attempt. Both
    validation_attempts: int | None = Field(ge=1)   # None together, only when a
                                            #   crash lost the case's cost (§8.7)
    summarize_wall_s: float = Field(ge=0, allow_inf_nan=False)
                                            # L201: summarize's wall time — every attempt,
                                            #   and the SDK's transport retries with their
                                            #   backoff (§8.7)
    draft: SOAPNoteDraft | None             # L203: what the model returned; None when
                                            #   summarize returned no draft. Grounding and
                                            #   the checks are pure, so a run replays free
    errored_checks: list[str] = Field(default_factory=list)   # v1.3 (L43)
    error: str | None = None                # pipeline failure CODE — never a message (L53)

    @model_validator(mode="after")
    def _cost_known_together(self) -> "CaseResult":    # L212: L186's "None together"
        if (self.usage is None) != (self.validation_attempts is None):
            raise ValueError("usage and validation_attempts are None together")
        return self

class CorpusMetrics(BaseModel):             # v1.3 (L3): four numbers, never one
    detection_recall: float | None          # detection repeats passed / applicable
    control_specificity: float | None       # control repeats passed / applicable
    model_fidelity: float | None            # fidelity repeats passed / applicable
    fidelity_caught: float | None           # of fidelity repeats that FAILED without a
                                            #   pipeline error, the fraction where a LIVE
                                            #   (reference-free) CRITICAL fired (L206)
    pass_rate: float | None                 # kept for continuity; never quoted alone (L205)
    flaky_cases: list[str]                  # D11: pass fraction strictly between 0 and 1
    # None, not 1.0, over an empty denominator — a vacuous metric is not a perfect one.
    # A repeat is applicable unless it is not_applicable (L205).

class ChecksConfig(BaseModel):              # L187: the knobs that decide verdicts,
    model_config = ConfigDict(frozen=True)  #   built at the edge only and passed in
    fuzzy_score_cutoff: float = Field(ge=0, le=100, allow_inf_nan=False)   # §6.3, L105
    min_quote_content_tokens: int = Field(ge=1)                            # §8.4, L161

class CorpusRunRecord(BaseModel):
    ran_at: datetime
    git_sha: str                            # L207: both read before the first call
    git_dirty: bool                         # v1.3 (L45): D5 runs on uncommitted code by
                                            #   design — the record says so
    model: str
    prompt_version: str
    corpus_version: str
    checks_version: str                     # v1.3 (L45): a lexicon edit changes verdicts;
                                            #   now it changes the lineage too
    checks_config: ChecksConfig             # L187: so does a knob, so it's recorded
    judge_enabled: bool
    repeats: int = Field(ge=1)              # D11 (L212)
    concurrency: int = Field(ge=1)          # L202: contention lands in the wall times and
                                            #   the upstream failures
    n_cases: int = Field(ge=1)              # distinct MODEL cases (injected ones are pytest's)
    metrics: CorpusMetrics
    usage: TokenUsage                       # summarize, incl. failed attempts (L13, L49):
                                            #   the sum of the cases' known usages (L186)
    judge_usage: TokenUsage                 # kept separate — the split IS the cost story
    cases: list[CaseResult]                 # n_cases × repeats rows: debug regressions,
                                            #   don't just watch a number move

    @model_validator(mode="after")
    def _one_row_per_repeat(self) -> "CorpusRunRecord":   # L212
        if len(self.cases) != self.n_cases * self.repeats:
            raise ValueError("cases holds n_cases * repeats rows")
        return self
```

---

## 5. Layer 1 — Orchestrator

**Job:** `summarize(raw_text) -> SummarizationResult`. Raw mess in, validated draft (+ run
metadata) out. Everything downstream assumes this hands over a clean, schema-valid object.

### 5.1 Getting structure out of the model: tool use (not "respond in JSON")

The spectrum, worst → best: prompt-for-JSON + `json.loads` (fragile to fences, preambles,
trailing commas) → assistant prefill → **tool use (function calling)**. With tool use, the
tool's input schema *is* our draft schema, and we force the call:

```python
SUMMARY_TOOL: ToolParam = {                              # v1.3.2 (L83): typed, so mypy checks
    "name": "emit_soap_note",                            #   it against the Protocol (§5.5)
    "description": "Return the structured SOAP summary of the encounter.",
    "input_schema": SOAPNoteDraft.model_json_schema(),   # the spine becomes the contract
}
```

### 5.2 The call (async, pinned, forced)

```python
class CallConfig(TypedDict):                             # v1.3.2 (L83): `**CALL_CONFIG` is
    tool_choice: ToolChoiceToolParam                     #   checked key-by-key against the
    max_tokens: int                                      #   Protocol; a dict[str, object]
    thinking: ThinkingConfigDisabledParam                #   unpacks as `object` everywhere
    output_config: OutputConfigParam                     #   (L181: the SDK's param types)

CALL_CONFIG: CallConfig = {                              # v1.3 (L15): everything that shapes
    "tool_choice": {"type": "tool", "name": "emit_soap_note",    # the output, in one place —
                    "disable_parallel_tool_use": True},          # hashed into PROMPT_VERSION
    "max_tokens": settings.max_output_tokens,                    # (§5.4). L75: one block.
    "thinking": {"type": "disabled"},                            # L181: pinned, never an
    "output_config": {"effort": "low"},                          #   API default (inv. 3)
}

resp = await client.messages.create(
    model=settings.model,                                # pinned model id (§5.5, L84)
    system=SYSTEM_PROMPT,
    tools=[SUMMARY_TOOL],
    messages=messages,
    **CALL_CONFIG,
)
```

- **No sampling parameters (L181).** The pinned model rejects `temperature` (400,
  "deprecated for this model", L180), so the call sends no `temperature`, `top_p`, or
  `top_k`, and no `extra_body` to carry one: L82's route is retired. Variance is
  measured, not suppressed — the corpus design (§8.7) and its repeats (D11) absorb it.
  What would otherwise be left to the API is pinned instead. `thinking` is disabled:
  `max_tokens` covers thinking tokens, so a model that thinks spends §5.2's budget on text
  no check reads. `effort` is `"low"`, provisional: the baseline's repeats (§14) test it.
  Both live in `CALL_CONFIG`, so both are inside `PROMPT_VERSION` (invariant 15), typed
  with the SDK's own param types; `CallConfig.thinking` is the disabled variant alone, so
  turning thinking on is a type change, not a value edit (mypy rejects
  `{"type": "enabled", …}` there, measured). The tempting "fix" when the SDK or the API
  rejects a call-config field — deleting it — hands that field to a default that can change
  with no diff in the repo (invariant 3); flag it. *Test:* the fake client records
  `thinking == {"type": "disabled"}` and `output_config == {"effort": "low"}` on every
  `create` call, validation retries included, and no `temperature`, `top_p`, `top_k`, or
  `extra_body` — L82's test, inverted.
- **forced `tool_choice`** means the model must populate the structure; it can't wander
  into prose. The pinned model accepts it (L180); Sonnet 5.5, Opus 5.5, and Fable 5.1
  return 400 for it (found in phase 1's step 3a), which is why §5.5's comparison arm waits.
- **Parallel tool use is off (L75).** §5.4's API contract: every `tool_use` block in an
  assistant turn must be answered by a `tool_result` for the same id in the next user
  message — and §5.4's loop answers only the first block. Forcing the tool does not cap the
  block count, so a two-block response would make the validation retry 400, which §9.4
  reports as our 500. The unanswerable state is prevented, not handled. The flag lives in
  `CALL_CONFIG`, so it is inside `PROMPT_VERSION` automatically (invariant 15).
  *Test:* the fake client records the kwargs of every `create` call; `tool_choice` carries
  the flag on every attempt, validation retries included.
- **async** (`AsyncAnthropic`): the LLM call is the one genuinely I/O-bound, seconds-long
  step in the system. (The route in §9 awaits this.)
- **`max_output_tokens` is derived from `max_input_chars`.** The output is mostly *copies of
  the input* (every `source_quote` is a verbatim span), so output size scales with input
  size; `config.py` derives one from the other. Two knobs that must move together are one
  knob. **v1.3.3 (L94):** the ratio is itself a knob, `output_tokens_per_input_char` (`gt=0`,
  default `1.6`, L184), and
  `max_output_tokens = math.ceil(max_input_chars * output_tokens_per_input_char)` is a
  read-only property on `Settings`, never a field: a field could be set from the environment
  independently of `max_input_chars`, which is two knobs again. The unit crosses from
  characters to tokens on purpose — the ratio absorbs chars-per-token *and* the output's
  overhead beyond the copied quotes (claim text, JSON structure), so it is tuned empirically,
  not derived. It feeds `CALL_CONFIG`, so tuning it changes `PROMPT_VERSION` (invariant 15).
  **The defaults are measured (L184).** On the smoke encounter (943 chars) the output ran
  1.40 tokens per input char on Haiku 4.5 (the `v0.2a-safety` run) and 1.19 to 1.32 on the
  pinned model (four probe calls). At the old default of 0.5 every request got 10,000
  tokens, so an encounter past about 7,600 chars would truncate: a 502 on input the route
  accepted. The ratio is 1.6, the pinned model's worst case (1.32) plus about 20%, and
  `max_input_chars` is 12,500, so `max_output_tokens` is 20,000 — sized to the timeout
  (next bullet), not to the input the route used to accept. One encounter measured
  linearity; the model corpus gives the distribution, and the ratio is retuned from it.
  **v1.3 (L16):** the derived value is validated against the model's output ceiling *at
  boot* — raising `max_input_chars` (or the ratio) past what the model can emit fails at
  startup, not per request. The ceiling is
  `settings.model_max_output_tokens`, declared directly beside `model` — the two change
  together (L72). The Models API does report the ceiling (`models.retrieve(id).max_tokens`),
  but reading it at boot is a network call, and CI runs offline (§10); so it is declared,
  and the phase-1 smoke run verifies the declaration against the API (v1.3.2, L85, §14).
  *Test:* settings whose derived `max_output_tokens` exceeds the ceiling raise at
  construction; a non-positive `output_tokens_per_input_char` raises at construction;
  `"max_output_tokens" not in Settings.model_fields` (L94).
- **The budget must fit the timeout (L185).** Three links, one chain: `max_input_chars` ×
  the ratio is `max_output_tokens`; `max_output_tokens` ÷ the model's output throughput is
  the longest call; and the longest call must fit inside `llm_timeout_s` with margin, or a
  truncation's 502 becomes a timeout's 504. The probe measured ~320 output tokens/s (L180),
  so 20,000 tokens is about 63 s of generation; the smoke run on the pinned model measured
  ~273 end to end, with the prompt, the network, grounding, and the checks included, so
  about 73 s (L198). Both fit inside the 90 s timeout. The end-to-end figure is the one to
  bound by: the timeout clocks only the API call, so a figure that also counts grounding,
  the checks, and the browser's round trip overstates it, which errs safe. The first link
  is checked at boot (L16); the third can't be, because throughput is the model's, measured
  over the network. The smoke run re-measures it at each pin change (L81, L85, §14). The
  SDK refuses a non-streaming `max_tokens` above 21,333 on its default timeout and skips
  that check when the client sets one (L180), so it guards nothing here: the client always
  sets one.
- **Timeouts and transport retries are explicit (v1.3, L54, L5).** The client is built once
  as `AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value(),
  timeout=settings.llm_timeout_s, max_retries=settings.sdk_transport_retries)`. The SDK's default timeout is measured in
  minutes — a hung upstream call would hold a worker that long; a timeout now maps to 504
  (§9.4). The SDK's `max_retries` retries *transport* failures (429, 5xx) with backoff, and
  an identical request is correct there: the failure is about load, not content. That is a
  different loop from §5.4's *validation* retries, and v1.3 gives the two different names
  so nobody "enforces" invariant 16 by zeroing the wrong one.
- **"Built once" means once per process (L78).** `get_client` is the FastAPI dependency
  that supplies the client (§9.1). **It lives in `orchestrator.py`, beside the `LLMClient`
  Protocol it returns (v1.3.3, L95):** the module that owns the vendor's format is the one
  that constructs the vendor's client. It is a plain cached factory that imports nothing
  from FastAPI — `api.py` applies `Depends(get_client)` at the route, so the orchestrator
  stays framework-free and `api.py` never constructs a client. FastAPI calls dependencies
  per request — so `get_client` is decorated `@functools.cache`: one `AsyncAnthropic`, one connection pool,
  constructed on first use. Without the cache, every request builds and abandons an httpx
  pool. Route tests override it via `dependency_overrides`; the override key is the cached
  function object, which is what `Depends` holds. *Test:* `get_client() is get_client()`
  (construction makes no network call; the conftest dummy key suffices, §10).
- **The key is passed, never ambient (L77).** pydantic-settings reads `.env` into
  `Settings` but never exports it to `os.environ`, the only place the SDK looks. An
  implicit key works in a shell that happens to export it and 401s everywhere else — which
  §9.4 would report as our 500. `anthropic_api_key` is a required `SecretStr` (§10), kept
  out of `repr` and logs.

### 5.3 The system prompt — where the moat first appears in code

A generalist writes "summarize this into SOAP." The clinical version (v1.3, L191):

```
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
  "NKA", "discontinued". A negated finding is a finding; do not drop it and do
  not flip it.
• Preserve certainty exactly as written: "likely", "possible", "r/o", "vs",
  "consistent with". Never turn a hedged statement into a definite one.
• When uncertain, OMIT — except safety-critical facts, which are ALWAYS carried
  forward: allergies, NKDA, NKA, and every medication started, stopped, or
  changed at this visit. Omitting a dangerous fact does not make a note safer;
  it hides the danger from the person signing it.

SECTIONS (set each claim's `section` field)
• S — Subjective: what the patient reports (symptoms, history, complaints),
  including the patient's own guesses about what is wrong.
• O — Objective:  measurable findings (vitals, exam, labs)
• A — Assessment: diagnoses or clinical impressions THE CLINICIAN stated,
  including differentials, with their stated certainty. Never generate an
  assessment the clinician did not state. If none was stated, emit no A claims.
• P — Plan:       orders, medications, follow-up
```

"Omit when uncertain" is a **clinical safety stance**: a missing line is recoverable; an
invented medication is a patient-safety event. **v1.3 (L50) draws its boundary:** it is safe
for *uncertain* content and never for *safety-critical* content. A dropped contraindicated
prescription is not caution — the clinician signs a note that looks clean while the order
goes through. Allergies had this exception in v1.2; medications started, stopped, or
changed now do too, and §8.4 backs the rule with live checks. The prompt names NKA beside
NKDA in both places (L191): NKA is the stronger statement (food and environmental allergens
too, D10), and whether "allergies" covers "no known allergies" was left to the model.
*Test:* the never-omit clause names both NKDA and NKA. The S/O/A/P definitions encode what
actually belongs where — a non-clinician gets the Assessment-vs-Plan boundary subtly wrong
and never knows.

**DECISION D7 (v1.3, vetoable) — the model is a scribe, not a consultant.** v1.2's prompt
said "never infer" *and* defined A as "clinical interpretation" — and §8.2's judge existed
to adjudicate inferred assessments. The contradiction resolves toward clinician-stated
only, for three reasons. **Authorship:** the clinician signs the note; an assessment they
never made becomes their diagnosis on record, then the problem list, then billing, then the
next clinician's anchor — and automation bias means it gets approved at sign-off.
**Product category:** summarizing what the clinician said is documentation; generating
diagnoses is clinical decision support — a different product under different scrutiny.
**Consistency:** "never infer" and "omit when uncertain" become true without exceptions.
Three sharpenings ride along: *stated*, not *written* (transcripts speak their
assessments); a patient's self-diagnosis is S, not A; and **certainty is clinical
information exactly as negation is** — "r/o PE" → "PE" is a flip on a different axis. An
empty A is a valid, faithful note (§9.10 renders it as such).

**v1.2 additions, each aimed at a downstream layer:** *contiguous, shortest span* is for
grounding (a stitched quote can only ever reach Tier 3 or 4, so it manufactures PARAPHRASED
noise); *one fact per claim* is for extraction and anchoring (a paragraph-sized claim makes
`claim_ids` useless and lets a bad drug hide behind three good ones); *negation verbatim*
and *allergies always* are for the checks — the prompt tries to pass the fidelity traps on
purpose, and the checks exist for when it doesn't. Prompt-level behavior and check-level
detection are two layers, not one.

### 5.4 The boundary: validate, and self-correct

Tool use *steers* but does not *guarantee*. Validate at the boundary; on failure, hand the
model its own error and let it fix itself (graceful degradation around a stochastic
component — a pattern almost no pivoter portfolio shows).

**The API contract this loop must honor (v1.1):** once an assistant turn contains a
`tool_use` block, the next user message **must** answer it with a `tool_result` block
referencing the same `tool_use_id` — a plain-text correction 400s. So the validation error
travels back **through the tool-result channel**, marked `is_error=True`:

```
user:      raw_text
assistant: [tool_use     id=tu_1           {…invalid…}]
user:      [tool_result  tool_use_id=tu_1  is_error=True  "Validation failed: …"]
assistant: [tool_use     id=tu_2           {…}]
```

```python
import hashlib, json

class OrchestratorError(Exception):
    """Base: the orchestrator could not hand over a valid draft."""
    code = "orchestrator_error"

    def __init__(self, msg: str, *, usage: TokenUsage, validation_attempts: int):
        super().__init__(msg)
        self.usage = usage                  # v1.3 (L49): failed calls cost money too
        self.validation_attempts = validation_attempts   # L186: and how many tried

class ModelOutputError(OrchestratorError):
    """The model is the problem (no block / invalid after retries) → 502."""
    code = "model_output_invalid"

class OutputTruncatedError(ModelOutputError):
    """stop_reason in TRUNCATION_STOPS on an input the route ALREADY accepted (§9.1). v1.3 (L14):
    v1.2 called this InputTooLongError → 422, blaming the client for an input that passed
    our own guard. The fault is the output/input ratio in config, or model verbosity → 502."""
    code = "output_truncated"

TRUNCATION_STOPS = frozenset({"max_tokens", "model_context_window_exceeded"})
# v1.3.2 (L88): both cut the output mid-emission. A context-window stop with a partial tool
# block would otherwise fail validation and "retry" with a LARGER context — invariant 16's
# identical-failure spend, made worse. Unreachable at sane max_input_chars; closed anyway.

CORRECTION_TEMPLATE = (
    "Validation failed: {errors}. "
    "Call emit_soap_note again with input that satisfies the schema."
)

# The version is DERIVED, not declared (invariant 15). v1.3 (L15): v1.2 hashed the prompt
# and the tool schema but not the retry text or the call parameters — both shape the
# output. Everything the model is conditioned on is in the hash; the model id is its own
# lineage field.
PROMPT_VERSION = hashlib.sha256(json.dumps({
    "system": SYSTEM_PROMPT, "tool": SUMMARY_TOOL,
    "correction": CORRECTION_TEMPLATE, "call": CALL_CONFIG,
}, sort_keys=True).encode()).hexdigest()[:12]

async def summarize(raw_text: str, *, client: LLMClient) -> SummarizationResult:
    messages: list[MessageParam] = [{"role": "user", "content": raw_text}]   # L83
    usage = TokenUsage()
    last_error: ValidationError | None = None

    for attempt in range(1, settings.max_validation_retries + 2):
        resp = await client.messages.create(
            model=settings.model, system=SYSTEM_PROMPT, tools=[SUMMARY_TOOL],
            messages=messages, **CALL_CONFIG,
        )
        usage += TokenUsage(input_tokens=resp.usage.input_tokens,      # v1.3 (L13): every
                            output_tokens=resp.usage.output_tokens)    #   attempt is paid for

        if resp.stop_reason in TRUNCATION_STOPS:
            # Identical request → same budget, input, forced call (L183). Fail fast.
            raise OutputTruncatedError("output truncated", usage=usage,
                                       validation_attempts=attempt)

        if resp.stop_reason == "refusal":
            # L97: any block was cut off and is never validated → nothing in `messages`
            # changes → an identical request. Fail fast.
            raise ModelOutputError("refusal under forced tool_choice", usage=usage,
                                   validation_attempts=attempt)

        tool_block = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_block is None:
            # Nothing in `messages` changed → an identical non-answer. Fail fast.
            raise ModelOutputError("no tool_use block under forced tool_choice",
                                   usage=usage, validation_attempts=attempt)

        try:
            draft = SOAPNoteDraft.model_validate(tool_block.input)   # v1.3 (L12): the try
        except ValidationError as e:                                 #   wraps THIS line only
            # NOT an identical retry: the model now sees its own error. Worth spending.
            last_error = e
            messages += [
                {"role": "assistant", "content": resp.content},
                {"role": "user", "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "is_error": True,
                    "content": CORRECTION_TEMPLATE.format(errors=e.errors(include_url=False)),
                }]},
            ]
            continue

        return SummarizationResult(                                  # outside the try: a bug
            draft=draft,                                             #   building metadata is
            metadata=RunMetadata(                                    #   OUR error — never fed
                model=settings.model,                                #   back to the model as
                prompt_version=PROMPT_VERSION,                       #   ITS mistake
                usage=usage,
                validation_attempts=attempt,
            ),
        )

    raise ModelOutputError(
        f"invalid after {settings.max_validation_retries + 1} attempts", usage=usage,
        validation_attempts=settings.max_validation_retries + 1,
    ) from last_error
```

**Why the `try` is one line wide (v1.3, L12).** v1.2 wrapped `model_validate` *and* the
construction of `SummarizationResult`/`RunMetadata`. If building the metadata ever raised a
`ValidationError` (an SDK `usage` shape change, a new required field), the loop would tell
the model it had made a mistake it didn't make, and pay to retry. Fault attribution is the
whole point of this function; the `try` covers exactly the model's output.

**A refusal fails fast before the block lookup (L97).** `stop_reason="refusal"`
means the API's classifiers stopped the output mid-emission, so any tool block
present is as cut off as a truncated one. Validated anyway, it is either returned as
a success with claims missing — the clinician signs a note that looks complete — or
it buys validation retries against a classifier that fires again on the same input.
Gated before the lookup, the block is never validated, nothing in `messages`
changes, and invariant 16 holds as written. Same exception and code as §9.4's
no-block refusal (L73). `pause_turn` needs server tools and `stop_sequence` needs
stop sequences, and this call sends neither; `end_turn` without a block takes the
missing-block branch. A test pins every `StopReason` value to one of these paths, so
an SDK that adds a stop reason fails CI instead of falling through.

**The correction goes to the model, never to a log (v1.3, L53).** The model sees its own
output echoed back in the validation errors — that's the point, and it's traffic to the
same API that produced it. What must never carry that text is a log line or an HTTP body:
handlers log `OrchestratorError` by `code` + request id without `exc_info`, and the `from`
chain exists for tests and local debugging (§9.4, §9.8).

The error-handling arc: EAFP at the boundary, an exception *hierarchy* that names the
failure domain **and whose fault it is**, `raise … from` preserving the cause, and every
failure carrying what it cost. The retry rule is one sentence: **retry only when the next
request differs from the last one** (invariant 16). Truncation, a refusal, and a missing
block don't change the request → fail fast: an identical request reproduces its cause — the
budget, the input, the forced call — even when the reply itself varies (L183). A validation
error feeds the model its mistake → the request changed → retry. (Transport retries are the
SDK's — §5.2, a different loop.)

### 5.5 Seam & model choice

- **`client` is injected, and typed (v1.3, L19; L74).** `LLMClient` is a `typing.Protocol`;
  the real `AsyncAnthropic` and the test fake both satisfy it, so mypy checks the seam every
  test depends on. Its `create` declares exactly the keywords the orchestrator passes —
  `model`, `system`, `tools`, `messages`, `tool_choice`, `max_tokens`, `thinking`,
  `output_config` (L181) — typed with the SDK's own param types so contravariance can't
  bite (allowed: the orchestrator is EDGE, §0). `CallConfig` (§5.2) narrows `thinking` to
  the disabled variant on our side. No loose signature checks anything: `**kwargs: Any`
  alone rejects `AsyncAnthropic`, and `*args: Any, **kwargs: Any` is treated as `...`.
  `messages` is a read-only `@property` on the Protocol, not a bare attribute: a bare
  protocol attribute is settable, and the SDK's `messages` is a cached property. Tests pass
  a fake returning a canned tool-use block, built from real `anthropic.types.Message`
  objects so the fake can't drift from the wire format: no network, no real key, fast,
  deterministic. *Test:* mypy over `backend/` and `tests/`, forced by binding sites on both
  sides — `get_client() -> LLMClient` returns `AsyncAnthropic(...)`, and the fake in
  `tests/` is bound to an `LLMClient`-typed name. Without both, mypy checks half the seam.
- **The orchestrator is an edge adapter (v1.3, L17).** It is one of two modules allowed to
  speak Anthropic's message format (the other is `judge_client.py`, §8.2). Everything it
  hands inward is a spine type.
- **Model choice is eval-driven, not vibes — and costed.** Start on the cheap/fast (Haiku)
  tier; run the corpus; if a smaller model holds the four metrics (§4.2), you've *earned*
  the right to use it and can prove it. With `usage` summed across validation attempts
  (L13) and the judge's usage kept separately (L7), the claim is *"Haiku holds the safety
  metrics at a measured fraction of Sonnet's cost per note — including the retries it
  needed."* The Sonnet arm is decided at phase 3 planning, where the cost line is owed
  (§14): Sonnet 5.5 rejects the forced call the pinned model accepts (L180), so no one
  call shape spans the two.
- **`settings.model` is a pinned model id, never an alias (v1.3.2, L84).** An alias can
  resolve to different weights next month with no diff in the repo — every
  `CorpusRunRecord.model` would say the same thing while meaning different things. v1.3.1
  said "dated": true of the ids before the Claude 4.6 generation (use
  `claude-haiku-4-5-20251001`, never its alias `claude-haiku-4-5`), false from 4.6 on, where
  the dateless id *is* the pinned snapshot. The test for pinned is Anthropic's model-ids
  page at the time of the change, never a date-suffix regex — that would reject every
  current-generation id. Upgrading the model is a
  deliberate config change that shows up in `git log`, next to the corpus run that
  justified it. The pinned model is `claude-haiku-5-5` (L180), with
  `model_max_output_tokens` 128000 (`models.retrieve`, L85).

---

## 6. Layer 2 — Grounding

**Job:** `ground(draft, raw_text, *, config) -> SOAPNote`. The orchestrator *claimed* every
claim has a source; grounding **proves it** — with **zero LLM calls**, pure deterministic
string work. It constructs the enriched `ClinicalClaim` for each `ClaimDraft`.

### 6.1 The matching ladder ⭐ (the layer's keystone)

`raw_text.find(quote)` alone is **wrong**: models normalize compulsively (expand `pt`→
`patient`, fix typos, swap curly→straight quotes, collapse spaces), so an honest paraphrase
returns −1 and gets screamed at as a hallucination. The central tension of the layer:
**did the model paraphrase a real quote, or invent a fake one?** The ladder separates them:

```
Tier 1  exact substring                  ─► span, no flag          (clean)
Tier 2  normalized exact                 ─► span, no flag          (whitespace/case/quotes)
Tier 3  fuzzy ≥ cutoff AND digits match  ─► span + PARAPHRASED     (low confidence)
Tier 4  nothing survives                 ─► no span + UNSUPPORTED  (hallucination signal)
```

Tier 4 is the **first hallucination detector**, and it cost zero API calls. The ordering is
principle 6: each tier runs only on what the cheaper tier above it couldn't settle.

### 6.2 Offset mapping (mechanics → code)

Normalizing to compare shifts every index, so a match in *normalized* space points to the
wrong place in the *original*. Keep a map back to original coordinates:

```
original:    P  t  ␣  ␣  d  e  n  i  e  s  \t C  P
orig idx:    0  1  2  3  4  5  6  7  8  9  10 11 12
normalized:  p  t  ␣     d  e  n  i  e  s  ␣  c  p
index_map:  [0, 1, 2,    4, 5, 6, 7, 8, 9, 10,11,12]     (orig idx 3 collapsed away)
```

```python
PUNCT_MAP = {
    "\u201c": '"', "\u201d": '"',    # curly double quotes
    "\u2018": "'", "\u2019": "'",    # curly single quotes
    "\u2013": "-", "\u2014": "-",    # en / em dash
    "\u00b5": "\u03bc",              # v1.3 (L26): micro sign → Greek mu. Identical glyphs,
}                                    #   different code points — and in "µg" a dose unit.

@dataclass(frozen=True)
class NormalizedText:
    text: str
    index_map: tuple[int, ...]       # normalized index → original index (L192: a tuple)

    @classmethod
    def of(cls, text: str) -> "NormalizedText":
        """Lowercase + collapse whitespace + fold punctuation variants, keeping the map."""
        out: list[str] = []
        index_map: list[int] = []
        prev_space = False
        for i, ch in enumerate(text):
            if ch.isspace():
                if not prev_space:
                    out.append(" "); index_map.append(i)
                prev_space = True
                continue
            for c in PUNCT_MAP.get(ch, ch).lower():   # v1.3 (L26): lower() may return MORE
                out.append(c); index_map.append(i)    #   than one char ("İ" → "i̇"); every
            prev_space = False                        #   char it yields maps to the original
        return cls("".join(out), tuple(index_map))   # L192: frozen once, here

    def to_original(self, n_start: int, n_end: int) -> tuple[int, int]:
        """Half-open normalized [n_start, n_end) → half-open original span."""
        if n_start >= n_end:                          # L109: an empty slice has no last
            raise ValueError("empty normalized slice")  #   character; at 0, index_map[-1]
        return self.index_map[n_start], self.index_map[n_end - 1] + 1   #   wraps to the end
```

**The map is a tuple (L192).** `frozen=True` blocks reassigning `index_map`, not
`index_map.append(...)`, and a list field makes the generated `__hash__` raise `TypeError`
(both measured) — L6's smell, one layer down. `of()` builds a list and freezes it once, at
the end; tests compare the map to tuple literals.

**The off-by-one that lives in `to_original`:** the end is the *last matched character's*
original index plus one — never `index_map[n_end]`, which may not exist and, when it does,
points past collapsed whitespace:

```
find "denies cp" in normalized → [n_start=3, n_end=12)
✓ (index_map[3], index_map[11] + 1) = (4, 13)    raw[4:13] == "denies\tCP"
✗ (index_map[3], index_map[12])       → IndexError
```

**An empty slice raises (L109).** `to_original(k, k)` has no last matched character, and at
`k = 0` `index_map[-1]` wraps to the end and returns the whole text as the span. Tier 2's
normalized quote is never empty and Tier 3 checks `src_end > src_start`, so an empty slice
is a caller's bug: `to_original` raises `ValueError` rather than return a plausible span.

**The v1.2 Unicode bug (v1.3, L26).** v1.2 appended `ch.lower()` as one character with one
map entry. `"İ".lower()` is two code points, so `out` grew by two while `index_map` grew by
one — every index after it silently wrong. The per-character loop fixes it; if a match ends
inside a multi-character expansion, `to_original` still returns an end past the whole
original character, which is the correct half-open span. §11's property test generates
non-ASCII text so this can't regress.

### 6.3 The ladder, assembled

```python
import re
from rapidfuzz import fuzz

_DIGITS = re.compile(r"\d+(?:[./]\d+)?")     # 120, 0.5, 190/110, 2.5

def _numbers_match(quote: str, span_text: str) -> bool:
    """Fuzzy is allowed to forgive letters, never digits.
    Every numeric token in the quote must appear verbatim in the aligned span."""
    span_nums = set(_DIGITS.findall(span_text))
    return all(n in span_nums for n in _DIGITS.findall(quote))

def _snap(raw_text: str, start: int, end: int) -> tuple[int, int]:
    """Widen a span to whole words (L108): an alignment window can start or end mid-word."""
    while start > 0 and raw_text[start - 1].isalnum() and raw_text[start].isalnum():
        start -= 1
    while end < len(raw_text) and raw_text[end - 1].isalnum() and raw_text[end].isalnum():
        end += 1
    return start, end

def ground_claim(draft: ClaimDraft, raw_text: str, norm: NormalizedText,
                 *, claim_id: int, config: ChecksConfig) -> ClinicalClaim:
    quote = draft.source_quote             # stripped + non-blank at the boundary (L25, L106)
    base = draft.model_dump() | {"id": claim_id}

    idx = raw_text.find(quote)                                       # Tier 1
    if idx != -1:
        return ClinicalClaim(**base, source_span=(idx, idx + len(quote)))

    nq = NormalizedText.of(quote).text
    n_idx = norm.text.find(nq)                                       # Tier 2
    if n_idx != -1:
        return ClinicalClaim(**base, source_span=norm.to_original(n_idx, n_idx + len(nq)))

    align = fuzz.partial_ratio_alignment(norm.text, nq)              # Tier 3 — in NORMALIZED
    if align is not None and align.src_end > align.src_start:        #   space (v1.3, L27)
        span = _snap(raw_text, *norm.to_original(align.src_start, align.src_end))  # L108
        if (align.score >= config.fuzzy_score_cutoff                 # L187: passed in
                and _numbers_match(quote, raw_text[span[0]:span[1]])):
            return ClinicalClaim(**base, source_span=span, grounding_score=align.score,
                                 flags=(SafetyFlag.PARAPHRASED,))
        return ClinicalClaim(**base, grounding_score=align.score,    # Tier 4, score KEPT:
                             flags=(SafetyFlag.UNSUPPORTED,))        #   near-misses and
                                                                     #   numeric demotions are
                                                                     #   the tuning data (L8)
    return ClinicalClaim(**base, flags=(SafetyFlag.UNSUPPORTED,))    # Tier 4

def ground(draft: SOAPNoteDraft, raw_text: str, *, config: ChecksConfig) -> SOAPNote:
    norm = NormalizedText.of(raw_text)                               # once per note
    return SOAPNote(claims=tuple(
        ground_claim(c, raw_text, norm, claim_id=i, config=config)
        for i, c in enumerate(draft.claims)
    ))
```

Spans are **half-open `[start, end)`** — same convention as Python slicing, so
`raw_text[start:end]` returns the quote and a whole class of off-by-one bugs disappears
(invariant 9).

**Why Tier 3 moved into normalized space (v1.3, L27).** v1.2 ran fuzzy matching on the raw
strings because rapidfuzz then returns original coordinates for free. The price: fuzzy
scoring is case- and whitespace-sensitive, so a paraphrase that *also* changed
capitalization lost points Tier 2 had already forgiven. Now both strings are normalized,
aligned, and mapped back through the same `to_original` as Tier 2 — one mapping path, not
two. A unit test pins which string's coordinates `src_start`/`src_end` refer to for this
argument order; nobody's memory of the rapidfuzz API is trusted over a test.

**Tier 3's span snaps to whole words (L108).** `partial_ratio_alignment` aligns a window
exactly as long as the normalized quote, so when the source says the same thing in more
characters, the window cuts a word at one end: `1000mg BID` aligns to
`ncrease metformin to 1000 mg BID`, and `75mcg daily` to
`stable on levothyroxine 75 mcg dail`. §6.4 hands the span to the consistency family as what
the source says (L35), and a cut word is a mismatch the source doesn't contain. So the span
widens to whole words before the numeric guard reads it; widening only adds characters, so
the guard loses no digit. A window that misses a token entirely (`PHQ9 score 7` aligned to
`PHQ-9 score `) isn't rescued: the guard demotes it, the safe direction.

**Why the numeric guard is a clinical decision, not a string-matching one (v1.2):**
`partial_ratio("BP 130/110", "BP 190/110")` scores 90.0, exactly the default cutoff (L105,
L110), so without the guard it would ground as PARAPHRASED. Letters are where models
paraphrase (`pt` → `patient`); digits are where they *hallucinate* — a wrong vital, a wrong
dose, a wrong date. For numbers, any difference *is* invention. The guard errs toward red:
`5.0 mg` quoted as `5 mg` demotes to `UNSUPPORTED` even though the value is equal — the safe
direction, and trailing zeros are on the do-not-use list anyway. The guard lives in
grounding, not evals, because it decides the *tier* — whether the quote is real — and only
grounding may write that (D6). Whether a claim's text agrees with a real span is evals'
question (§6.4, §8.4).

**The cutoff routes; it doesn't detect (L105).** `fuzzy_score_cutoff` defaults to 90.
Measured on synthetic notes, one-token fabrications (a side, `mcg` for `mg`, a look-alike
drug, a flipped negation) scored as high as 98, above most honest paraphrases, so no cutoff
separates the two. What the cutoff decides is the route. At or above it, a claim whose
digits match keeps its span, and the consistency family checks the text against that span
(L35); below it, the claim is UNSUPPORTED, and the red badge and `hallucinated_medication`
own it. 90 errs red, as the numeric guard does. L8 keeps every near-miss score, so 2b's
model corpus can retune it.

### 6.4 Errors-as-values, structural flags, and the eval handoff

- Grounding **almost never raises.** An ungroundable claim is a *result*, not an error
  (Principle 4, invariant 4). A smoke detector should not burst into flame.
- Grounding owns only **structural / provenance** flags (`UNSUPPORTED`, `PARAPHRASED`) —
  "did this come from the source at all?" The eval layer owns **clinical-semantic**
  findings — "is this set of claims medically safe?"
- **Explicit handoff (not coincidence):** the eval layer's `hallucinated_medication` check
  **consumes** grounding's `UNSUPPORTED` flag rather than re-deriving it (invariant 6). Two
  layers re-deriving the same fact can disagree; this can't.
- **What grounding does NOT prove — the honest boundary:** grounding proves the *quote*
  exists in the source. It says nothing about whether the claim's *text* follows from it.
  `text="start amoxicillin"` / `quote="start antibiotics"` is a perfect Tier 1 match and a
  fabricated drug. That question — is the text entailed? — belongs to evals (§8.4), because
  answering it needs the clinical extractors, and grounding imports none of them
  (invariant 14).
- **The span is the ground truth handed to evals (v1.3, L35).** Once grounding has found a
  span, *that* is what the source says; the `source_quote` is only what the model *claims*
  it says. At Tiers 1–2 they are the same text. At Tier 3 they differ by definition — and a
  long quote with one swapped drug name or one flipped "denies" can clear the fuzzy cutoff
  with its digits intact. So every eval that asks "does the text agree with the source?"
  compares `claim.text` against `raw_text[claim.source_span]`, never against the quote.
  Responsibility partitions cleanly:

  ```
  source_span is None  → grounding's red badge + hallucinated_medication own it
  source_span exists   → the consistency family compares text against the SPAN
  ```

- **The rule for which layer owns a check:** if it decides whether the quote is real, it's
  grounding's; if it decides whether the claim is true to a real span, it's evals'. The
  numeric guard is the first kind; `dose_consistency` is the second — which is why they
  can't swap.

### 6.5 Edge cases (bake into tests day one)

- **Smart quotes / en-dashes / µ vs μ** — folded by `PUNCT_MAP` (§6.2); the tests assert it.
- **Multi-character lowercase** (`"İ"`) — the per-character map loop (§6.2); the property
  test generates non-ASCII text.
- **Quote longer than any clean span** (model merged two sentences) — fuzzy catches partial,
  flags low-confidence. The prompt asks for contiguous, shortest spans, so this should be
  rare; the test stays because "should" is not a guarantee.
- **Same quote appears twice** ("denies chest pain") — first-occurrence default; *know* you
  chose it.
- **Empty / whitespace-only quote** — the schema strips and requires length ≥ 1 (§4.1), so
  `""` *and* `"   "` fail validation and trigger the §5.4 retry. (v1.2 described
  `min_length=1` and the Tier 0 guard as two defenses against one input; they covered
  different inputs — `"   "` passed `min_length=1`. v1.3, L25.) A blank quote is
  unrepresentable on both sides of grounding (L106), so Tier 0 is gone (L107): its output
  could never be constructed. A draft built around a blank quote without validation is a
  programming error, and grounding raises when it builds the claim.
- **Fuzzy match with mismatched digits** — `"BP 190/110"` against a source that says
  `"BP 130/110"` → `UNSUPPORTED`, not `PARAPHRASED`, with its `grounding_score` kept.
- **Degenerate quote (v1.3, D15)** — `quote="the"` or `quote="pain"` is a clean Tier 1
  match almost anywhere; "the quote exists" proves nothing when the quote says nothing.
  Grounding is right to accept it (it *is* in the source); the finding belongs to evals:
  `quote_informativeness` (§8.4), backed by the entailment judge. A bare lexicon name is as
  degenerate as "the" (L158): it grounds wherever the source names it, and drops the cue
  beside it, which is how a flip reads green (§8.8, L157).

**Deliberate non-feature (v2):** locality-based duplicate resolution (pick the occurrence
nearest where sibling claims matched). Real and satisfying; decorative before the pipeline
runs end-to-end.

### 6.6 Why this is secretly the interview flex

Grounding has **no external dependencies** — most testable layer in the system. And it's
genuinely **algorithmic** (substring search, normalization-with-index-mapping, fuzzy
alignment, threshold tuning) — the algorithm-round content the hiring loop demands, sitting
naturally inside the most AI-flavored project. A reviewer reads clean string-algorithm code
*with tests* and concludes "can actually engineer," not just "can call an API."

---

## 7. Layer 3 — Clinical extraction (shared module)

**`clinical/extract.py`** — the hardest hidden subproblem, depended on by the eval checks.
Pulling a drug or allergy out of a free-text claim is its own little NLP task:

- **brand → generic** normalization (Tylenol → acetaminophen) so a set-compare doesn't flag
  a false hallucination — applied to **allergens too** (v1.3, L30): "Augmentin allergy" is
  an amoxicillin-clavulanate allergy.
- **scoped negation** ("denies chest pain" is NOT a positive symptom) — with a real scope
  rule (v1.3, L31, below).
- **medication status** ("discontinue lisinopril" is NOT an active prescription) — its own
  lexicon class, separate from finding negation (L31), with its own extractor (D13).
- **`NKDA`** is itself clinical information that must survive — and **NKA** (no known
  allergies, including food and environmental) is a different fact (D10).
- **allergy-context awareness (v1.2):** "allergic to penicillin" *mentions* a drug and
  *prescribes* nothing. Without this exclusion `extract_drugs` hands "penicillin" to the
  contraindication check, which then fires on every penicillin-allergic patient.
- **certainty** ("likely", "r/o") on diagnoses (D12) — negation's sibling on another axis.

**Who shares it (v1.3, L29).** v1.2's §0 diagram said extraction was "shared by grounding
+ evals." It isn't — grounding imports none of it, and the numeric guard is local regex.
Extraction is shared along two *other* axes: across **three strings** (the same extractor
runs over `claim.text`, the claim's source span, and `raw_text`, and the check compares),
and across **two modes** (the live checks and the CI reference checks use the same
primitives, so a fixture can't pass on a matching rule the product doesn't have, §8.4).

**The primitives operate on plain strings (v1.2) and return multi-valued results
(v1.3, L33).** v1.2's `dict[str, str]` doses and `dict[str, bool]` findings collapsed a
titration ("250 mg, then 500 mg") and a mixed finding ("denies chest pain at rest, reports
chest pain on exertion") to whichever came last. Every comparison in §8.4 is now one rule —
**text ⊆ span** — over sets.

```python
# clinical/extract.py — imports ONLY clinical/lexicons.py (v1.3, L65). Pure text → sets.
from typing import Literal, NamedTuple

class Dose(NamedTuple):
    value: float                     # parsed, so "500mg TID" == "500 mg tid" (L33)
    unit: str                        # "mg", "μg" (folded), "ml" …
    freq: str | None                 # normalized: "tid", "bid", "daily" …

MedStatus = Literal["active", "stopped"]
Certainty = Literal["definite", "probable", "possible", "rule_out"]   # strongest first

def extract_drugs(text: str) -> set[str]:
    """Generic names mentioned as ACTIVE. Brand→generic. Excludes negated, stopped
    (MED_STOP_CUES, MED_STOP_POST: L125), and allergy-context mentions."""

def extract_med_status(text: str) -> dict[str, set[MedStatus]]:
    """v1.3 (D13): drug → the statuses asserted for it. "continue apixaban" → {"active"};
    "discontinue apixaban" → {"stopped"}. Consumed by med_status_consistency."""

def new_prescriptions(text: str) -> set[str]:
    """v1.3 (L41): drugs STARTED at this visit — a MED_START_CUES cue within the window
    ("start", "prescribe", "Rx", "begin"), or a MED_START_POST cue just after the drug
    ("amoxicillin started", L125). Deliberately narrow: the only drug derivation
    from raw text trusted enough to run live (§8.1). "mom takes metformin", "tried
    ibuprofen last year", "discussed a statin, pt declined" → excluded."""

def extract_allergies(text: str) -> set[str]:
    """v1.3 (L30): allergens NORMALIZED — brand→generic, aliases resolved ("PCN" →
    "penicillin"). A key is a generic drug ("amoxicillin"), a class ("penicillin",
    "sulfa", "nsaid"), "nkda", or "nka". Absence is information."""

def extract_doses(text: str) -> dict[str, set[Dose]]:
    """drug → parsed doses. A set, so a titration keeps both. (D1, L33.)"""

def extract_findings(text: str) -> dict[str, set[bool]]:
    """finding → polarities asserted. "denies chest pain" → {"chest pain": {False}}.
    Scoped negation (below). A set, so a mixed statement keeps both (L33)."""

def extract_diagnoses(text: str) -> dict[str, set[Certainty]]:
    """v1.3 (D12): diagnosis → certainties asserted. "r/o PE" →
    {"pulmonary embolism": {"rule_out"}} (L134). Lexicon is corpus-driven (MVP), like
    FINDINGS."""

def extract_excluded_diagnoses(text: str) -> set[str]:
    """v1.3.28 (L140): the diagnoses text excludes, the negated mentions extract_diagnoses
    drops. "PE ruled out" → {"pulmonary embolism"}."""

def content_tokens(text: str) -> list[str]:
    """L160: text's words, numbers included, less FUNCTION_WORDS, in order. "The pain,
    500 mg" → ["pain", "500", "mg"]. What quote_informativeness counts (§8.4)."""
```

Callers add the claim linkage themselves. These two helpers live in `evals/` — they touch
spine types, and `clinical/` imports nothing from the spine:

```python
def drug_mentions(note: SOAPNote) -> list[tuple[str, tuple[int, ...]]]:   # (drug, claim ids)
    return [(d, (c.id,)) for c in note.claims for d in extract_drugs(c.text)]

def span_text(claim: ClinicalClaim, raw_text: str) -> str | None:        # v1.3 (L35)
    return None if claim.source_span is None else raw_text[slice(*claim.source_span)]
```

**The negation scope rule (v1.3, L31).** v1.2 had `NEGATION_CUES: set[str]` and no rule for
what a cue governs. "Cue anywhere in the string" gets all of these wrong:

```
"no fever, but reports chest pain"   → chest pain negated          ✗ terminator ignored
"no increase in pain"                → pain negated                ✗ pseudo-negation
"chest pain: denied"                 → chest pain positive         ✗ post-negation missed
"know" / "nose"                      → contains the cue "no"        ✗ substring match
```

The MVP rule is NegEx-shaped and deterministic: **token-level** cue matching; a
**pre-negation** cue negates findings within `NEGATION_WINDOW` words after it; a
**post-negation** cue negates the finding immediately before it, or the list it ends when
the list opens its clause (L193); **terminators** ("but",
"however", "although", ";", ".", a line break; `TERMINATORS` lists the rest, L147) close the
window; **pseudo-negations** ("no increase", "no change", "not only") are matched first and
suppress the cue. The same window machinery serves the order cues (L124, L125), allergy
context (L128), and certainty (L135): one scope engine for every cue class.

**The scope rule, made exact (L121).** The engine's token is a word (a run of letters and
digits; a decimal number is one word, so "38.5" ends no sentence), one punctuation mark, or
a line break, read from the casefolded text; a carriage return, alone or before a line feed,
reads as one line break (L128), and an underscore, like whitespace, only separates words
(L123). A curly single quote reads as the apostrophe, as §6.2's normalizer reads it (L170),
so "d/c’d" matches the table's "d/c'd". Lexicon phrases are tokenized the same way, so "d/c"
matches as three tokens and "SI/HI" is two words. Phrases match left to right, longest
first: a pseudo-negation, which contains its cue, is matched in the cue's place, and
"negative for" wins over "negative". The window counts words only: punctuation spends none
of it, and a finding is in scope when its first word is among the `NEGATION_WINDOW` words
after the cue. "Immediately before" skips any mark but a comma or a terminator (L122):
"chest pain: denied" negates chest pain, and "endorses chest pain, denied fever" negates the
fever. A phrase in both cue classes ("denied") is a post-cue when a finding is immediately
before it and a pre-cue otherwise, so "pt denied chest pain" and "chest pain denied, fever"
both read right.

**A post-cue reaches a list that opens its clause (L193).** A negation, stop, or start
post-cue reaches back over the coordinated run before it — mentions joined by commas,
"and", "or", "/", or "&", ending at the mention adjacent to the cue — when the run opens
its clause: it begins at the text's start, or after ".", ";", a line break, or a header's
colon (up to three words and a colon at a line's start or after a period, the header L128
reads). Otherwise the cue reaches the adjacent mention only. So "Fever, chills, and nausea
denied." and "ROS: fever, chills, and nausea denied" negate all three, while "Continue
lisinopril, metformin held" stops only the metformin and "Reports fever, chills denied"
negates only the chills: a terminator word ("reports", "endorses", "positive for",
"continue") closes a window but opens no clause, so a list after it reads adjacent-only
(§8.8). Prototyped Oct 12: a run with no clause condition over-reached on exactly those
two, and on the "ROS:" line v1.3's rule fires two false CRITICALs on faithful notes, split
or merged, and misses a flipped claim; L193 clears both and catches the flip. Certainty
post-cues stay adjacent. Allergy post-cues keep L128's reach, which asks for no clause
start: there a miss is a silent CRITICAL and an over-reach a loud one. The run and the
clause starts are grammar, so they live in `extract.py` beside its join set (`_LIST_REACH`,
`_CLAUSE_STARTS`, `_JOINS`).

**Finding aliases (L173).** `FINDING_ALIASES` maps a finding's other names onto `FINDINGS`,
each read at its cue's polarity as the finding is, and one name may stand for two ("N/V" is
nausea and vomiting). `ABSENT_FINDINGS` maps a word that states its finding absent
("afebrile" → fever), and the word reads absent under any cue: read as negated, it would
flip inside every negated list ("denies chills, afebrile"). A double negation is an alias,
matched whole ahead of the word ("not afebrile" is a fever); one the tables don't spell is
§8.8's. Each alias and word names a `FINDINGS` entry, which a test holds: a name outside it
is a polarity no claim can share (L139).

**Medication cues (L124, L125).** A drug mention sees three cue classes at once: negation
(the `FINDING_NEG_*` tables, shared with findings), stop, and start. Each cue carries its
class, and the most recent pre-cue's window governs: a new pre-cue of any class replaces an
open window, so "stop metformin and start lisinopril" stops one drug and starts the other.
A post-cue's class labels the mention immediately before it, or the list it ends when the
list opens its clause (L193). A negated mention is "stopped": `MedStatus` has two values,
and "not on apixaban" asserts the drug isn't taken, which keeps a flip to "Continue
apixaban" visible to `med_status_consistency`. `extract_drugs` keeps each drug with an
active mention; `new_prescriptions` keeps each drug a start cue governs. A stop is most
often charted after its drug ("lisinopril discontinued"), so `MED_STOP_POST` and
`MED_START_POST` hold the post-cue forms, as `FINDING_NEG_POST` does for findings.
Narrative past tense ("started", "prescribed") counts as a start: read as nothing, it would
let a stop's window run on over the next drug ("held metformin, started apixaban"), and the
cost, an old start ("metformin was started in 2019") in `new_prescriptions`, lands on a
WARNING. Refused and continued orders ("do not stop", "don't stop", "continue") are lexicon
entries, not a rule (L172). A restart or a resumption is a start (L169), so "resume" is a
start cue; as a pre-cue it replaces a stop's open window, the job it did as a terminator. A
refused start, restart, or resumption, written out or contracted ("do not restart", "don't
resume"), is a stop (L167). A refusal the tables don't spell, and a cue the rule can't
reach, are §8.8's (L168).

**Allergy context (L128, L129).** Allergy is a fourth cue class a drug mention sees:
`ALLERGY_CUES` before the allergen and `ALLERGY_POST` after it. A mention it governs is an
allergen, which `extract_allergies` collects and the drug extractors drop. It reaches
further than the other classes, in two ways a window can't. An allergy cue ending in a colon
at a line's start ("Allergies:") opens a section, which runs to a blank line, or to the next
header (up to three words and a colon, the first naming no allergen) at a line's start or
after a period. Inside it, a mention no other cue governs is an allergen and a terminator
doesn't end the section, while every other cue still governs its own window: "Start
amoxicillin" under the header is a start, never an allergen. An allergy post-cue reaches
back over the list before it, the mentions joined by commas, "and", "or", or a mark such as
"/", ending at the one adjacent to the cue, and takes each that no other cue governs: "PCN
and sulfa allergies" names both. Where these fail, they fail loud, since `allergy_preserved`
fires: a bare medication line under a header reads as an allergen, and a list can reach back
into a medication ("takes lisinopril, sulfa allergy"). Allergen names follow L126's rule.
`ALLERGY_ALIASES` holds the classes and D10's statements, a canonical name mapping to
itself, and drug allergens come through `GENERIC_DRUGS` and `BRAND_TO_GENERIC`. "nkda" and
"nka" need no cue unless negated, "Allergies: none" is NKA, and a denied allergy ("not
allergic to") is a negation cue. A CRLF line break is one token, which sections need.

**Doses (L131, L133).** `lexicons.py` holds what a dose needs to know as data: `DOSE_UNITS`
and `DOSE_FREQUENCIES` map each charted form to its canonical one ("mcg" -> "μg", "t.i.d."
-> "tid"), and `extract.py` owns the grammar, so the lexicon still imports nothing and every
unit and frequency carries its own sign-off. A dose is a number and a unit ("500 mg",
"500mg", "1,000mg") after a listed drug, in that drug's sentence. It belongs to the most
recent drug before it, whatever that mention's status, and a titration keeps both doses. It
takes the first frequency charted after its unit, before the next dose, drug, or terminator,
else none; a prn yields to an interval in that reach, so "q6h prn" and "prn q6h" both read
q6h. Units are canonical but never converted ("1 g" stays grams). Neither number of a range
is a dose, so a range changed to a fixed dose still differs from its source: a hyphen joins
a range whether or not its numbers carry units ("5-10 mg", "5mg-10mg"), and "to" joins one
only after a number without a unit ("5 to 10 mg"), since "from 500 mg to 1000 mg" is a
titration. A dose before its drug ("500 mg of amoxicillin") or in the next sentence reads as
nothing, the accepted costs. `dose_consistency` reads 1 g as 1000 mg through `DOSE_MASS_UG`,
and a dose without a frequency as matching one with (§8.4, L141).

**Diagnoses and certainty (L134, L135, L140).** `diagnosis_in_quote` compares keys, so a
diagnosis needs every name it is charted by, as a drug does (L126): `DIAGNOSES` holds the
canonical names, and `DIAGNOSIS_ALIASES` maps the others onto them ("PE" -> "pulmonary
embolism"). Certainty is a cue class a diagnosis sees beside negation: `CERTAINTY_CUES`
before it and `CERTAINTY_POST` after it, each cue naming the `Certainty` it asserts, and a
diagnosis no cue governs is definite. A negated diagnosis isn't asserted, so "PE ruled out"
(excluded) and "r/o PE" (to be excluded) read apart; `extract_excluded_diagnoses` reads the
excluded ones (L140). "Cannot rule out" and "not ruled out" are possible. A differential cue
("vs") governs both its sides: the diagnosis immediately before it, unless another cue
governs that one, and the window after it, so "PNA vs PE" reads both as possible. "PE" also
charts the physical exam, so "PE: lungs clear" reads a pulmonary embolism, an accepted cost.

**Classes and side chains (L148, L149, L150).** D9's ladder reads three tables, and
`contraindication` in `evals/checks.py` walks it. `DRUG_CLASS` classes the vocabulary:
amoxicillin, amoxicillin-clavulanate, and ampicillin are penicillins, cephalexin a
cephalosporin, azithromycin a macrolide, ibuprofen an NSAID, and lisinopril an ACE
inhibitor; acetaminophen, apixaban, and metformin have no entry, since no class allergy
covers them. A class name is its own class, so a class allergy ("PCN allergy") reaches its
drugs at rung 2, and no listed drug is named like a class. `R1_GROUP` puts ampicillin and
cephalexin in one group and amoxicillin and amoxicillin-clavulanate in another, which no
listed cephalosporin shares; a drug without an entry shares its side chain with no drug of
another class. Ampicillin joins the vocabulary so the identical-side-chain rung has a drug
on each side (L148). `CROSS_REACTIVITY` holds penicillin to cephalosporin and cephalosporin
to penicillin, each a WARNING (D14). A rung-4 finding says why: "R1 side chain not shared"
for an allergy to a specific drug, and D14's "specify the penicillin to refine the risk" for
a class allergy, which names no side chain.

**`clinical/lexicons.py` — the shape (v1.3):**

```python
# imports NOTHING. Severities are plain strings ("critical" / "warning") so clinical/ never
# imports the spine; evals converts with Severity(value). (v1.3, L65)

GENERIC_DRUGS:     set[str]          # the drug vocabulary (L126): "apixaban", "lisinopril", ...
BRAND_TO_GENERIC:  dict[str, str]    # "tylenol" -> "acetaminophen", "augmentin" -> "amoxicillin-clavulanate"
ALLERGY_ALIASES:   dict[str, str]    # "pcn" -> "penicillin", "sulfa drugs" -> "sulfa",
                                     # "no known drug allergies" -> "nkda", "nka" -> "nka"     (D10)
ALLERGY_CUES:      set[str]          # "allergic to", "allergy to", "allergies:", "reaction to"
ALLERGY_POST:      set[str]          # "allergy", "allergies": after the allergen (L128)
FINDING_NEG_PRE:   set[str]          # "denies", "no", "without", "negative for"
FINDING_NEG_POST:  set[str]          # "denied", "absent", "negative"
PSEUDO_NEGATIONS:  set[str]          # "no increase", "no change", "not only"
TERMINATORS:       set[str]          # "but", "however", ";", ".", a line break, ... (L147)
NEGATION_WINDOW:   int               # words a pre-cue governs — linguistic knowledge, so it lives here
MED_STOP_CUES:     set[str]          # "discontinue", "d/c", "stop", "held", "hold"    (L31: split out)
MED_STOP_POST:     set[str]          # "discontinued", "held": after the drug (L125)
MED_START_CUES:    set[str]          # "start", "restart", "resume", "prescribe", "rx" (L41, L169)
MED_START_POST:    set[str]          # "started", "prescribed": after the drug (L125)
CERTAINTY_CUES:    dict[str, str]    # "likely" -> "probable", "r/o" -> "rule_out", "possible" -> "possible"
CERTAINTY_POST:    dict[str, str]    # "likely" -> "probable": after the diagnosis (L135)
DIFFERENTIAL_CUES: dict[str, str]    # "vs" -> "possible": both its sides (L135)
DRUG_CLASS:        dict[str, str]    # "amoxicillin" -> "penicillin", "cephalexin" -> "cephalosporin",
                                     # "ibuprofen" -> "nsaid". v1.3 (L67): ONE direction. v1.2 kept
                                     # ALLERGY_CLASSES (class → members) AND DRUG_CLASSES (member →
                                     # class) — two encodings of one relation, free to disagree.
R1_GROUP:          dict[str, str]    # D9: generic -> R1 side-chain group, for drugs whose side chain
                                     # is shared ACROSS classes (ampicillin with cephalexin/cefaclor;
                                     # amoxicillin with cefadroxil/cefprozil). Each entry commented
                                     # with its rationale.
CROSS_REACTIVITY:  dict[tuple[str, str], str]
                                     # (allergen class, drug class) -> severity when no R1 side chain
                                     # is shared (L150, L155): ("penicillin", "cephalosporin") -> "warning"
DOSE_UNITS:        dict[str, str]    # "mcg" -> "μg", "milligrams" -> "mg": the canonical unit (L131)
DOSE_FREQUENCIES:  dict[str, str]    # "t.i.d." -> "tid", "twice daily" -> "bid" (L131)
DOSE_MASS_UG:      dict[str, int]    # "g" -> 1_000_000: a mass unit's size in μg; ml, units none (L141)
FINDINGS:          set[str]          # "chest pain", "fever", "sob", ... (MVP: what the corpus needs)
FINDING_ALIASES:   dict[str, tuple[str, ...]]  # "n/v" -> ("nausea", "vomiting"): other names (L173)
ABSENT_FINDINGS:   dict[str, str]    # "afebrile" -> "fever": absent under any cue (L173)
DIAGNOSES:         set[str]          # D12: corpus-driven, like FINDINGS; canonical names (L134)
DIAGNOSIS_ALIASES: dict[str, str]    # "pe" -> "pulmonary embolism": every other charted name (L134)
FUNCTION_WORDS:    set[str]          # "the", "of", "and", "is": words content_tokens drops (L160)
```

**DECISION D9 (v1.3, vetoable) — cross-reactivity is keyed on the R1 side chain.** The
evidence v1.2 cited (~1–2% overall penicillin → cephalosporin cross-reactivity, concentrated
in shared R1 side chains, not the old "10%") is side-chain-level; v1.2's table was
class-level, so cephalexin on an ampicillin allergy (identical R1) got the same WARNING as
ceftriaxone (dissimilar). `contraindication(allergen, drug)` in `evals/checks.py` resolves
one pair by walking a ladder, first match wins:

```
1. same drug                                        → CRITICAL
2. same class (DRUG_CLASS; a class key is its own)  → CRITICAL
3. allergen is a specific drug AND its R1_GROUP
   matches the drug's across classes                → CRITICAL   (identical side chain)
4. CROSS_REACTIVITY[(class(allergen), class(drug))] → the table's call (WARNING for PCN → ceph)
5. otherwise                                        → no finding
```

**DECISION D14 (v1.3, vetoable) — the unspecified allergy and the reaction type.** "PCN
allergy" names no specific penicillin, so no R1 group resolves: penicillins are CRITICAL
(rung 2), every cephalosporin is WARNING (rung 4), and the finding's detail says *"specify
the penicillin to refine the risk."* This is the most common way allergies are documented;
flagging every cephalosporin CRITICAL would teach clinicians to ignore red, and flagging
none would go silent. **Reaction type** (anaphylaxis vs rash) changes the clinical calculus
and is not extracted in v1 — a stated limitation (§8.8), backlogged (§15). Carbapenems and
aztreonam enter the lexicon only if a corpus case needs them. *These are defaults drafted
from the modern evidence; they get Cal's clinical sign-off when `lexicons.py` is authored,
with the rationale in a comment above each entry (L120).*

All lexicon entries are **generic-only** post-normalization: every extractor maps
brand→generic first, so a class entry containing a brand name is dead weight at best and a
missed match at worst.

**The drug vocabulary (L126).** `GENERIC_DRUGS` lists every drug the extractors know.
`BRAND_TO_GENERIC` maps every other name a listed drug is charted by onto it: brands,
abbreviations, and spellings ("apap", "amox/clav"), and a test holds its values in
`GENERIC_DRUGS`. A listed drug needs all its common names: when the source writes a name the
table lacks and the claim writes the generic, `drug_in_quote` fires on a faithful claim.
`DRUG_CLASS` keys are drawn from `GENERIC_DRUGS` too. The vocabulary is closed in the MVP
(L171): a drug joins it with the case that exercises it, carrying its common names and its
`DRUG_CLASS` entry (L149). Breadth is v2's (RxNorm, below).

**The sign-off (L120).** Each table in `lexicons.py`, and `NEGATION_WINDOW`, is headed by a
`# Clinical sign-off: <name>, <date>.` line that covers the entries beneath it, and each entry
carries its rationale in a comment on the line above it. When a table gains or changes an
entry, the line's date moves: it attests the table as it stands, and git history keeps each
entry's own. A test holds the form.

**MVP scope:** a small hand-curated lexicon + the scope engine + a dose grammar over the
lexicon's units and frequencies (L131) + findings and diagnosis lists covering exactly the
traps in *my* corpus.
**v2:** medspaCy / NegEx / RxNorm for robust, ontology-derived extraction.

---

## 8. Layer 4 — Evals ⭐ THE MOAT

**Job:** `await run_checks(note, raw_text, case=None, *, mode, config, judge=None)` →
`EvalReport`.
Take a finished, *grounded* note and answer one question — **is this clinically safe?**
— as a verdict you can run. This is the layer a strong generalist cannot build, because
they don't know what to check for. (Async because the judge is a network call — §8.2. The domain holds a
`Judge` protocol, never an Anthropic client — v1.3, L17.)

### 8.1 Two species of check (the keystone distinction)

- **Reference-free (intrinsic):** verifiable from `(note, raw_text)` alone — *"every
  medication in the summary appears in the source."* Can run **in production**, on real
  encounters, because real inputs have no answer key.
- **Reference-based (extrinsic):** needs a known-correct expectation — *"the penicillin
  allergy was preserved."* Runs **only** in CI, against labeled cases.

**The deep asymmetry:** the most dangerous error — **omission** — is fundamentally
reference-based. You cannot detect a *dropped* allergy by inspecting the output; the
dropped thing isn't there to inspect. Absence requires knowing what *should* have existed.

**Refinement (the precise axis):** the real test isn't "needs a reference: yes/no," it's
**how much you trust the derivation**. A contraindication check reads an *explicit* allergy
and an *explicit* prescription — high-confidence extraction — so it qualifies as
reference-free and **runs live on real patients.** Comprehensive omission detection fails
the test because it needs a *trustworthy exhaustive enumeration* of everything that should
have been captured, and automating that exhaustively is the fallible step — so in CI we
replace the fallible extraction with a hand-labeled `must_preserve` list.

**The trust axis is a placement rule (v1.3).** Where a check runs is decided by
*derivation trust × severity*: a high-trust derivation can run live at CRITICAL
(`allergy_preserved`); a lower-trust one either narrows until it is trustworthy
(`new_prescriptions` → `new_prescription_preserved`, WARNING) or moves to CI behind a hand
label (`must_preserve`). The worked counterexample — why `medication_preserved` never runs
live — is in §8.4.

### 8.2 Match the tool to the check

```
deterministic     set/string ops      fast · free · reproducible · brittle to synonyms
lexicon-assisted  RxNorm / NegEx       robust to medical variation · still deterministic
LLM-as-judge      a 2nd model call     handles semantics · stochastic, fallible
```

**The senior move is not "use the most powerful tool everywhere."** Structural checks get
deterministic code; semantic checks get the LLM judge — **and the judge's verdict is never
the sole gate on a CRITICAL.** Being able to say *"here's where I used LLM-as-judge, and
here's exactly why I didn't trust it for the critical path"* is more senior than the
technique itself.

**The judge, scoped (v1.1 D2) and reframed (v1.3, DECISION D8, vetoable).** Exactly one
judge check ships, in build phase 2c: `text_entailment_judge`. v1.2's judge asked whether
each Assessment claim was *clinically supported* by its cited span — its showcase was
"BP 190/110" → "hypertensive urgency," sound inference that grounds nowhere textually. D7
made that showcase a *violation*: the model may not infer an assessment. So the question
flips from "is this inference supported?" to **"is this claim's text entailed by its source
span?"** — asked of every grounded claim, in every section. That is the general form of the
claim-local consistency family (§8.4): the deterministic checks answer it for the entities
their lexicons know; the judge answers it for everything else — the degenerate quote (D15),
the invented assessment (D7, D12), drift no lexicon names. WARNING tier, reference-free,
never a CRITICAL gate (invariant 7). This is the concrete artifact behind the interview line
above — the line needs a `git blame`-able referent.

**The judge is a network call, and the domain doesn't speak Anthropic (v1.2; v1.3, L17).**
`run_checks` is async because one member awaits. v1.3 changes *what* it awaits: evals
declare a protocol —

```python
# evals/judge.py — a DOMAIN interface
class Judge(Protocol):
    usage: TokenUsage
    async def entailment(self, pairs: Sequence[tuple[str, str]]) -> list[bool]: ...
```

— and `judge_client.py` (edge) implements it over the Anthropic API: one batched call
carrying every `(text, span)` pair and returning one verdict per pair (L40 — a 20-claim note
is one call, not twenty), its own call config pinned per invariant 3 (L182; its fields are
2c's), its own `settings.judge_timeout_s`, shorter than the summarize timeout (L54). A
judge is constructed per request (and per corpus case), so its `usage` belongs to exactly
one report and lands in `EvalReport.judge_usage` (L7). Whether the judge runs is a
*parameter* — `run_checks(..., judge=None)` skips it — not a global read inside the domain
(L49); `settings.judge_enabled` is read only at the edge that decides whether to construct
one. Tests pass a fake `Judge` with canned verdicts.

**Negation** is the cleanest illustration of why generic code fails: a naive `"chest pain"
in summary` matches both "denies chest pain" and "reports chest pain" — it cannot tell a
faithful note from a catastrophic flip. You need negation-aware comparison because you've
read ten thousand notes and know it's a named failure mode.

### 8.3 Safety extraction scans the WHOLE note (never trusts the section)

The section is the model's *judgment call* and is for **display only**. If the model
misfiles "start amoxicillin" into Assessment instead of Plan, a Plan-only check reads an
empty Plan and the contraindication sails through. **Safety-critical extraction iterates
every claim** — which, on the v1.1 flat spine, is literally just `note.claims`. The safe
path and the easy path are now the same path. A misfiled drug is still a prescribed drug.
Invariant 5 protects checks against *misfiling*; its sibling for *omission* is D17 (§8.4).

### 8.4 The showpiece check (the moat, executing) + the roster

```python
@register_check(name="allergy_contraindication", severity=Severity.CRITICAL, origin="source")
def check_allergy_contraindication(note: SOAPNote, raw_text: str,
                                   case: EvalCase | None = None, *,
                                   config: ChecksConfig) -> list[Finding]:   # L190
    """Omission behavior (D17):
    - allergy omitted from the note  → still read from raw_text.
    - NEW drug omitted from the note → still read via new_prescriptions(raw_text) (L51);
      the finding is note-level (claim_ids=()) → the banner.
    - CONTINUED home med omitted     → not seen live. Declared CI-only gap, covered by
      must_preserve(kind="medication")."""
    allergy_claim: dict[str, int] = {a: c.id for c in note.claims
                                     for a in extract_allergies(c.text)}
    allergens = (extract_allergies(raw_text) | allergy_claim.keys()) - {"nkda", "nka"}

    drugs = drug_mentions(note)                                        # WHOLE note (inv. 5)
    in_note = {d for d, _ in drugs}
    drugs += [(d, ()) for d in sorted(new_prescriptions(raw_text) - in_note)]   # L51

    findings: list[Finding] = []
    for drug, drug_ids in drugs:
        for allergen in sorted(allergens):
            hit = contraindication(allergen, drug)                     # the D9/D14 ladder:
            if hit is None:                                            #   pure, unit-tested
                continue                                               #   rung by rung
            severity, why = hit
            allergy_ids = (allergy_claim[allergen],) if allergen in allergy_claim else ()
            ids = drug_ids + allergy_ids if drug_ids else ()           # L151: no drug claim →
            findings.append(Finding(                                   #   the banner; else L37,
                detail=f"{allergen} allergy on record; {drug}: {why}",  #   the allergy claim too
                claim_ids=ids,
                severity=severity,                                     # ≤ CRITICAL (L38)
            ))
    return findings                                                    # [] = passed
```

The decorator (§8.7) turns `[]` into one `passed=True` result and a non-empty list into one
`passed=False` result per finding, each stamped with `check` and `severity`. The check
function never spells its own name.

Catching this requires *knowing amoxicillin is a penicillin* — and, after D9, knowing that
cephalexin shares ampicillin's side chain while ceftriaxone shares nobody's, and that the
~10% cross-reactivity figure everyone memorized was an artifact of manufacturing-era
contamination. That knowledge isn't on Stack Overflow. The fixtures that test it **are** my
background, executing.

**What v1.3 fixed in the showpiece.** Two holes, both CRITICAL:

```
L30  "allergic to amoxicillin" + amoxicillin prescribed
     v1.2: ALLERGY_CLASSES.get("amoxicillin") → None → no finding. Allergic to the exact
           drug prescribed, and the check passed. Same for "PCN", "Augmentin", ampicillin.
     v1.3: allergens normalize like drugs; rung 1 (same drug) and rung 2 (same class) fire.

L51  the model drops "start amoxicillin" from the note (omit-when-uncertain, misapplied)
     v1.2: allergies read from raw ∪ note, drugs from the note ONLY → the loop never sees it.
     v1.3: drugs = note ∪ new_prescriptions(raw). The model's omission can no longer remove
           the danger from both the note and the check that would catch it.
```

**The roster (v1.3).** Every check the corpus can score, with what it trusts:

| check | severity | ref? | compares | catches |
|---|---|---|---|---|
| `allergy_contraindication` | CRITICAL (rungs may lower) | no | allergies(raw ∪ note) vs drugs(note) ∪ new_prescriptions(raw) | prescribing into an allergy |
| `allergy_preserved` | CRITICAL; NKDA, NKA → WARNING (D10, L144) | **no** | allergies(raw) − allergies(note) | **a dropped allergy, live** |
| `hallucinated_medication` | CRITICAL | no | `UNSUPPORTED` flag + named(text) (L136) | a drug in a claim that grounds nowhere |
| `drug_in_quote` | CRITICAL | no | named(text) ⊆ named(span) (L136) | a drug the source span doesn't say |
| `med_status_consistency` | CRITICAL | no | status(text) ⊆ status(span), for drugs in both (D13) | "continue" ↔ "discontinue" |
| `negation_consistency` | CRITICAL | no | polarity(text) ⊆ polarity(span), for findings in both (L139) | "denies" → "reports" |
| `diagnosis_in_quote` | CRITICAL; downgrade or reopened exclusion → WARNING | no | diagnoses(text) ⊆ diagnoses(span), certainty never stronger (D12); exclusions too (L140) | an invented, upgraded, or wrongly excluded assessment |
| `dose_consistency` | WARNING | no | doses(text) ⊆ doses(span), parsed, for drugs both name; mass in μg, a missing frequency matches any (L141) | 50 mg → 500 mg |
| `new_prescription_preserved` | WARNING | no | new_prescriptions(raw) − named(note) (L41, L156) | a started drug the note dropped |
| `quote_informativeness` | WARNING | no | content_tokens(span) ≥ `config.min_quote_content_tokens`, or NKDA or NKA, or absence words alone (D15, L158, L159, L174) | degenerate quotes |
| `empty_note_on_clinical_input` | WARNING | no | `claims == ()` while raw names an entity: named(raw) ∪ allergies(raw) ∪ findings(raw) ∪ diagnoses(raw), asserted or excluded (L55, L164) | total omission reading green |
| `text_entailment_judge` | WARNING | no (LLM) | text entailed by span, one batched call (D8) | drift no lexicon names |
| `must_preserve` | CRITICAL; a dose, NKDA, NKA, downgrade, or reopened exclusion → WARNING (L217) | **yes** | each label's reading vs the note's, by its kind's extractor (L214–L216) | a labeled omission, status flip, or certainty drift |
| `must_not_add` | CRITICAL | **yes** | each label vs the note's positive readings (L36, L214) | a labeled invention |

`span` is `raw_text[claim.source_span]` (§6.4, L35). The consistency checks skip claims
whose span is `None` — those belong to grounding's red badge and `hallucinated_medication`.
`named` is every drug a string names, whatever status it asserts, negated included, and
never an allergen: `extract_med_status`'s keys, as `named_drugs` in `evals/checks.py`
(L136). `drugs` is the active ones alone, `extract_drugs`'s set, as
`allergy_contraindication`'s row reads them (L163).

Four things to read off the table:

1. **`allergy_preserved` is reference-free.** "Allergic to X" / "NKDA" is about the most
   explicit language in a clinical note, and the prompt says *never omit an allergy* — so
   the prompt and the check agree, and the single most dangerous omission gets a live check.
   A dropped NKDA or NKA is a WARNING (D10, L144): undocumented status prompts a re-ask;
   it is not a missed allergy. The prompt names both (L191), so the two agree on absence
   too.
2. **The claim-local consistency family compares against the span (L35).** v1.2 compared
   `claim.text` to the model's `source_quote`. At Tier 3 those differ by definition:

   ```
   span:  "…tolerating PO well, will start azithromycin 500 mg daily…"
   quote: "…tolerating PO well, will start amoxicillin 500 mg daily…"   long shared context,
   text:  "Start amoxicillin 500 mg daily"                                 digits intact → PARAPHRASED
   v1.2 drug_in_quote: {amox} ⊆ drugs(QUOTE) = {amox}      → passes. A fabricated drug, yellow.
   v1.3 drug_in_quote: {amox} ⊆ drugs(SPAN)  = {azithro}   → FIRES.
   ```
3. **Presence and status are partitioned (D13).** `drug_in_quote` owns *is the drug in the
   source?*; `med_status_consistency` owns *active vs stopped, for a drug in both*. The
   dangerous direction — "discontinue apixaban" written for a continued apixaban — is
   invisible to a subset check on active drugs (∅ ⊆ anything); the status check catches it.
   One error, one finding.
   Presence reads every named drug, not only the active ones (L136): read as active drugs, a
   swapped stop order ("Discontinue metformin" for the span's "discontinue lisinopril")
   compares ∅ ⊆ ∅ and passes every check. Both checks read `extract_med_status`'s keys, so
   they partition one key set: a negated mention is named, so "Continue apixaban" against
   "not on apixaban" is status's finding alone.
4. **`must_preserve` / `must_not_add` read labels with the live primitives (L214).** A
   label's `text` is read by its kind's extractor and states one reading, which is what the
   label asserts: `PCN allergy` is penicillin; `metformin` is metformin active and
   `metformin held` is metformin stopped; `metformin 500 mg BID` is one dose;
   `denies chest pain` is chest pain absent; `r/o pulmonary embolism` is a rule-out and
   `pulmonary embolism ruled out` an exclusion. The note's reading is every claim's text,
   whatever its section (invariant 5). A `must_preserve` item holds when the note keeps its
   reading: the allergen; the drug at its status (L215); the dose, as `dose_consistency`
   matches one (L141); the finding at its polarity (L36); the diagnosis as below (L216). A
   `must_not_add` item fires on a claim that reads it positively: the drug active, the
   finding present, the diagnosis asserted at any certainty, an invented differential
   included (D7). A negated, stopped, or excluded mention adds nothing, so a faithful
   "denies chest pain" is not an invented chest pain (L36).

**A labeled diagnosis is compared note-wide (L216).** A note records a course ("r/o PE in
the ED", "PE confirmed on CTA"), so `must_preserve` reads the whole note's strongest
certainty against the label's, not one claim against its span as `diagnosis_in_quote` does.
Against an asserted label, a note that doesn't name the diagnosis is CRITICAL, and so is one
that excludes it (an exclusion the source doesn't make, L140); a stronger certainty is an
upgrade, CRITICAL, and a weaker one a downgrade, WARNING. Against an exclusion label, a note
asserting the diagnosis definite or probable, or never naming it, is CRITICAL, and one
reopening it as possible or rule-out without the exclusion is a WARNING; a rule-out that
ends in the exclusion keeps it.

**The reference findings (L217, L218).** `must_preserve` is CRITICAL, and lowers a finding
to WARNING for a dose, a dropped NKDA or NKA (D10, L144), a labeled downgrade, or a reopened
exclusion; `must_not_add` is CRITICAL. A `must_preserve` finding names no claim, since what
it misses is in none; a `must_not_add` finding names each claim that adds the item. Both
raise when `case` is `None`, so a call without an answer key errors (invariant 12) rather
than passing over nothing.

**Diagnoses are compared as readings (D12, L140).** A string's reading of a diagnosis is the
certainties it asserts and whether it excludes it ("PE ruled out", "no pneumonia"). A
diagnosis the span doesn't name is invented, CRITICAL. Certainty compares strongest to
strongest: a claim's stronger than its span's is D12's upgrade, CRITICAL; a certainty the
span lacks, and none stronger, is its downgrade, WARNING. An exclusion the span doesn't make
is CRITICAL, whether the span rules the diagnosis out (premature closure), asserts it (a
flip), or never names it (an inferred exclusion, D7). A claim asserting a diagnosis its span
excludes is CRITICAL as definite or probable; as possible or rule-out it reopens the
question, a WARNING like the downgrade.

**Why `medication_preserved` is NOT on the roster (§8.1's trust axis, applied).**
`extract_drugs(raw) − extract_drugs(note)` looks like `allergy_preserved`'s twin. It isn't:
raw encounters are full of drug names a faithful note may omit — family history, failed
past therapy, counseling a patient declined, contingencies, patient questions, an 18-item
pasted home-med list — and the prompt *sanctions* omitting uncertain content. A live
CRITICAL would fire on most correct notes, clinicians would learn that red means nothing,
and the real allergy red would be ignored with it. One noisy check devalues the whole
channel. Medication omission therefore stays in CI (`must_preserve`, `kind="medication"`);
the only live slice is the narrow, high-trust one — `new_prescriptions` — at WARNING.

**DECISION D17 (v1.3, vetoable) — the omission law.** Invariant 5 protects checks against
*misfiling*. Its sibling protects them against *omission*: **every CRITICAL check documents,
per input, what happens when the model omits it; an omission that silences the check must be
covered by another live check or declared a CI-only gap.** L51 is the bug this law would
have caught. The contract, per CRITICAL check:

| check | if the model omits… | then |
|---|---|---|
| `allergy_contraindication` | the allergy | read from raw — still fires |
| | a new drug | read via `new_prescriptions(raw)` — still fires, banner |
| | a continued home med | **CI-only gap** → `must_preserve(kind="medication")` |
| `allergy_preserved` | the allergy | that omission is its subject — fires |
| consistency family, `hallucinated_medication` | the claim | nothing left to contradict; the omission belongs to `allergy_preserved` / `new_prescription_preserved` live and `must_preserve` in CI |
| `must_preserve` / `must_not_add` | — | omission is their subject (CI) |

Each row is a docstring on the check and a free-tier test (§11).

### 8.5 The synthetic corpus (`evals/cases/`) — three species, two ways to run them

Each case is a fixture carrying its own answer key (`EvalCase`, §4.2).

**Three species** (v1.1; an explicit field in v1.3, L9):

- **Fidelity traps** — test the *model*. `must_preserve` (the allergy must survive),
  `must_not_add` (no invented meds). Pass when nothing CRITICAL fires. `expected_flags: []`.
- **Detection traps** — test the *safety layer*. Pass when the expected flag fires. The best
  single fixture in the repo: a penicillin-allergic patient prescribed amoxicillin
  (`expected_flags: ["allergy_contraindication"]`).
- **Clean controls** — `trap: None`, `expected_flags: []`. Any CRITICAL that fires is a false
  positive and fails the case — a check that flags a perfect note is as broken as one that
  misses a fabrication. An injected control fires no check at any severity (L162): its draft
  is authored, so a WARNING on it is a false positive too, and a test holds it. The verdict
  stays CRITICAL-scoped (§8.7).

**Two ways to run a case (v1.3, L42 — the largest structural change in this revision).**
v1.2 made every case `raw_text` + an answer key, run through the real model. That works for
exactly one kind of detection trap — **the danger is in the source**: a faithful model
reproduces "PCN allergy … start amoxicillin," and the check fires. It cannot work for the
other kind — **the danger is created by the model**: a drug in the text its span doesn't
say, a flipped negation, an invented assessment. No raw text makes a good model fabricate
on cue; a good model mostly won't. v1.2's `detect_drug_not_in_quote` and
`detect_negation_flip` would have reported `missing_expected` and failed nearly every run —
the scorecard saying "the checks don't work" when the truth was "the model gave them nothing
to catch." And v1.2's coverage rule *required* such traps for every CRITICAL check.

The root cause: two questions blended into one case.

| question | stochastic? | case kind | tier |
|---|---|---|---|
| Given a draft containing mistake X, does the safety layer catch X? | **no** — ground + checks are pure functions of the draft | **injected** (`draft` set) | free, every commit |
| Does the model make X — and do the live checks catch what it actually makes? | **yes** | **model** (`draft` unset) | paid, manual |

```yaml
# evals/cases/detect_drug_not_in_quote.yaml — an INJECTED case
id: detect_drug_not_in_quote
species: detection
raw_text: |
  Pt with acute sinusitis. Will start antibiotics, f/u 1 wk.
trap: "claim text names a drug its source span does not"
draft:                                  # the planted mistake, hand-written
  claims:
    - text: "Start amoxicillin"
      section: P
      source_quote: "Will start antibiotics"
expected_flags: [drug_in_quote]
```

Tier 1 grounds, `drug_in_quote` fires, every time. The injected case proves the check; the
model cases measure the model. Design for evaluability (principle 3), applied to the eval
harness itself — and most of the moat's *proof* moves from the paid tier to the free one.

**Corpus mechanics:**

- **One YAML file per case**, `<id>.yaml`, parsed as YAML 1.2 by ruamel.yaml's safe loader
  and loaded with `EvalCase.model_validate`. A duplicate key is a load error (L118): a
  second `expected_flags:` would otherwise replace the first without a word. So is any other
  entry in `evals/cases/`, a `.yml` file or a subdirectory included, because a file the
  loader skipped would be a case that never runs; dotfiles are skipped (L119).
- **The loader validates the answer key against the registry.** Every `expected_flags` entry
  must be a registered check name — a typo is a load error, not a case that fails forever
  and gets rationalized as "the model's fault." So is a misspelled key (L103): `EvalCase`
  and its item types forbid extra fields, so a typo'd `draft:` can't turn an injected case
  into a paid model case, and a typo'd `must_preserve:` can't leave a fidelity trap with
  nothing to check.
- **Reference labels are validated at load (L219)**, for the same reason: a label no check
  can read is a case that fails forever. Each label must read as one entity with one reading
  (§8.4): a bare allergen reads nothing without its allergy context, and neither does an
  unlisted or misspelled name. `present` applies to findings and must agree with the text,
  so `present: false` on another kind, or on a finding whose text reads present, is a load
  error. The raw text must keep every `must_preserve` reading, by the check's own rule. A
  `must_not_add` label must read positively, and the raw text must not add it, which also
  rejects a drug the source names in family history: the extractors have no family-history
  context, so "Mother on apixaban" reads apixaban active (measured).
- **`corpus_version` is derived** (L204) — over the model cases a run scores: each case's
  `model_dump_json()`, sorted by id, hashed to twelve hex digits like `prompt_version`
  (L114). Injected cases are pytest's, so editing one leaves a model run's lineage alone. A
  YAML comment or a key's order doesn't move it, and an edit to a case's content does
  (measured); so does a schema change that adds a defaulted field, which errs safe.
- **Size:** ≥ 24 **model** cases, ≥ 6 per species; injected cases as many as the coverage
  rule demands (they're free).
- **The coverage rule (restated v1.3 for L42), unit-tested free:** for every registered
  CRITICAL check — ≥ 1 injected detection trap with it in `expected_flags`, and ≥ 1 injected
  clean control that exercises its extraction path without a violation. Checks with
  `origin="source"` additionally need ≥ 1 **model** detection trap (does a real model keep
  the danger visible?). A check nobody wrote a trap for is a check nobody knows works. A
  control exercises a check when the check has something to compare on it: for the
  claim-local family, an entity the check's extractor finds in both a claim's text and that
  claim's span (L138); for `hallucinated_medication`, a claim naming a drug, which
  grounding's flag then decides; for `allergy_preserved`, an allergy the raw text and a claim
  both state (L146); for `allergy_contraindication`, an allergy and a drug for the ladder to
  pair (L152). The test holds one such predicate per CRITICAL check, and fails when one is
  missing or when no CRITICAL check is registered, since a rule over no checks holds of
  nothing. The model clause joins the test in 2b, with the corpus's first model case
  (§14, L137); until then the test asserts the corpus holds none, so that case turns it red.
- **DECISION D16 (v1.3, vetoable) — one planted danger per trap.** Expected flags match on
  check *name*, so a trap can pass for the wrong reason: the check fires on an incidental
  claim while missing the planted one. Injected drafts make that nearly impossible — they
  contain only the planted claim. For model cases, the authoring rule: **no incidental
  entities that could trip the same check.** The residual gap is stated in §8.8; an `about:`
  field on expected flags is backlogged (§15).
- **A case's raw text breaks lines only where its source would (L143).** A line break is a
  terminator (§7, `TERMINATORS`: a templated line carries one statement), so it closes a
  cue's window like a period. A case wrapped to fit a width changes what it means: "start"
  at a line's end, with "azithromycin" on the next, reads no new prescription (measured). So
  a long sentence stays on one line. Review enforces it, as it does D16: a section header
  over its list is a break the source makes, and no test can tell that from a wrap.
- **Tier-3 fixtures self-check.** An injected case meant to exercise the fuzzy tier
  (`detect_paraphrase_drug_swap`) asserts in its test that the claim actually grounded
  `PARAPHRASED` — otherwise a cutoff change silently turns it into a Tier 4 case testing
  something else.

**The regression fixtures (each one a frozen bug from v1.2 or v1.3):**

| fixture | kind | species | freezes |
|---|---|---|---|
| `control_pcn_allergy_azithro` | model + injected | control | allergy context read as a prescription (v1.2) |
| `detect_drug_not_in_quote` | injected | detection | the text-vs-quote gap (v1.2) |
| `detect_negation_flip` | injected | detection | "denies" → "reports" (v1.2) |
| `fidelity_dropped_allergy` | model | fidelity | allergy omission (v1.2); its injected twin is `detect_dropped_allergy` |
| `detect_dropped_allergy` | injected | detection | allergy omission (v1.2) — expects `[allergy_preserved]`; `must_preserve` joins in 2b (L145) |
| `detect_same_drug_allergy` | model + injected | detection | L30 |
| `detect_contra_omitted_rx` | injected | detection | L51 — the draft omits the amoxicillin the raw text starts |
| `detect_shared_side_chain` | injected | detection | D9 — cephalexin on an ampicillin allergy, an identical R1 side chain v1.2 read as a WARNING (L153) |
| `detect_paraphrase_drug_swap` | injected | detection | L35 — a Tier 3 quote with a swapped drug |
| `detect_status_flip` | injected | detection | D13 |
| `detect_invented_assessment` | injected | detection | D7/D12 — "BP 190/110" → "hypertensive urgency" |
| `detect_certainty_upgrade` | injected | detection | D12 — "r/o PE" → "PE" |
| `detect_premature_exclusion` | injected | detection | L140 — "r/o PE" → "PE ruled out" |
| `detect_degenerate_quote` | injected | detection | D15 |
| `detect_empty_note` | injected | detection | L55 |
| `control_hedged_assessment` | model + injected | control | D7 — a hedged A kept hedged is clean (L23) |
| `control_empty_assessment` | model | control | D7 — no stated A, no A claims, clean (L23) |

(v1.2's `detect_vital_drift` expected no eval check — it tests grounding's numeric guard. It
moved to `tests/test_grounding.py`, L66.)

### 8.6 Severity = clinical triage (the moat hiding in one enum)

```
CRITICAL   dropped allergy · hallucinated med · contraindication (same drug, same class,
           identical R1) · negation flip · status flip · drug absent from its span ·
           invented or certainty-upgraded diagnosis · a wrong exclusion, or an excluded
           diagnosis asserted definite or probable (L140, L142) · labeled invention ·
           labeled omission (allergy / medication / finding / diagnosis) · labeled status
           flip, certainty upgrade, or wrong exclusion (L215, L216)
WARNING    dose mismatch · cross-class contraindication with a dissimilar or unknown side
           chain (D9, D14) · dropped NKDA or NKA (D10, L144) · dropped new prescription ·
           degenerate quote · empty note on clinical input · certainty downgrade · reopened
           exclusion (L140) · not entailed (judge) · labeled dropped dose, NKDA, or NKA ·
           labeled certainty downgrade or reopened exclusion (L217)
INFO       section misplacement · stylistic drift — the tier is defined, no INFO check
           ships in v1 (§15)
```

v1.3 (L49) removed v1.2's "temporal error" from WARNING: no check produced it, and a triage
list names only what exists. Triage drives everything practical — which flags interrupt the
clinician, which merely annotate, which block a deploy. A finding may *lower* its check's
severity (the contraindication rungs, NKDA and NKA, a certainty downgrade, a reopened
exclusion) and never raise it (§8.7, L38).

### 8.7 The dual-mode runner (one engine, two jobs) + the verdict + the lineage

**The registry (v1.1, sharpened v1.2 and v1.3).** Checks self-register; adding a safety check
is one decorator. The name and severity are declared once and stamped onto every result; the
registry is a dict that refuses duplicates (pytest re-imports will hand you a doubled
registry otherwise). **Every check takes `(note, raw_text, case=None, *, config)`
(L190)**, and a judged check takes `judge` beside it: one signature, so mypy checks every
registration, and no flag decides which check gets the knobs. A check reads a knob from
`config`, never from `settings` (L187).

```python
# evals/registry.py
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal

@dataclass(frozen=True)
class Finding:                        # what a check RETURNS: the facts of one violation.
    detail: str                       # Check-internal: never crosses a layer boundary, so it
    claim_ids: tuple[int, ...] = ()   #   lives here, not in schemas.py (sanctioned, §13)
    severity: Severity | None = None  # optional DOWNGRADE — enforced at stamping (v1.3, L38)

@dataclass(frozen=True)
class Check:
    name: str
    severity: Severity
    fn: Callable[..., list[Finding] | Awaitable[list[Finding]]]
    requires_reference: bool                # CI-only
    needs_judge: bool                       # v1.3: was needs_client — the domain holds a
                                            #   Judge, never a vendor client (L17)
    origin: Literal["model", "source"]      # v1.3 (L42): who creates the danger — drives
                                            #   the coverage rule (§8.5)

REGISTRY: dict[str, Check] = {}

def register_check(*, name: str, severity: Severity, requires_reference: bool = False,
                   needs_judge: bool = False, origin: Literal["model", "source"] = "model"):
    def deco(fn):
        if name in REGISTRY:
            raise RuntimeError(f"duplicate check name: {name}")
        REGISTRY[name] = Check(name, severity, fn, requires_reference, needs_judge, origin)
        return fn
    return deco

_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}

def stamp(check: Check, f: Finding) -> EvalResult:
    sev = f.severity or check.severity
    if _RANK[sev] > _RANK[check.severity]:        # v1.3 (L38): v1.2's "never an upgrade"
        raise ValueError(f"{check.name}: finding severity exceeds the check's")   # was a comment
    return EvalResult(check=check.name, severity=sev, passed=False,
                      detail=f.detail, claim_ids=f.claim_ids)
# runner.py and loader.py (L221) import checks.py, which registers the roster;
# checks.py imports only register_check + Finding. No cycle.
```

**The engine** (async; fail-closed per check; production gets the reference-free subset):

```python
async def run_checks(note: SOAPNote, raw_text: str, case: EvalCase | None = None, *,
                     mode: Literal["production", "ci"], config: ChecksConfig,   # L187
                     judge: Judge | None = None) -> EvalReport:
    selected = [c for c in REGISTRY.values()
                if (mode == "ci" or not c.requires_reference)
                and (not c.needs_judge or judge is not None)]    # v1.3 (L49): a parameter,
    claim_ids = {c.id for c in note.claims}                      #   not a global read
    results: list[EvalResult] = []
    for check in selected:
        try:
            out = (check.fn(note, raw_text, case, config=config, judge=judge)   # L190
                   if check.needs_judge else check.fn(note, raw_text, case, config=config))
            findings = await out if inspect.isawaitable(out) else out
            stamped = [stamp(check, f) for f in findings]        # a bad finding = a bad check
            # L115: a finding naming a claim the note lacks would render nowhere
            if any(i not in claim_ids for r in stamped for i in r.claim_ids):
                raise ValueError(f"{check.name}: a finding names a claim the note lacks")
        except Exception as exc:
            # A crashed check is NOT a passed check and NOT a 500 (invariant 12). Logged in
            # L69's form, by NAME and structure: the message and exc_info can carry the
            # note's content (L53, L113). CancelledError is a BaseException and correctly
            # passes through.
            logger.error("check_crashed code=check_errored check=%s exc_type=%s frames=%s",
                         check.name, type(exc).__name__, format_frames(exc))
            results.append(EvalResult(check=check.name, severity=check.severity,
                                      passed=False, errored=True, detail="check errored"))
            continue
        results.extend(stamped or [EvalResult(check=check.name, severity=check.severity,
                                              passed=True)])
    return EvalReport(results=results,
                      checks_run=frozenset(c.name for c in selected),
                      checks_version=CHECKS_VERSION,
                      judge_usage=judge.usage if judge is not None else TokenUsage())
```

Why an errored result is `passed=False`: silently skipping a check is the v1.1 vacuous-truth
bug wearing a stack trace. A crashed CRITICAL in production turns the note red — loud,
honest, fixable. A judge that times out is an errored WARNING: the note is returned, its
CRITICAL verdict is unchanged (invariant 7 is exactly why a judge outage can turn a note
neither red nor green), and the UI says the semantic check didn't run (§9.10). "Not checked"
never renders as "passed."

**The per-case verdict (v1.1; tri-state v1.3).** The v1.1 fix — consume the answer key, so a
fired expected flag is a PASS for a detection trap — stands. v1.3 adds the two cases it
couldn't express, and renames `case_passed` because the answer is no longer a bool:

```python
def case_verdict(report: EvalReport, case: EvalCase) -> CaseStatus:
    if not report.checks_run:
        return "not_applicable"           # L117: a run that checked nothing scores no case,
                                          #   not even a control (invariant 12)
    expected = set(case.expected_flags)
    if not expected <= report.checks_run:
        return "not_applicable"           # L44: an expected check didn't RUN (judge off) —
                                          #   excluded from the rates, recorded, not a fail
    errored = {r.check for r in report.results if r.errored}
    if errored & expected or any(r.errored and r.severity is Severity.CRITICAL
                                 for r in report.results):
        return "failed"                   # L43: an error never satisfies an expectation,
                                          #   and a crashed CRITICAL never passes a case
    fired = {r.check for r in report.results if not r.passed and not r.errored}
    unexpected_critical = any(
        not r.passed and not r.errored and r.severity is Severity.CRITICAL
        and r.check not in expected
        for r in report.results
    )
    return "passed" if expected <= fired and not unexpected_critical else "failed"
```

The v1.2 bug L43 closes, traced:

```
v1.2: allergy_contraindication raises → EvalResult(passed=False, detail="check_error")
      fired = {… if not r.passed} ∋ "allergy_contraindication" → expected <= fired → PASS
      The showpiece trap scored green BECAUSE its check was broken.
v1.3: errored=True → excluded from fired, and errored ∩ expected ≠ ∅ → FAILED
```

How the verdict reads across species:

```
species     expected   what happened                    verdict   all_critical_passed alone
─────────────────────────────────────────────────────────────────────────────────────────────
detection   {contra}   fired {contra}                   PASSED    FAIL  ← the v1.1 inversion
detection   {contra}   fired {}                         FAILED    PASS
detection   {contra}   errored {contra}                 FAILED    FAIL  (v1.2's verdict: PASS, L43)
detection   {judge}    judge not selected               N/A       —     ← L44
control     {}         no check ran                     N/A       FAIL  ← L117
fidelity    {}         fired {}                         PASSED    PASS
fidelity    {}         fired {allergy_preserved}        FAILED    FAIL
control     {}         fired {dose_consistency} (W)     PASSED*   PASS
control     {}         fired {drug_in_quote} (C)        FAILED    FAIL  ← a false positive
                                                        * visible in unexpected_fired
```

**The verdict is CRITICAL-scoped, on purpose.** An unexpected WARNING doesn't fail a case — a
corpus that fails on every borderline dose regex is one nobody trusts. But `unexpected_fired`
and `errored_checks` record every severity: gate on CRITICAL, *watch* everything.
An injected control is held harder by a test, not by the verdict: an authored draft can't be
borderline, so it fires no check (§8.5, L162).

(`fidelity_dropped_allergy`, §8.5: `allergy_preserved` fires live and `must_preserve` fires
in CI — two CRITICALs on a fidelity trap, so it fails, correctly, because the model dropped
the allergy. Its injected twin, `detect_dropped_allergy`, a detection trap expecting both
names from 2b (`allergy_preserved` alone in 2a, L145), passes when both fire. The answer key
decides which question a case asks. That's the point of having one.)

**The metrics (v1.3, L3).** One `pass_rate` blended three species: a clean control passing
caught nothing, and a fidelity trap where the model dropped the allergy *and*
`allergy_preserved` fired live was a failure in the rate even though the safety layer
worked. `corpus_metrics()` separates them:

```
detection_recall     = detection repeats passed / detection repeats applicable
control_specificity  = control repeats passed   / control repeats applicable
model_fidelity       = fidelity repeats passed  / fidelity repeats applicable
fidelity_caught      = of fidelity repeats that FAILED without a pipeline error, the fraction
                       where at least one reference-free (live) CRITICAL fired
pass_rate            = repeats passed / repeats applicable, every species (never alone)
```

`fidelity_caught` is the number the interview sentence (§2) was reaching for: *when the model
got it wrong, would production have seen it?* Recall for the fabrication checks is not in
this record at all — it is the injected tier, and it is 100% or CI is red. Every metric is
`None`, not 1.0, over an empty denominator, `pass_rate` included (L205), and a repeat is
applicable unless it is `not_applicable`. A case with a pipeline `error` is `failed`: no
note reached the checks, and that never reads as safe (invariant 12).

`fidelity_caught` counts a live CRITICAL alone (L206). It claims what production would have
shown, and counting a WARNING would let an incidental one (a degenerate quote) score a catch
on a fidelity failure, which lands exactly on the CI-only gaps the omission table declares
(D17), the gaps the metric exists to expose. Undercounting the narrow WARNING slice
(`new_prescription_preserved`) errs safe, and a WARNING stays visible in `unexpected_fired`.

**The scorer, with lineage (v1.1; hardened v1.2 and v1.3; at the edge, L188).**

```python
# backend/corpus.py — EDGE (L188): settings, the API, git, and runs/ meet here
async def score_corpus(cases: list[EvalCase], *, client: LLMClient,
                       judge_factory: Callable[[], Judge] | None) -> CorpusRunRecord:
    model_cases = [c for c in cases if c.draft is None]        # injected cases are pytest's
    if not model_cases:
        raise ValueError("no model cases — refusing to emit metrics over nothing")

    git_sha, git_dirty = current_git_sha(), git_is_dirty()     # L207: before any spend
    config = settings.checks_config()                          # L187: built once,
    sem = asyncio.Semaphore(settings.corpus_concurrency)       #   here, and recorded whole

    async def run_one(case: EvalCase, repeat: int) -> tuple[CaseResult, TokenUsage]:
        async with sem:
            result: SummarizationResult | None = None
            wall_s: float | None = None
            started = time.perf_counter()                      # L201: inside the semaphore
            try:                                               # L208: every step inside
                result = await summarize(case.raw_text, client=client)
                wall_s = time.perf_counter() - started
                judge  = judge_factory() if judge_factory else None   # per case: its usage
                note   = ground(result.draft, case.raw_text, config=config)   # is its own
                report = await run_checks(note, case.raw_text, case, mode="ci",
                                          config=config, judge=judge)
                return (case_result(case, repeat, report, result,     # via case_verdict()
                                    summarize_wall_s=wall_s),
                        report.judge_usage)
            except OrchestratorError as e:                     # summarize raised: its clock
                failed = errored_case(                         #   stops here
                    case, repeat, e.code, usage=e.usage,
                    validation_attempts=e.validation_attempts, draft=None,
                    summarize_wall_s=time.perf_counter() - started)
                return failed, TokenUsage()
            except Exception as e:     # v1.3 (L46): parity with run_checks — an APIError on
                logger.error(          #   one case can't escape gather and discard the rest
                    "case_crashed code=case_errored case=%s exc_type=%s frames=%s",
                    case.id, type(e).__name__, format_frames(e))         # L113: L69's form
                # L186, L203: a crash after summarize returned keeps the cost and the draft
                meta = result.metadata if result is not None else None
                failed = errored_case(
                    case, repeat, type(e).__name__,
                    usage=None if meta is None else meta.usage,
                    validation_attempts=None if meta is None else meta.validation_attempts,
                    draft=None if result is None else result.draft,
                    summarize_wall_s=(time.perf_counter() - started if wall_s is None
                                      else wall_s),
                )
                return failed, TokenUsage()

    pairs = await asyncio.gather(*(run_one(c, r) for c in model_cases
                                   for r in range(settings.corpus_repeats)))   # D11
    results = [cr for cr, _ in pairs]
    record = CorpusRunRecord(
        ran_at=datetime.now(timezone.utc),
        git_sha=git_sha, git_dirty=git_dirty,                       # L45, L207
        model=settings.model, prompt_version=PROMPT_VERSION,        # L46: known without a
        corpus_version=corpus_version(model_cases),                 #   successful call, so
        checks_version=CHECKS_VERSION,                              #   an all-failed run is
        checks_config=config,                                       #   still recorded: the
        judge_enabled=judge_factory is not None,                    #   one most need to see
        repeats=settings.corpus_repeats,
        concurrency=settings.corpus_concurrency,                    # L202
        n_cases=len(model_cases),
        metrics=corpus_metrics(results),
        usage=sum((r.usage for r in results if r.usage is not None), TokenUsage()),  # L186
        judge_usage=sum((j for _, j in pairs), TokenUsage()),
        cases=results,
    )
    append_jsonl(settings.runs_path, record)
    return record
```

v1.2 had three ways to lose a record — one error unwinding the run, an empty corpus dividing
by zero, sequential awaits — and fixed them. v1.3 closes the last two: a non-orchestrator
exception on one case (an upstream `APIError`) no longer escapes `gather` and discards the
other 23; and a run where every case failed still writes its record, because lineage no
longer depends on a successful call. L208 closes two more: building the judge and building
the case's result sat outside the per-case `try`, so a raise in either escaped `gather` and
discarded every row. And the tree is read before the first call (L207), since one read after
a long run can name code that never ran. `git_is_dirty` counts untracked files, because an
untracked case YAML runs, and skips what `.gitignore` excludes; outside a git checkout
`current_git_sha` raises before anything is spent.

**Why `score_corpus` is an edge module (L188).** It reads `settings`, calls the API through
`summarize`, shells out to git, and writes `runs/`: every side effect the domain refuses.
v1.3 filed it in `evals/runner.py`, which left `evals/` importing the config. Now
`corpus.py` builds the config (`settings.checks_config()`) and is where a real run gets its
client (`get_client()`, §5.2); `evals/runner.py` keeps the pure parts — `run_checks`,
`case_verdict`, `corpus_metrics`, `case_result`, `errored_case`, `CHECKS_VERSION`. An AST
test holds the line (§11). Each case carries its own cost (L186): `CaseResult.usage` and
`.validation_attempts` come from `RunMetadata` on success, from the `OrchestratorError` on
a pipeline failure, and from the `RunMetadata` again when a crash comes after `summarize`
returned. They are `None` only when a crash lost the case's cost (an `APIError` inside
`summarize`), so the record's `usage` is the sum of the known costs: a floor, never a
guess.

**What a case keeps, and how a run starts (L201–L203, L210).** `summarize_wall_s` is
`time.perf_counter()` around the `await`, started inside the semaphore. The SDK's timeout
clocks each HTTP attempt, not the call (measured), so the wall time holds every validation
attempt and every transport retry with its backoff. L185's bound is read from the rows with
no `error` and one validation attempt, naming its inputs: a hidden transport retry only
lowers the throughput read, which errs safe, and corpus replies are short, so the samples
sit far below the full output budget. `concurrency` is on the record because contention
lands in those times (429 retries and their backoff) and in the failure count. `draft` makes
a run replayable: grounding and the checks are pure functions of the draft, the raw text,
the config, and the code at the run's commit (D5), so reading a run, or a check change
against it, costs no API call. A run starts from `python -m backend.corpus`, which loads the
cases, prints the planned calls (n × k, and the ceiling with validation retries), and exits;
`--spend` runs it with `get_client()` (§5.2) and prints the record's metrics and where it
was written.

`CHECKS_VERSION` (v1.3, L45) is a hash over the source of `evals/`, `clinical/`,
`grounding.py`, and `schemas.py` (L189), computed at import — derived like every other
version (invariant 15). `schemas.py` holds verdict logic (`all_critical_passed`, L102, and
`EvalResult`'s errored-never-passes validator), so it joins; it also moves the version on
edits that change no verdict, which errs in the safe direction. The knobs that decide
verdicts aren't source, so they are recorded whole beside the hash (`checks_config`, L187),
and `score_corpus`'s source left the hash when it left `evals/` (L188): orchestration
decides no verdict. Source is the `.py` files: the case YAMLs have `corpus_version`, and
`runs/corpus_runs.jsonl` changes with every run. Each file enters with its path relative to
`backend/` and its content's hash, sorted by path, so a moved or renamed file moves the
version; twelve hex digits, as `prompt_version` (L114). v1.2 hashed the model, the prompt,
and the corpus but not the checks: editing a lexicon changed verdicts with every lineage
field unchanged.

**DECISION D11 (v1.3, vetoable) — repeats.** Replies vary from run to run, and no sampling
parameter is sent to narrow them (§3, L181); at n = 24 with one run, a single flaky case
moves a rate by ~4 points — noise that reads as a regression. `settings.corpus_repeats`
(default 3; cost × k) runs every model case k times; `CaseResult` rows are per (case,
repeat); `CorpusMetrics.flaky_cases` names every case whose pass fraction is strictly
between 0 and 1. The README states n and k beside every number.

**DECISION D5 (v1.2, amended v1.3) — where the lineage lives.** Corpus runs happen locally,
and `corpus_runs.jsonl` is committed *in the same commit* as the prompt/model change that
prompted them; the manual-dispatch workflow also uploads the record as a build artifact. v1.3
(L45): committing the run with its change means the run executes on uncommitted code by
design — so `git_sha` names the parent commit, `git_dirty=True` says so honestly, and
`prompt_version` + `checks_version` identify the code that actually ran.

- **production:** the reference-free subset runs on every real note → a **live safety
  layer**; its CRITICAL findings are the red badges in the UI.
- **ci:** the full suite → **injected** cases in pytest (deterministic proof of every check)
  and **model** cases in `score_corpus` (the four metrics, with lineage).

Same code, two masters, three clocks (§11). The eval harness was never a testing
afterthought — it is what makes the model-choice and prompt-change decisions
evidence-based.

### 8.8 Honest mirror (state this, don't hide it)

Clinical-semantic evaluation is **genuinely unsolved at the frontier.** The judge has its own
false-positive and false-negative rates; a truly rigorous version would *meta-evaluate the
evaluators* (do the checks agree with a human clinician?). What this harness does **not**
know, stated plainly (v1.3):

- **Lexicon recall on real language.** Injected traps prove each check fires on the text it
  was written for. How often the hand lexicon misses a real-world phrasing is unmeasured —
  the corpus is synthetic by design (zero PHI).
- **Vocabulary** (L127, L130). A drug the lexicon doesn't list is invisible to every drug
  check, which then passes over it. Recall on an unlisted drug is zero, not unmeasured. An
  allergen that isn't a drug (latex, a food) is never extracted, so `allergy_preserved`
  can't see one dropped.
- **An empty note on a source the lexicons can't read** (L165).
  `empty_note_on_clinical_input` knows clinical input only by what the extractors read
  (L164), so its recall is the vocabulary's. "HTN follow-up, BP 152/96 today. Start
  amlodipine 5 mg daily, recheck in 4 weeks." names nothing the lexicons list (measured): an
  empty note on it raises no WARNING and renders as non-clinical (§10). The other way, a
  non-clinical paste naming a listed word ("pain") draws the WARNING, whose detail names the
  word.
- **A drug after an allergy post-cue** (L154). "PCN allergy (amoxicillin)" and "PCN allergy -
  amoxicillin" read the amoxicillin as an active drug, since a post-cue labels only what comes
  before it (§7), so a faithful claim copying either fires `allergy_contraindication`. "PCN
  allergy: amoxicillin" reads "allergy:" as a header and loses the penicillin, so a note
  writing "PCN allergy" reads as dropping the amoxicillin, which `allergy_preserved` reports.
  Both fail loud.
- **Findings both sides name** (L139). `negation_consistency` compares polarity only for a
  finding the claim and its span both name, and `FINDINGS` and its aliases list no other
  names (L173). A flip behind a name it lacks ("denies CP" → "reports chest pain") reads
  nothing; so does a finding the span never names, which is the judge's and `must_not_add`'s
  to catch. A span holding both polarities ("denies chest pain at rest, reports chest pain
  on exertion") passes a claim keeping either one, since qualifiers aren't extracted.
- **Laterality** (L200). No extractor reads a side and no check compares one (§7, §8.4), so
  a wrong side has only the judge behind it (2c, WARNING-tier). A claim reading "Right knee
  pain after a fall" under the verbatim quote "Left knee pain after a fall" grounds at Tier
  1 and fires nothing. A quote that swaps the side itself fires nothing when it clears the
  fuzzy cutoff, and most do: mid-note, "Pain in L arm since this morning" against "R arm"
  scores 96.9, and a 43-character left/right swap 93.0. "Left" and "right" differ in
  length, so a short one can fall below it: "Left knee pain after a fall" mid-note scores
  88.9 and is flagged `UNSUPPORTED`, which the clinician sees (all measured, cutoff 90).
  Wrong-site is a never-event class; the check waits for a later minor revision.
- **A span that cuts off its cue** (L157). The claim-local family reads the span (L35), so a
  cue outside it is invisible. A bare name grounds at Tier 1 and reads at the defaults
  (active, present, definite), so a flip away from stopped, denied, or hedged passes every
  check: "Continue metformin" citing "metformin" in "Hold metformin", "Fever" citing "fever"
  in "Denies fever", "PE" citing "PE" in "r/o PE" or "PE ruled out" (measured). A flip
  toward them fires, as does a dose its span lacks. `quote_informativeness` flags a
  one-token span, a WARNING (L158); a two-token one passes it ("Reports chest pain" citing
  "chest pain" in "Denies chest pain"), and so does a slash abbreviation, which counts two
  ("Reports N/V" citing "N/V" in "Denies N/V", measured, L175); and the judge is
  WARNING-tier (invariant 7). The fix reads a span in its sentence, which changes what L35
  compares, so it waits for a later minor revision.
- **A cue the scope rule can't reach** (L168). A mention takes one label, and a post-cue
  reaches back from the mention directly before it (§7, L122, L193), never past a word, so
  "Apixaban held, then restarted" reads stopped: a faithful "Continue apixaban" fires
  `med_status_consistency`, a CRITICAL, and "Hold apixaban", which drops the restart,
  passes it (measured). A negation before a start form no table spells as a refusal reads
  as the start ("Not starting metformin"). The fix reads a mention's last status cue in its
  clause and lets a negation govern a start cue, which changes the scope rule, so it waits
  for a later minor revision.
- **Labels read through the extractors** (L220). The loader checks a label against the raw
  text through the same extractor the check uses (L219), so a label can't state what the
  extractor misreads, and a misread label loads: "metformin held, then restarted" reads
  stopped (L168), as label and as source alike (measured). Case authoring avoids the
  phrasings this section lists.
- **A list after a word** (L193). A negation, stop, or start post-cue reaches back over a
  list only when the list opens its clause (§7), so a list after a word reads
  adjacent-only: "no fever, but chills, nausea denied" reads the chills present. Reaching
  further without the clause condition read "Continue lisinopril, metformin held" as
  stopping the lisinopril and "Reports fever, chills denied" as the fever absent
  (prototyped), a false CRITICAL on each faithful note.
- **A word that states an absence** (L173, L174). An `ABSENT_FINDINGS` word reads absent
  under any cue, so a double negation the tables don't spell reads absent ("denies chills,
  not afebrile"), and so does the word cut from one: "Afebrile" citing "afebrile" in "no
  longer afebrile" passes every check, since `quote_informativeness` exempts the word as it
  exempts NKDA (measured). Read as negated instead, the word would flip inside every negated
  list ("denies chills, afebrile"), which is everyday charting.
- **Judge quality.** Measured only indirectly, through model cases; never against a
  clinician.
- **Reaction type** (D14). An anaphylaxis history and a childhood rash get the same rung.
  Side chains are compared for identity only (D9, L149): amoxicillin's and cephalexin's,
  similar but not identical, read as not shared, a WARNING.
- **Wrong-reason passes** (D16). Expected flags match on check name; the authoring rule
  narrows the gap, it doesn't close it.
- **Small n** (D11). 24+ model cases × k repeats is a regression tripwire, not an accuracy
  estimate — the README says so next to the number.

Don't oversell the harness as bulletproof. The strength isn't claiming I solved clinical
safety — it's understanding the problem deeply enough to know I *haven't*, and building
honest guardrails anyway. That humility reads as more senior than any accuracy number.

---

## 9. Layer 5 — API + persistence

Less *conceptual* weight than the layers above; its value is **craft and credibility.**
This is where the project reads as "shipped software" vs "school assignment," and the
difference is entirely the boring stuff done right. It's Phase 2 material (FastAPI, SQL)
doing load-bearing work.

### 9.1 The route is a composition root (no logic lives here)

```python
class SummarizeRequest(BaseModel):          # HTTP-boundary shape; lives in api.py (EDGE —
    raw_text: str = Field(                  #   sanctioned outside schemas.py, §13)
        max_length=settings.max_input_chars,    # an oversized paste fails honestly at
    )                                           # validation (422). Chunking stays v2.

    @field_validator("raw_text")                # v1.3.2 (L87): the degenerate-input guard
    @classmethod                                #   (§10) counts CONTENT, and never mutates:
    def _enough_content(cls, v: str) -> str:    #   from phase 2a every span is an offset into
        if len(v.strip()) < settings.min_input_chars:   # the exact paste. Stripping here
            raise ValueError("too short")       #   would shift every highlight.
        return v

class SummarizeResponse(BaseModel):
    note_id: UUID                            # minted HERE, before persist runs
    note: SOAPNote
    report: EvalReport                       # incl. judge_usage (L7)
    metadata: RunMetadata                    # model / prompt_version / usage / attempts

@app.post("/summarize", response_model=SummarizeResponse)
async def summarize_endpoint(
    req: SummarizeRequest,
    background_tasks: BackgroundTasks,
    client: LLMClient = Depends(get_client),
    judge: Judge | None = Depends(get_judge),   # None unless settings.judge_enabled (edge)
    _: None = Depends(reserve_budget),          # §9.8: 503 budget_exhausted BEFORE any spend
):
    note_id = uuid4()
    result = await summarize(req.raw_text, client=client)                     # orchestrator
    config = settings.checks_config()                                         # L187
    note   = ground(result.draft, req.raw_text, config=config)                # grounding
    report = await run_checks(note, req.raw_text, mode="production",          # evals (live subset)
                              config=config, judge=judge)
    background_tasks.add_task(persist, note_id, req.raw_text, note, report, result.metadata)
    return SummarizeResponse(note_id=note_id, note=note, report=report,       # sink runs AFTER this
                             metadata=result.metadata)
```

A handful of lines that wire the pipeline in order. **The thinness is the signal** — a
seven-line route instead of a 200-line god-handler is the visual proof of "dependencies
point inward." `persist` rides a `BackgroundTask`, so "the sink runs after the response" is
the framework's execution order, not a promise the route keeps (§9.6). The id is minted in
the route because the response must carry it and the response is built before the row
exists.

**Phase 1 is smaller, and says so (v1.3; L76).** No grounding, no report: the phase-1 route
returns `{draft: SOAPNoteDraft, metadata: RunMetadata}`. The type name tells the reader the
content is unverified (§4.1) — honest by construction. The wire shape is its own edge type in
`api.py`; the route never uses `SummarizationResult` as its `response_model`:

```python
class SummarizeResponse(BaseModel):          # phase 1; becomes the shape above in phase 2a
    draft: SOAPNoteDraft
    metadata: RunMetadata
```

The domain return type and the wire contract are different jobs: in phase 2a the edge shape
becomes `note_id` + `note` + `report` + `metadata`, and nothing in `schemas.py` changes.
*Test:* in phase 1, the happy-path route test asserts the body's top-level keys are exactly
`{"draft", "metadata"}`.

**Phase 2a's route is the one above, less what later phases add (L166).** No judge until 2c,
so `run_checks` selects no judged check; no `reserve_budget` and no `persist` until phase 3
(§14). `note_id` is minted all the same: with nothing persisted it names no row, as §9.10
says of `persist_enabled=false` (L58). *Test:* the happy-path route test asserts the keys
are exactly `{"note_id", "note", "report", "metadata"}` and a span that offsets into a
padded paste; a test that registers its own checks asserts the route checks the note it
returns, against the exact paste, in production mode, with no judge.

### 9.2 Async, justified (amended v1.2)

`await` the I/O-bound steps: the LLM call (seconds) and, when enabled, the judge's
second call inside `run_checks`. Grounding and the deterministic checks are fast,
CPU-bound, pure → they run inline *inside* those awaits; nothing about them is
awaited individually. *"Why async here?"* → "two network calls per request, one of
them optional, and I didn't want either serializing the event loop, while the
deterministic layers stay inline." (v1.1 said "grounding and evals run inline";
D2 made half of that false and v1.2 says the true version.)

### 9.3 Response contract = the spine's 4th job

`SOAPNote` + `EvalReport` are Pydantic models already written in §4 → FastAPI serializes
them, validates the outgoing shape, and generates live OpenAPI docs **for free.**

The verdict travels with them (L102). `all_critical_passed` is a computed field, so it is in
the body and in the OpenAPI schema. A consumer that recomputed it from `results` could drop
the vacuous-truth guard (invariant 12); the page and the phase-3 UI read it instead.

### 9.4 Error translation at the HTTP boundary

```
RequestValidationError (length guard)  → 422  input_invalid          the INPUT is the problem
RateLimitExceeded (slowapi)            → 429  rate_limited           THIS client is over its limit
BudgetExhaustedError                   → 503  budget_exhausted       the demo's daily cap (§9.8)
OutputTruncatedError                   → 502  output_truncated       config ratio / model verbosity
ModelOutputError                       → 502  model_output_invalid   the MODEL is the problem
anthropic.RateLimitError               → 503  upstream_busy          + Retry-After if exposed
anthropic.APITimeoutError              → 504  upstream_timeout       v1.3 (L54)
anthropic.APIStatusError 429, 529      → 503  upstream_busy          overloaded = busy (L71, L99)
anthropic.APIStatusError 4xx (not 429) → 500  internal_error         OUR request or config (L71)
anthropic.APIStatusError (any other)   → 502  upstream_error         not my bug (L71, L99)
anthropic.APIError (other)             → 502  upstream_error         incl. non-timeout connection failures
unexpected Exception                   → 500  internal_error         logged by structure, never message (L69)
```

Every body has one shape — `{"error": <code>, "request_id": <id>}` — and **never** the
exception's message (v1.3, L53). A Pydantic `ValidationError` string carries `input_value`,
which here is model-emitted clinical text; v1.2's handlers returned `{"detail": str(exc)}`
and echoed it to the client. Handlers resolve by the exception's MRO, so the specific
subclasses (`OutputTruncatedError`, `APITimeoutError`) win over their parents.

```python
@app.exception_handler(ModelOutputError)          # OutputTruncatedError inherits → its own code
async def handle_model_output_error(request: Request, exc: ModelOutputError):
    rid = request.state.request_id
    logger.warning("model_output_failure code=%s request_id=%s", exc.code, rid)   # L79
    return JSONResponse(status_code=502, content={"error": exc.code, "request_id": rid})
```

The route never leaks a stack trace; it speaks HTTP semantics, and each code says a
*different true thing about whose fault it was*. v1.2 split `OrchestratorError` so a model
that returned garbage three times wasn't reported as the client's malformed request; v1.3
(L14) finishes the job — truncation on an input the route already accepted isn't the
client's fault either. And 429 is reserved for *our* rate limit: passing upstream throttling
through as 429 would tell the client *they* sent too many requests.

**Boundary details (L69–L71, L73, L79, L80, L98, L99).** Each fills or reconciles a line
above, and each names its test.

- **The 500 path logs structure, never messages (L69).** L53's PHI rule beats the table's
  former "logged in full" cell. The 500 path logs `code="internal_error"`, `request_id`,
  `exc_type=type(exc).__name__`, and frames as `file:line:function` from
  `traceback.extract_tb` — never `exc_info`, `str(exc)`, or a chained cause. Frames carry
  no PHI; messages can (a chained `ValidationError` carries `input_value`).
  `tracebacks.py`, which imports nothing from `backend/`, renders them, so a domain module
  can log a failure the same way (L112). It is a catch-all **middleware** running inside
  the request-id middleware, not `@app.exception_handler(Exception)`: Starlette's
  `ServerErrorMiddleware` calls that handler and then re-raises for the server to log, so
  uvicorn prints the full traceback anyway. The specific handlers (`ModelOutputError`, the
  SDK errors) stay `exception_handler`s. *Test:* a route raising an exception whose
  message is a sentinel → 500 `{error, request_id}`; the sentinel is in no `caplog` record
  and not in the body. With the default `TestClient`, the wrong implementation fails this
  test by re-raising.
- **The default 422 handler is replaced (L70).** FastAPI's default returns `exc.errors()`,
  whose `input` is the entire paste. A `RequestValidationError` handler returns 422
  `{"error": "input_invalid", "request_id": ...}` and logs by code only. *Test:* an
  oversized paste, an undersized paste, and a whitespace-padded paste longer than
  `min_input_chars` whose content is shorter (L87), each containing a sentinel → 422 with
  the correct body; the sentinel is in neither the body nor the logs.
- **Upstream failures are attributed by status (L71, L99).** A single `APIError` row
  calling every upstream failure "not my bug" contradicted this section's own rule: a 401
  from a bad key is our config, not upstream's bug. One `APIStatusError` handler branches
  on status — 4xx except 429 → 500, logged with `upstream_status` (our schema, key,
  access, model id, or size); 5xx except 529 → 502; 529 → 503, the same meaning as
  `RateLimitError`, whose own handler wins for 429 by MRO. The handler is total (L99): 429
  and 529 → 503, checked first because 429 is also a 4xx, so a 429 that arrives as the base
  class still means busy; any status outside 4xx/5xx → 502. It branches on the status,
  never the subclass: an upstream 503 or 504 → 502, whatever class carries it, and 504
  `upstream_timeout` is only our own client's timeout (L54). It forwards no headers:
  `Retry-After` stays on `RateLimitError`'s row. A connection failure that is not a timeout
  (`APIConnectionError`, not `APITimeoutError`) takes the residual `APIError` row. *Test:*
  one per mapping, with the fake client raising each status as the class the SDK builds for
  it, plus a base-class 429, a status on each side of 4xx/5xx, and a 529 carrying
  `Retry-After`, which the response drops; a `RateLimitError` with and without
  `Retry-After`. `APIConnectionError` gets its own test: it reaches 502 through a different
  MRO branch than a 5xx, and `APITimeoutError` subclasses it, so the pair pins the 504
  handler winning.
- **Phase-1 reach (L73).** Reachable in phase 1: 422 `input_invalid` · 502
  `output_truncated` · 502 `model_output_invalid` · 503 `upstream_busy` · 504
  `upstream_timeout` · 502 `upstream_error` · 500 `internal_error`. Not until phase 3: 429
  `rate_limited`, 503 `budget_exhausted`. The HTTP test module lists both sets at the top.
  `request_id` is minted per request by middleware (`uuid4().hex` on
  `request.state.request_id`); every error body and log line carries it. *Test:* 502
  `model_output_invalid` is reached twice — a response with no tool block, and
  `stop_reason="refusal"` with no tool block — so the refusal path is pinned behavior, not
  an accident of the missing-block branch.
- **Log fields render in the message (L79).** With no custom formatter, `extra=` attaches
  attributes to the `LogRecord` that no handler prints: a `caplog` test asserting on record
  attributes passes while the terminal shows neither field. Log calls put their fields in
  the message as `key=value` pairs via %-style args, as in the sample above. `api.py`
  configures the root logger once at app construction (§9.8). *Test:* logging assertions
  read `record.getMessage()`, never record attributes; each handler's test asserts its
  `code` and `request_id` appear in the rendered message.
- **Framework default error bodies are replaced (L80, L98).** Outside
  `RequestValidationError`, FastAPI's default `HTTPException` handler returns
  `{"detail": ...}` for unmatched routes and methods, breaking "every body has one shape."
  A handler registered on `starlette.exceptions.HTTPException` (FastAPI's subclasses it,
  and the router raises the Starlette one) returns `{"error": <code>, "request_id": ...}`
  with the original status and the exception's headers: 404 `not_found`, 405
  `method_not_allowed`, anything else `http_error`. The headers are protocol, not content:
  the router's 405 carries `Allow`, which RFC 9110 requires on every 405, the courtesy the
  table above extends to `Retry-After` (L98). These are framework codes, not rows of the
  table above, and not part of the phase-1 reach list. *Test:* `GET /nope` → 404
  `{"error": "not_found", ...}`; `GET /summarize` → 405
  `{"error": "method_not_allowed", ...}` with `Allow: POST`; a `POST /summarize` whose JSON
  body is not valid UTF-8 → 400 `{"error": "http_error", ...}`.

### 9.5 Persistence: hybrid relational-envelope + JSONB

A SOAP note is a **document-shaped aggregate** — read and written whole; you never query
"every claim across all notes where section='A'." Normalizing into a claims table builds
query power you have no query for (Volkswagen). So: relational envelope, JSONB payload.

```python
class NoteRecord(Base):
    __tablename__ = "notes"
    id                         = Column(UUID, primary_key=True)   # minted in the route (§9.1)
    created_at                 = Column(DateTime, server_default=func.now())
    raw_text                   = Column(Text)
    model_used                 = Column(String)      # ← regression metadata
    prompt_version             = Column(String)      # ← regression metadata
    checks_version             = Column(String)      # ← v1.3 (L57): verdicts stay interpretable
                                                     #   across a lexicon change
    input_tokens               = Column(Integer)     # ← the cost axis (§5.5), summed across
    output_tokens              = Column(Integer)     #   validation attempts (L13)
    validation_attempts        = Column(Integer)     # ← v1.3 (L57)
    judge_input_tokens         = Column(Integer)     # ← v1.3 (L7, L57): the second call's cost
    judge_output_tokens        = Column(Integer)
    production_critical_passed = Column(Boolean)     # ← PER-NOTE verdict from the PRODUCTION
                                                     #   (reference-free) mode
    note                       = Column(JSONB)       # ← the whole validated SOAPNote
    report                     = Column(JSONB)       # ← the whole EvalReport
```

The pulled-out columns are exactly the ones you'd ever filter or trend on. `model_used` +
`prompt_version` + `production_critical_passed` make the **regression thesis durable**:
later you can query *"did my CRITICAL pass-rate drop when I switched from Opus to Haiku?"*
— the evals-as-regression story becomes a tracked metric with history, not a one-shot
script print.

> ⚠️ Naming (v1.1, sharpened): there are **two similarly-shaped metrics** and the name
> now says which is which. `production_critical_passed` is a per-note boolean from the
> reference-free production subset. The **CI corpus rate** is a different number from a
> different check-set, and it lives in `evals/runs/corpus_runs.jsonl` (§8.7). Never
> store either aggregate in a per-row column; never let the two share a name.

### 9.6 Persistence is a sink, not a dependency

`persist()` runs *after* the response is returned — as a `BackgroundTask`, that's the
framework's guarantee, not the route's good manners. The pipeline never reads from the
DB. A write failure must NOT 500 the user — they already have their valid,
safety-checked note (and by the time the task runs, the response is already gone):

```python
async def persist(note_id, raw_text, note, report, metadata) -> None:
    if not settings.persist_enabled:                    # v1.2: the demo can run stateless (§9.8)
        return
    try:
        async with SessionLocal() as session:           # v1.2: its OWN session — see below
            session.add(NoteRecord(id=note_id, raw_text=raw_text, ...))
            await session.commit()
    except DBError:
        logger.error("persist failed", exc_info=True)   # log, don't raise
```

**The session trap (v1.2):** `persist` must open its own session from the sessionmaker,
never receive the request's `Depends(get_session)`. Since FastAPI 0.106, dependencies
with `yield` run their cleanup *before* background tasks execute — the request-scoped
session is already closed by the time the sink runs, and the write fails with a
closed-connection error on every single request. It would be logged and swallowed
(§9.6 promises exactly that), so the app would look healthy while persisting nothing.
A sink that silently sinks nothing is the failure mode this section was written to
prevent; the integration test asserts a row exists after the response.

### 9.7 Two UI render channels (present-but-suspect vs absent-but-required)

Flags live in two places, and **omissions have nowhere to hang** (the dropped thing isn't
in the note):

- **claim-anchored findings** → **inline highlights.** Two sources, joined by
  `claim.id` (v1.2): grounding's `ClinicalClaim.flags` + `source_span` (hover a claim,
  see its source; yellow for `PARAPHRASED`, red for `UNSUPPORTED`), and any
  `EvalResult` whose `claim_ids` is non-empty (the contraindication finding lands on
  the amoxicillin claim *and* the allergy claim).
- **note-level findings** (`EvalResult` with `claim_ids == ()`: omissions, an errored check,
  the dropped allergy that has no claim to hang on, and — v1.3, L51 — a contraindication
  whose drug exists only in the source because the note dropped it) → a **top-of-note
  safety banner.**

"flags → badges" was too simple; the response contract must expose both channels —
and in v1.2 it actually can, because `claim_ids` exists (v1.1 described the two
channels and shipped a contract that could only express the first).

### 9.8 Edge cases / production realities (flag, don't all build)

- **Connection pooling** — the real concurrency concern is the DB, not async itself. Async
  engine (`asyncpg` pool via SQLAlchemy). Cheap; do it right.
- **`/health` endpoint** — five lines; its *presence* signals you thought about deployment.
- **CORS** (v1.1) — the React dev server runs on a different origin; without
  `CORSMiddleware` (allow the frontend origin, configured in `config.py`) phase 3 begins
  with a mystery evening. One middleware registration, specced now so future-me doesn't
  debug it at midnight.
- **Logging / observability (v1.1; PHI-scoped v1.3).** stdlib `logging` configured once in
  `api.py` — plain text with timestamp, level, and logger name; fields rendered in the
  message as `key=value` (L79): per-request id, model, latency, token counts, error *codes*. v1.3 (L53) makes one
  rule absolute: **raw text, note content, and exception messages that may carry them never
  reach a log line or an HTTP body.** Concretely: `OrchestratorError` is logged by `code`
  without `exc_info`; any stringified validation error uses `errors(include_input=False)`;
  error bodies are `{error, request_id}` (§9.4); the 500 path logs exception type and
  frames, never the message or `exc_info` (L69), and a crashed check logs the same way, by
  check *name* (L113).
  `persist_enabled=false` keeps the demo out of the database; this rule keeps it out of the
  hosting platform's log retention, which v1.2's "not a PHI sink" had forgotten.
  Structured/JSON logging → v2.
- **Migrations** (v1.1, DECISION D3) — `Base.metadata.create_all` for build phases 1–2
  (schema churn is high, data is disposable); **Alembic adopted in phase 3** when
  Postgres becomes real and the schema stabilizes. The ladder is the decision: create_all
  isn't a gap, it's a phase.
- **Secrets** — API key in env, never in code (`.env` gitignored, `.env.example` committed —
  the reflex carries over from the APIs arc; matters more here, clinical-adjacent).
- **Oversized transcripts** → rejected honestly at the boundary via `max_length` (§9.1);
  chunking to *accept* them → v2.
- **The wallet (v1.2; hardened v1.3).** A deployed `/summarize` with no auth and a paid API
  key behind it is a denial-of-wallet endpoint. Minimum viable defense, both required: a
  per-IP rate limit (`slowapi`, a few requests/minute → 429) *and* a daily spend cap
  enforced in code (`settings.daily_token_budget` → 503 `budget_exhausted`). v1.3 (L56)
  closes three ways v1.2's cap leaked. **Reserve before spend:** the `reserve_budget`
  dependency atomically charges the worst case (`settings.max_request_tokens` — max input
  plus max output across every validation attempt, plus the judge's ceiling) *before* any
  call, so concurrent requests can't all pass a check-then-spend race. **No refund:** the
  demo charges the reservation, not actual usage — a conservative cap is a correct cap, and
  it needs no settlement path. **One counter:** the demo runs a single worker with an
  in-process counter under an `asyncio.Lock`, documented, because N workers × N counters is
  N× the cap and a restart is a reset. A shared counter is v2. Neither defense is "auth"
  (v2). Both are what a reviewer from a health-AI company will check for within thirty
  seconds of seeing a live link.
- **Proxies (v1.3, L58).** Behind a platform proxy, `request.client.host` is the proxy —
  every user shares one rate-limit bucket. Run uvicorn with `--proxy-headers` and
  `--forwarded-allow-ips` set to the platform's proxy range (`settings.forwarded_allow_ips`).
- **The paste box is a PHI intake (v1.2).** The repo has zero real PHI. The *deployed
  demo* has a text box, and someone will paste a real note into it. Two consequences:
  (1) the UI carries a visible "synthetic / de-identified text only — this is a demo,
  not a HIPAA environment" banner above the box; (2) `settings.persist_enabled`
  exists and the public demo runs with it **off** — the pipeline runs, the note is
  returned, nothing is written. Persistence is demonstrated in the integration tests
  and in a locally-run instance, not by accumulating strangers' clinical text on a
  free-tier Postgres. Knowing to make that call is the clinical-adjacent judgment
  the whole project is supposed to prove. (v1.3: persistence off is necessary, not
  sufficient — the logging rule above is the other half.)

**Deliberate non-feature (architecturally interesting):** **streaming.** It fights the
design — you cannot ground a claim until it's *complete*, nor safety-check a half-emitted
note. The whole flow is a *whole-object* pipeline. *"I chose not to stream because it
conflicts with grounding the output before display"* is a better interview answer than most
features. (Auth, multi-tenancy, real EHR/FHIR write-back → same v2 bucket.)

### 9.9 Honest mirror

This layer is where the instinct is to coast (the moat is elsewhere). Don't. Reviewers
**judge competence by the plumbing precisely because it's unglamorous.** The moat gets the
interview; the clean route, translated errors, health check, pooled connections, and real
tests get me trusted.

### 9.10 The frontend contract (v1.2 — previously a directory name)

`frontend/` had a one-line description and a promise ("the frontend's type
source-of-truth") with nothing backing it. The contract, minimally:

- **Types are generated, not typed.** `openapi-typescript` runs against FastAPI's
  `/openapi.json` and emits `frontend/src/api.d.ts`. `SOAPNote` and `EvalReport`
  exist exactly once, in `schemas.py`, and `SummarizeResponse` once, in `api.py` (§13,
  L76); the TypeScript is a build artifact. That's what makes the §12 receipt's last line true rather than aspirational.
- **One highlight at a time.** Spans can overlap (two claims from one sentence) and
  coincide (the duplicate-quote case, §6.5). The UI never paints all spans onto the
  source at once — it highlights the span of the claim under the cursor (or the one
  clicked), and nothing else. This sidesteps overlap rendering entirely and matches
  the product motion (§1: "hover → highlight"). A claim with `source_span: None`
  highlights nothing and shows its `UNSUPPORTED` badge; that absence *is* the signal.
  Offsets count code points, Python's string index (L177): the UI slices `[...text]`, since
  `text.slice` counts UTF-16 units and every character past the BMP would shift the spans
  after it, and it slices the text it sent, not the paste box as it now stands.
- **Findings join by `claim.id`.** The claim card shows grounding flags plus every
  `EvalResult` whose `claim_ids` contains its id; the banner shows every result with
  `claim_ids == ()`. The UI does no clinical reasoning; it renders two lists.
- **Every state designed (v1.3, L24, L55, L58)** — keyed on the body's `error` code, never
  on parsing a message: loading; result; **empty** (no claims *and* no clinical entities →
  "no clinical content recognized," §10 — if the input *was* clinical, the result state
  renders with the `empty_note_on_clinical_input` warning instead); **empty Assessment**
  ("No assessment documented" — a faithful note under D7, not a blank section); **coverage
  reduced** (an errored check → "this check didn't run on this note," never rendered as
  passed); `input_invalid` 422; `rate_limited` 429; `upstream_busy` and `budget_exhausted`
  503 (different copy — one says retry shortly, one says the demo is done for today);
  `model_output_invalid` / `output_truncated` / `upstream_error` 502; `upstream_timeout`
  504. No state is a blank page or a raw JSON dump.
- **`note_id` is not a link (v1.3, L58).** With `persist_enabled=false` the id refers to
  nothing, and `GET /notes/{id}` is v2 — the UI never implies the note can be retrieved.
- **Read-only in v1.** "Review, edit, sign off" (§1) is the product; edit and
  sign-off *persistence* is v2 (§15) — the v1 UI is a review surface. Naming that
  here is what makes it a decision instead of an omission.
- **The PHI banner** (§9.8) is above the paste box, always, not a dismissible toast.

**Before the contract: the phase-1 display (L68).** §14's "minimal display" is a static
page, not an early `frontend/`. `GET /` in `api.py` serves `backend/static/index.html`:
textarea → `fetch("/summarize")` → `draft.claims` grouped by `section` client-side; from
phase 2a it reads `note.claims` (§9.1, L166). All four sections always render; an empty one
shows "none stated" (D7). Output is labeled "DRAFT — unverified" (invariant 12: nothing
unchecked reads as checked). A one-line PHI warning sits above the textarea (the full banner
is phase 3). Same-origin, so no CORS in phase 1. No `by_section`, and in phase 1 no
`SOAPNote`: the phase-1 `schemas.py` fence holds (§14). Claims render via `textContent`,
never `innerHTML` — every `source_quote` copies the paste verbatim, so markup
in the paste would execute. `backend/static/` is deleted when `frontend/` replaces it in
phase 3. Anything but a result renders in its place (L92, L100): a response renders its
HTTP status, plus the body's `error` code and `request_id` when the body carries both; a
fetch that gets no response renders a fixed line that names no code, since there is none.
The result area is never blank, or the L81 smoke run can fail without saying so. *Test:*
`GET /` → 200, `text/html`; the served file contains no `innerHTML`.

**Phase 2a's page (L176).** The page renders the report beside the note, flat. A verdict
line reads `all_critical_passed`, never recomputed (L102), with the count of checks that
ran: those `checks_run` selected, less the errored. Each claim card shows its id and its
flags as text. Under the note, every result goes to one place by its own flags: a fired one
with its severity, check, claim ids, and detail; an errored one under "didn't run on this
note," never passed (invariant 12); a passed one by name. The page keys on no check's name.
"DRAFT — unverified" stays: the checks are not a clinician. The join by `claim.id`, the
banner, the highlight, every state above, `note_id`, and the per-code error copy are phase
3's (§14). *Test:* the served page reads `report.all_critical_passed` and `result.errored`;
CI runs no JavaScript, so the design room runs the page against real bodies in jsdom.

---

## 10. Cross-cutting concerns

- **`config.py` (pydantic-settings):** every operational knob (invariant 10) — `model`
  (pinned id, L84) and, directly beside it, `model_max_output_tokens` (its output ceiling; the
  two change together, L72); `anthropic_api_key` (`SecretStr`, required, L77);
  `max_input_chars` and `output_tokens_per_input_char` → derived `max_output_tokens` (a
  read-only property, validated against the model's ceiling at boot, L16, L94);
  `max_validation_retries` (L5); `sdk_transport_retries`;
  `llm_timeout_s`, `judge_timeout_s` (L54); `fuzzy_score_cutoff`; `min_input_chars`;
  `min_quote_content_tokens` (D15; default 2, L161) — the cutoff and the token minimum
  reach the domain only through `settings.checks_config()`, called at the edge (L187);
  `judge_enabled`; `persist_enabled`; `corpus_concurrency` (`ge=1`, default 1, L209);
  `corpus_repeats` (D11, `ge=1`, default 3);
  `daily_token_budget`, `max_request_tokens` (L56); `rate_limit`; `forwarded_allow_ips`
  (L58); `runs_path` (default `backend/evals/runs/corpus_runs.jsonl`, §13, L209); CORS
  origins. Clinical knowledge — including `NEGATION_WINDOW` —
  lives in `clinical/lexicons.py`. The literal numbers in this spec's code samples are
  `settings.*` in the repo.
- **Configuration fails at boot, not per request (L77).** Every knob declares its domain:
  `max_validation_retries` and `sdk_transport_retries` `ge=0`, `llm_timeout_s` `gt=0`,
  `min_input_chars` `ge=1`, `fuzzy_score_cutoff` `ge=0, le=100` and finite (L105),
  `min_quote_content_tokens` `ge=1` (L161), and a validator rejects
  `min_input_chars >= max_input_chars`. `ChecksConfig` (§4.2) re-declares its two fields'
  bounds, so a config built in a test can't go out of range either; a test pins the two
  copies equal (L187). A negative
  `max_validation_retries` would make §5.4's loop run zero times and report a model failure
  the model never had the chance to cause. `tests/conftest.py` sets a dummy
  `ANTHROPIC_API_KEY` before anything imports `backend`; CI needs no secret, because no test
  reaches the network. *Test:* a missing key, a negative retry count, and
  `min_input_chars >= max_input_chars` each raise at `Settings()` construction.
- **Degenerate input (v1.3, L55, L58) — three paths, not one.** A paste whose content
  (stripped length, L87) is shorter than `min_input_chars` → 422 at the route (v1.2's
  example, "hello," never reached the pipeline; this is where it was rejected). A long
  non-clinical paste → a valid empty `SOAPNote` (`claims=()`) → "no clinical content
  recognized": the empty-note check's recall is the vocabulary's (L165, L178), so a clinical
  paste the lexicons can't read lands here too. A *clinical* paste that comes back with zero
  claims → the `empty_note_on_clinical_input` WARNING (§8.4): total omission must not read
  green — invariant 12's law, reached by a different road.
- **No dedup / idempotency:** same paste twice = two rows. Correct for MVP; *know* it;
  caching → v2.

---

## 11. Testing strategy — tiers by determinism, not by folder

The whole-system view reveals a split the per-layer view hid. **A test's tier is decided by
whether anything stochastic sits in its path — not by what it tests, and not by which folder
its fixture lives in** (v1.3, L42).

| Tier | What | Determinism | Cost | Cadence |
|---|---|---|---|---|
| **Unit** | pure functions: the ladder, extraction, each check, `contraindication` rungs, `case_verdict` | deterministic | free | **every commit** |
| **Injected corpus** (v1.3) | every YAML case with a `draft`: ground + `run_checks` + `case_verdict`, fake `Judge` | deterministic | free | **every commit** |
| **Integration** | route + fake client/judge (`dependency_overrides`) + test DB (phase 3) | deterministic | free | **every commit** |
| **Model corpus** | `score_corpus` — real API calls over model cases, k repeats | **stochastic** | **$ × k** | **pre-deploy / manual dispatch** |

Naming this cadence split is itself a production-AI signal: evals are CI, but a *different
kind* of CI than unit tests. And the cheap tiers verify the expensive one: `case_verdict` is
unit-tested, and the injected corpus proves every check the model corpus relies on.

**The workflow file:** the free tiers run in **GitHub Actions** (`.github/workflows/ci.yml`:
`uv sync` → `ruff check` + `ruff format --check` → `mypy` → `pytest`; v1.3.3, L96) on
every push **from phase 1** (v1.3, L60 — v1.2
scheduled CI in phase 3 while CLAUDE.md said it ran on push; a green badge from the first
commit is the cheapest credibility signal in the repo). The model corpus is deliberately not
in the push workflow — it spends real money.

**Free-tier tests the spec demands** (each guards a specific bug or claim):

- **Property-based, on the index map** (`hypothesis`, with non-ASCII strategies — L26).
  v1.3 (L62) restates both properties, because v1.2's were false as written: (1) for any
  `raw_text` and any substring `q` with `q.strip()` non-empty, grounding a claim quoting `q`
  returns a span `s` with `raw_text[s[0]:s[1]] == q.strip()` — v1.2 asserted `== q`, but the
  quote is stripped, and hypothesis would find a leading space in under a second; (2) for
  every original character `ch` of any text, the normalized characters mapped to its index
  are exactly `PUNCT_MAP.get(ch, ch).lower()` (or a single space for the first character of
  a whitespace run, nothing for the rest) — stated per *original* character, so
  multi-character lowercasing can't break it.
- **Tool-schema snapshot** — `SUMMARY_TOOL["input_schema"]` against a committed JSON; any
  change to `ClaimDraft` is a reviewed diff *and* a new `PROMPT_VERSION`.
- **Orchestrator boundary (phase 1)** — fake client: happy path; a validation retry with a
  correctly shaped `tool_result` (`tool_use_id`, `is_error=True`); `max_tokens` and
  `model_context_window_exceeded` each fail fast as `OutputTruncatedError` (L88); a refusal
  with a tool block fails fast as `ModelOutputError`, and every `StopReason` value has a
  decided path (L97); every attempt carries the pinned `thinking` and `output_config` and
  no sampling parameter or `extra_body` (L181); a missing block fails fast; retries
  exhausted; usage summed across attempts; a `RunMetadata` construction error is NOT fed
  back to the model (L12).
- **HTTP mapping (phase 1)** — every §9.4 row reachable in phase 1 (L73's list), including
  504 on a client timeout, and no body ever containing exception text (L53).
- **Phase-1 boundary decisions** — each names its test where it is specified: §9.4 (L69,
  L70, L71, L73, L79, L80, L98, L99), §5.2 (L72, L75, L78), §10 (L77), §5.5 (L74),
  §9.1 (L76), §9.10 (L68).
- **Grounding** — Tiers 1–4; the numeric guard (`"BP 190/110"` vs a `130/110` source →
  `UNSUPPORTED` with its score kept); the rapidfuzz coordinate pin (L27); v1.2's
  `detect_vital_drift`, moved here (L66).
- **Extraction** — `extract_drugs("allergic to penicillin") == set()`; the four negation
  scope cases (L31); `extract_allergies("PCN allergy") == {"penicillin"}` (L30); parsed doses
  compare equal across spacing and case (L33); each `contraindication` rung (D9, D14).
- **Corpus load + coverage** — every fixture parses; every `expected_flags` entry is
  registered; every reference label reads, the raw text keeps each `must_preserve` reading,
  and adds no `must_not_add` one (L219); the §8.5 coverage rule holds.
- **Fail-closed engine** — a raising check yields `errored=True, passed=False` and the others
  still run; a severity-upgrading finding errors its check (L38); an errored expected check
  fails its case (L43); a check absent from `checks_run` makes its case N/A (L44), and so
  does a report that ran no check (L117).
- **Omission law (D17)** — for each row of the §8.4 omission table, a test that omits the
  input and asserts the stated behavior.
- **Frozen spine** — assigning to or appending to a `ClinicalClaim`'s fields raises (L6).
- **Import boundary (L188)** — an AST walk over `grounding.py`, `evals/`, `schemas.py`, and
  `tracebacks.py` finds no import of `backend.config`, `anthropic`, or `fastapi`, at module
  level or inside a function.
- **The scorer, with a fake client (L211)** — `score_corpus` over canned responses: a case
  whose `summarize` raises an `APIError` is one errored row and the others still score
  (L46); a run where every case fails still writes its record (L46); each row's usage and
  attempts come from its own path (L186) and the record's usage is their sum; a raise in
  `case_result` or the judge factory loses one row, not the run (L208); git is read before
  the first call (L207); each row keeps its draft and wall time (L201, L203); the record
  lands at `runs_path`. No network, and no git of the real tree.
- **Judge plumbing (phase 2c)** — a fake `Judge` that times out yields an errored WARNING,
  the note is returned, and `all_critical_passed` is unchanged.
- **The sink actually sinks (phase 3)** — the integration test asserts a `notes` row with the
  returned `note_id` exists after the response; §9.6's session trap would pass every other
  test in the suite.

---

## 12. The "one spine, many jobs" receipt

One data-modeling decision in the skeleton phase, propagating without re-definition:

```
SOAPNoteDraft  ──►  LLM tool contract              (orchestrator)
               ├─►  post-call validation            (orchestrator boundary)
               └─►  the phase-1 response            (unverified — and the type name says so)

SOAPNote       ──►  grounding output / source of truth
               ├─►  persistence shape                (DB, JSONB)
               ├─►  HTTP response contract           (API)
               ├─►  auto-generated OpenAPI docs       (free)
               └─►  the frontend's type source-of-truth

EvalCase       ──►  fixture answer key               (corpus authoring)
               ├─►  the per-case verdict input        (case_verdict — the answer key is
               │                                       consumed, not decorative)
               └─►  an injected draft (v1.3)          (a SOAPNoteDraft again: the tool
                                                       contract doubles as the test fixture)
```

Get the data contract right at the beginning → citations, grounding, validation,
persistence, the API, and the docs all become mechanical.

---

## 13. Repo / module structure

```
notepilot/
├── CLAUDE.md               ← Claude Code's instructions; must be at the root to auto-load (L93)
├── PROJECT_01_NOTEPILOT.md ← this spec — the header carries the version, never the filename
├── PROJECT_01_NOTEPILOT_CHANGELOG.md ← its history; every L# / D# cited here resolves there
├── pyproject.toml          ← uv project; runtime deps under [project], dev under groups ·
│                              anthropic>=1.9,<2 (L82) · [tool.mypy] strict = true (L91)
├── uv.lock                 ← the environment's source of truth
├── .github/
│   └── workflows/ci.yml    ← ruff check + format, mypy, pytest on push, FROM PHASE 1 (L96)
│                              (model corpus: manual, $)
├── backend/
│   ├── schemas.py          ← DOMAIN. the spine. imports nothing; imported by everything.
│   ├── tracebacks.py       ← DOMAIN. imports nothing. L69's frames as file:line:function (L112)
│   ├── config.py           ← operational knobs (pydantic-settings)
│   ├── orchestrator.py     ← EDGE. raw text → SummarizationResult; the LLMClient protocol ·
│   │                          get_client (L95)
│   ├── judge_client.py     ← EDGE (phase 2c). implements evals' Judge protocol over the API
│   ├── grounding.py        ← DOMAIN. SOAPNoteDraft → SOAPNote (pure, the ladder)
│   ├── clinical/           ← DOMAIN. imports nothing from the spine (L65)
│   │   ├── extract.py      ← extractors + their result types (sanctioned) — imports ONLY lexicons.py
│   │   └── lexicons.py     ← imports nothing; severities as plain strings (§7)
│   ├── evals/              ← DOMAIN
│   │   ├── registry.py     ← Check + Finding (check-internal, sanctioned) · @register_check · stamp
│   │   ├── judge.py        ← the Judge protocol — a domain interface (phase 2a, L111)
│   │   ├── checks.py       ← the §8.4 roster · contraindication() rungs · their helpers ·
│   │   │                      the reference labels' readers (§7, §8.4, L214)
│   │   ├── runner.py       ← run_checks · case_verdict · corpus_metrics · CHECKS_VERSION (pure)
│   │   ├── loader.py       ← YAML → EvalCase; validates expected_flags and reference labels
│   │   │                      (L219, L221); corpus_version()
│   │   ├── cases/          ← one YAML per case: model cases AND injected cases (§8.5)
│   │   └── runs/           ← corpus_runs.jsonl — committed from local runs (D5)
│   ├── corpus.py           ← EDGE (phase 2b, L188). score_corpus: settings · the API · git · runs/
│   ├── api.py              ← EDGE. routes (composition root) · handlers · logging · rate limit · budget
│   ├── static/index.html   ← phase 1 only: the static display (§9.10, L68); frontend/ replaces it
│   └── db.py               ← EDGE (phase 3). SessionLocal, NoteRecord, persist()
├── frontend/               ← React (phase 3): paste → SOAP view → hover-highlight + safety banner
│   └── src/api.d.ts        ← GENERATED by openapi-typescript (§9.10); never hand-edited
├── tests/                  ← unit + injected corpus + integration (deterministic, every commit)
│   ├── snapshots/tool_schema.json
│   └── ...                 ← test_orchestrator, test_api, test_grounding (incl. hypothesis),
│                              test_extract, test_checks, test_omission, test_runner,
│                              test_injected_cases, test_corpus_coverage
├── .env.example            ← committed; real .env gitignored
└── README.md               ← product layer + four-metric scorecard (n, k) + cost line + CI badge
```

**The three documents live at the root, together (v1.3.2, L93).** CLAUDE.md names the other
two by bare filename, so co-location is what makes those references resolve. The
invariants' statements live in §3.1; a spec change that adds, removes, renumbers, or
retitles one, or changes its standing instruction in CLAUDE.md, lands with CLAUDE.md's
update in one commit (L196; CLAUDE.md, "The spec and this file move together").

**The law made visible:** dependencies point *inward* toward `schemas.py`, and the
DOMAIN / EDGE labels say where a vendor's format may appear (§0). `rag/` does not exist until
phase 4 — an empty module in the tree is a promise the code hasn't made. `alembic/` joins in
phase 3 (D3). Each module lands in the phase whose exit criteria need it (§14), not before.

**Shapes outside `schemas.py` — three sanctioned exceptions, nothing else.** New pipeline
data shapes go in `schemas.py`. HTTP edge shapes (`SummarizeRequest`, `SummarizeResponse`)
live in `api.py`. Layer-internal shapes never cross a layer boundary and live in the layer
that uses them (L104): `Finding` and `Check` in `evals/registry.py`, `NormalizedText` in
`grounding.py` (§6.2), and the orchestrator's `CallConfig` (§5.2).
Extraction's result types (`Dose`, `MedStatus`, `Certainty`) live in `clinical/extract.py`
and cross into `evals/`, which imports them from there (L132): invariant 13 keeps `clinical/`
from importing the spine, so they can't live in `schemas.py`. Anything else outside
`schemas.py` is drift.

---

## 14. Build sequence (layered — the Volkswagen safeguard)

Strictly sequential. Every phase leaves something that runs end to end, and every phase has
**exit criteria** (v1.3, L61) — v1.2 had only §17, which audits the finished project, so
"is phase 1 done?" had no checklist. Every phase closes the same way: exit criteria audited
line by line, CI green, CLAUDE.md's "Current phase" line updated, and a git tag.

v1.3 (L59) splits phase 2. It held grounding, extraction, nine checks, the corpus, the
loader, the runner, lineage, and the judge — before this revision added some twenty more
items. A phase that large has no demoable midpoint: a Volkswagen inside the build sequence
itself. `run_checks` is async from 2a even though nothing awaits until 2c — free now, a
signature change across every caller later.

### Phase 1 — MVP spine · `v0.1-spine`

paste → FastAPI → LLM tool call → `SOAPNoteDraft` → display. No grounding, no DB, no evals.

```
□ paste → route → summarize → SOAPNoteDraft + RunMetadata → static-page display grouped by
  section (§9.10, L68) · SummarizeResponse is exactly {draft, metadata} (L76)
□ schemas.py holds ONLY: ClaimDraft (extra="forbid", stripped non-blank text and quote
  (L86), structural descriptions) · SOAPNoteDraft · TokenUsage · RunMetadata (every field
  produced, L11; domains, L89) · SummarizationResult — plus the Section and NonBlankStr
  aliases they use (L90)
□ orchestrator: one-line try (L12) · usage summed + validation_attempts (L13) ·
  OutputTruncatedError → 502 (L14) · PROMPT_VERSION over the full call config (L15) ·
  errors carry usage (L49) · refusal fails fast (L97)
□ prompt: D7 Assessment rule + certainty (L20) · never omit safety-critical facts (L50)
□ config.py: pinned model id (L84) · max_validation_retries + sdk_transport_retries (L5) ·
  llm_timeout_s (L54) · max_output_tokens derived via output_tokens_per_input_char, a
  property not a field (L94), validated at boot against model_max_output_tokens (L16, L72) ·
  required SecretStr key, every knob's domain (L77)
□ LLMClient Protocol with explicit kwargs (L19, L74) · typed CallConfig, temperature via
  extra_body (L82, L83) · client built once, in orchestrator.py (L78, L95) · parallel
  tool use off (L75) · orchestrator and api are EDGE (L17)
□ PHI-safe errors and logs: {error, request_id} bodies, codes not messages (L53) · 500
  logs structure only (L69) · 422 and framework bodies replaced (L70, L80, L98) · fields in
  the message (L79) · upstream attributed by status, the handler total (L71, L99)
□ tests: the orchestrator boundary list (§11) · tool-schema snapshot · every §9.4 row
  reachable in phase 1, incl. 504 (L73) · each boundary decision's named test (§11)
□ CI on push: ruff check + ruff format --check (L96) + mypy (strict, L91) + pytest (L60)
□ one live smoke run, recorded in the annotated tag (L81)
```

**Phase 1 closes with one live smoke run (L81).** Every test uses the fake client, so CI
can go green on a request the real API rejects: the tool schema's `$defs`, L75's flag, the
pinned model id, L82's `extra_body` field, and L77's key wiring are checked by mypy against
the SDK's types at best, never by the API. Before tagging `v0.1-spine`, run the app locally
and summarize one synthetic encounter (zero PHI, the same rule as `evals/cases/`) through
`GET /`. Record `model`, `prompt_version`, `validation_attempts`, and `usage` from the
response in the annotated tag message, plus `anthropic.__version__` (the SDK shapes the
wire, L82) and `models.retrieve(settings.model).max_tokens` beside
`settings.model_max_output_tokens` — the two must match (L85) — and the output throughput
(`usage.output_tokens` over the call's wall time) against §5.2's timeout bound (L185).
Before the call, check `settings.model` against the id `config.py` pins (L84, L199): the id
isn't hashed into `PROMPT_VERSION`, and the `models.retrieve` comparison reads the setting
on both sides, so an `.env` override passes both. One call, cents, confirmed by Cal before
it runs — a smoke run, not a corpus run. Repeat at any later phase close that changes the
request shape, and at every change of the pinned model (L185). 2a's close runs one although
the request shape is unchanged (L179): the response and the page are new, and real model
output meets `ground()` and `run_checks` for the first time. The tag records what it
renders; a finding it shows is recorded, not fixed. No automated test, by design: the
annotated tag is the record, audited alongside the lines above.

### Phase 2a — the safety layer, proven for free · `v0.2a-safety`

```
□ ground(): Tiers 1–4 · numeric guard · Tier 3 in normalized space (L27) · Unicode-safe
  map (L26) · scores kept on near-misses (L8) · frozen note, tuple flags (L6) · ids stamped
□ property tests restated, non-ASCII strategies (L62) · rapidfuzz coordinate pin
□ extract.py (imports only lexicons): drugs · allergies normalized (L30) · parsed doses
  (L33) · scoped negation (L31, L121) · med status (D13) · diagnoses + certainty (D12) ·
  new_prescriptions (L41)
□ lexicons.py: brand→generic · aliases · split cue classes · DRUG_CLASS (L67) · R1_GROUP
  (D9) · CROSS_REACTIVITY (D14) · NKDA ≠ NKA (D10) — each clinical entry carries its
  rationale and Cal's sign-off, in L120's form
□ registry: dict, rejects duplicates · origin · stamp() enforces downgrade-only (L38)
□ EvalResult.errored (L43) · EvalReport.checks_run + checks_version (L44, L45)
□ run_checks: async, fail-closed, judge as a parameter typed by evals/judge.py's Judge
  protocol (L111) · all_critical_passed guard
□ every reference-free check on the §8.4 roster except the judge, comparing against the
  span (L35) · the contraindication with L51 + L37
□ omission law: a docstring + a test per row of the §8.4 omission table (D17)
□ loader: YAML → EvalCase, expected_flags validated (L116)
□ case_verdict unit-tested: the v1.1 inversion · errored never satisfies (L43) · N/A (L44)
  · a report that ran no check is N/A too (L117)
□ injected corpus satisfies the coverage rule's injected clauses (L42, L137, L138) · green
  in pytest · its controls fire no check (L162)
□ route returns SOAPNote + EvalReport (production mode), no judge (L166) · still no DB
□ the page renders the note and its report, flat; the verdict read, never recomputed (L176)
□ one live smoke run, recorded in the annotated tag (L179)
```

### Phase 2b — the regression thesis goes live · `v0.2b-corpus`

```
□ v1.4 implemented before any model case (L194), then one live smoke run on the pinned
  model in L81's form: the new prompt_version, the ceiling (L85), throughput (L185)
□ ≥ 24 model cases, ≥ 6 per species, explicit species (L9) — incl.
  control_pcn_allergy_azithro, control_hedged_assessment, control_empty_assessment (L23)
□ one planted danger per trap (D16), enforced in review
□ the coverage rule's model clause, with the corpus's first model case (L137)
□ typed must_not_add, polarity-aware reference checks (L10, L36) · labels read by their
  kind's extractor, the note keeping each reading (L214–L218) and the loader validating
  them (L219) · must_preserve / must_not_add registered with requires_reference ·
  must_preserve joins detect_dropped_allergy's expected_flags (L145)
□ corpus_version, over the model cases a run scores (L116, L204)
□ config: corpus_repeats · corpus_concurrency · runs_path (L209)
□ score_corpus in corpus.py, edge (L188): concurrency · per-case catch parity, every step
  inside the try (L208), + all-failed runs recorded (L46) · k repeats + flaky_cases (D11) ·
  failed-attempt usage counted (L49), per case (L186) · each case's wall time and draft
  (L201, L203) · lineage read before the first call (L207) · python -m backend.corpus
  behind --spend (L210) · its fake-client tests (L211)
□ CorpusRunRecord: git_sha + git_dirty + checks_version (L45) · checks_config (L187) ·
  concurrency (L202) · CorpusMetrics (L3, L205, L206) · its domains (L212)
□ one baseline run on the chosen pinned model, committed with its change (D5)
□ README scorecard sentence (§2) drafted from real numbers, with n and k
```

### Phase 2c — the semantic backstop · `v0.2c-judge`

```
□ judge_client.py (edge), implementing 2a's Judge protocol (L111): one batched call (L40),
  its own call config pinned per invariant 3 (L182), judge_timeout_s (L54)
□ text_entailment_judge (D8): WARNING, needs_judge
□ judge usage → EvalReport.judge_usage → CorpusRunRecord.judge_usage (L7)
□ test: judge timeout → errored WARNING, note returned, CRITICAL verdict unchanged
□ detect_invented_assessment: diagnosis_in_quote fires with the judge off; the judge adds
  its WARNING with it on
□ corpus recorded with the judge on AND off; the difference stated in the README
```

### Phase 3 — full-stack real · `v0.3-shipped`

```
□ Postgres + Alembic (D3) · NoteRecord lineage parity (L57) · persist in its own session ·
  integration test asserts the row exists
□ React: generated api.d.ts · one highlight at a time · findings joined by claim.id ·
  banner · every §9.10 state · PHI banner above the paste box
□ deployed: persist_enabled=false · rate limit behind proxy headers (L58) · reserve-before-
  spend budget, one worker (L56) · CORS · /health · PHI-safe logging (L53)
□ README: product layer · four-metric scorecard with n and k · cost line (§5.5) · CI badge
□ the manual-dispatch corpus workflow (D5, L213): score_corpus on dispatch, its record
  uploaded as a build artifact, the key a repository secret that ci.yml never reads
□ §17 audited line by line
```

### Phase 4 — RAG deepening · `v0.4-rag`

Retrieve a reference corpus (drug interactions, guidelines) to cross-check the summary — the
retrieval muscle, a *deepening*, not MVP bloat. The spec describes it in one paragraph, so
its exit criteria begin with a design:

```
□ a minor revision: a RAG section designed and reviewed BEFORE any code (L194)
□ retrieval corpus public or licensed · zero PHI
□ each RAG-backed check placed on §8.1's trust axis (live vs CI-only) before it ships
□ retrieval quality measured on a labeled set before it gates anything · invariant 7 if an
  LLM is in the loop
```

---

## 15. v2 backlog (deliberate non-features — I know the prod version, I chose scope)

- Streaming token output (conflicts with whole-object grounding — §9.8)
- RxNorm / medspaCy / NegEx ontology-derived extraction (replaces hand lexicons — §7)
- Locality-based duplicate-quote resolution (§6.5)
- Auth, multi-tenancy, real EHR / FHIR write-back (§9.8)
- Transcript chunking for token limits (§5.4, §9.8 — until then, honest rejection)
- Dedup / idempotency / caching (§10)
- Meta-evaluation of the evaluators — checks and judge against a clinician (§8.8)
- Structured / JSON logging (§9.8)
- Additional LLM-judge checks beyond the entailment judge (§8.2)
- **Edit + sign-off persistence** — `PATCH /notes/{id}`, clinician edits, signed state. The
  product's third verb; the v1 UI is a review surface (§9.10)
- **`GET /notes/{id}`** — `note_id` in the response (§9.1) is the hook
- **Prompt caching** on the system prompt + tool schema block — changes the cost axis, not
  the architecture
- **Real auth** — the v1 rate limit + spend cap protect the wallet, not the data
- **INFO-tier checks** (section misplacement, stylistic drift) — the tier is defined (§8.6)
- **Allergy reaction-type extraction** — anaphylaxis vs rash changes the rung (D14, §8.8) (v1.3)
- **`about:` on expected flags** — matched against structured finding entities; closes the
  wrong-reason-pass gap D16 narrows (v1.3)
- **Shared budget counter + actual-usage settlement** for multi-worker deploys (§9.8, L56) (v1.3)
- **Carbapenem / aztreonam lexicon entries** — only when a corpus case needs them (D14) (v1.3)
- **Live medication-omission detection beyond new prescriptions** — only if a derivation
  trustworthy enough for §8.1 appears (§8.4) (v1.3)

---

## 16. Curriculum mapping (nothing wasted)

v1.3 (L63): the curriculum's units are **Arcs**; "Phase" means only a build phase (§14). One
word, one meaning — so "Current phase: 1" in CLAUDE.md can't be misread.

```
APIs & HTTP arc            ✓ ──► the authenticated LLM call (orchestrator)
Type Hints arc             ✓ ──► the Pydantic spine (schemas.py)
Error Handling arc         ✓ ──► the OrchestratorError hierarchy, EAFP boundary, HTTP translation
Iterators/Generators arc   ✓ ──► pipeline composition
Testing arc                ✓ ──► the tier strategy; case_verdict IS the bridge
                                  (eval = a test — fuzzy asserts over a corpus)
Web foundations arc          ──► the shell: api.py, frontend/, db.py, Alembic  (build phases 1, 3)
RAG / evals arc              ──► Layer 4, the moat (build phase 2) and its RAG deepening
                                  (build phase 4). Not Layer 2 — v1.2 mapped RAG to
                                  grounding, which retrieves nothing.
```

Every brick laid or about to be laid has a home in this thing.

---

## 17. Definition of done (portfolio-grade)

The whole project. Per-phase exit criteria live in §14.

- [ ] Pipeline runs end-to-end: paste → grounded, safety-flagged note — **persisted in the
      integration tests and a locally run instance**; the deployed demo runs with
      `persist_enabled=false` (v1.3, L64: v1.2 required "persisted" and "persistence off" of
      the same deploy)
- [ ] `schemas.py` is the only thing the domain layers import from each other;
      `clinical/extract.py` imports only `lexicons.py`, which imports nothing; vendor
      formats appear only in EDGE modules, and the domain reads no settings (L188)
- [ ] Grounding is pure + unit-tested: ladder + offset mapping (property-based, non-ASCII) +
      punctuation folding + numeric guard + normalized, word-snapped Tier 3 + flag cases
- [ ] `ClinicalClaim` and `SOAPNote` are frozen with tuple collections (D6 enforced)
- [ ] Every claim carries an `id`; every `EvalResult` carries `claim_ids`; the UI joins on it
      (both render channels demonstrable, §9.7)
- [ ] The §8.4 roster ships, the consistency checks comparing against the span; the
      omission table holds, one test per row (D17)
- [ ] Injected corpus satisfies the coverage rule and is green on every commit; ≥ 24 model
      cases, ≥ 6 per species, one YAML each; every §8.5 regression fixture present
- [ ] `case_verdict` consumes `expected_flags`, handles errored and N/A, and is unit-tested
      (incl. the inversion case: a fired expected flag = a PASS)
- [ ] `score_corpus` emits a `CorpusRunRecord` with `git_sha` + `git_dirty`,
      `checks_version`, `checks_config`, `judge_enabled`, k repeats, the four metrics,
      usage split from judge usage, and a per-(case, repeat) breakdown; survives failing
      cases; records all-failed runs; committed per D5; rerun on every prompt / model /
      check change
- [ ] `prompt_version`, `corpus_version`, `checks_version` are derived hashes;
      `settings.model` is a pinned model id, never an alias (L84)
- [ ] `all_critical_passed` guards vacuous truth; `run_checks` fails closed with `errored`
- [ ] Whole-note safety extraction (never trusts the section)
- [ ] Token usage captured per note — summed across validation attempts, judge separate —
      and persisted
- [ ] Integration test green with a fake client + fake judge + test DB (no network); asserts
      the persisted row exists
- [ ] Errors translated to honest HTTP codes (the §9.4 table, incl. 504); bodies carry codes,
      never messages; `/health` live; CORS; rate limit behind proxy headers;
      reserve-before-spend budget
- [ ] Tool-schema snapshot test committed
- [ ] GitHub Actions CI green on push since phase 1; badge in the README
- [ ] Deployed, live link, `persist_enabled=false`, PHI banner above the paste box, PHI-safe
      logs; secrets in env
- [ ] `frontend/src/api.d.ts` generated from `/openapi.json`; every §9.10 state designed
- [ ] README carries the product layer (who / what pain / v2) + the four-metric scorecard
      sentence with n and k (§2) + the cost line (§5.5) + the honest mirror's limits (§8.8)
- [ ] Clean conventional-commit git history, one tag per phase

---

*The bricks have been laid. v1.1 exists because one of them got interrogated. v1.2 exists
because the interrogation was pointed at what the checks could actually see — and found
they'd been trusting a quote to vouch for a sentence. v1.3 exists because someone walked the
whole building before moving in — and found the checks trusting the model's quote over the
source, the model's silence over the danger, and a crash over a verdict. Now the source
answers for the quote, and nothing is safe just because it's missing. 🧱⚔️◡̈*
