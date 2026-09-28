# PROJECT 01 — NotePilot

**A clinical-encounter → grounded, safety-checked SOAP summarizer.**
Flagship portfolio project. Status: **skeleton / pre-build (design locked).**
**Spec version: v1.2** (second adversarial review pass, September 2026).

> This document is the canonical build spec. It is the thing I build *against* and
> the thing a reviewer could read to understand the entire system end to end.
> Every field traces back to an origin; every check declares what it trusts; every
> layer's async and schema story agrees with its neighbors'.
>
> *However long — I arrive. However broken — I forge. So I return, and begin.* 🧱

---

## v1.2 changelog (second adversarial review deltas)

Severity uses the project's own triage enum. Each delta names the section it lands in.
Theme of this pass: **v1.1 fixed the scoring; v1.2 fixes what the checks can see.**

**CRITICAL**
- **§8.4, §8.5 — the reference-based checks now exist.** `must_preserve` /
  `must_not_add` had no consumer; the registry's `requires_reference` bit had zero
  members; omission — "the most dangerous error" — had no check. `check_must_preserve`
  and `check_must_not_add` specified. `must_preserve` entries are now typed
  (`PreserveItem`, DECISION D4) so a dropped allergy is CRITICAL and a dropped dose is
  WARNING.
- **§6, §7, §8.4 — the text-vs-quote gap closed.** Grounding proved the *quote* exists,
  not that the claim's *text* follows from it: `text="start amoxicillin"` /
  `quote="start antibiotics"` grounded clean at Tier 1. Same hole hosted negation flip
  and dose mismatch (listed in §8.6, never specified). New family of **claim-local
  consistency checks** — drugs, doses, and negated terms in `claim.text` must appear
  with the same value/polarity in `claim.source_quote`. The §7 primitives now operate
  on plain strings so one function serves text, quote, and raw source alike.
- **§6.3 — the empty quote no longer grounds clean.** `"abc".find("") == 0`: an empty
  `source_quote` earned span `(0, 0)` and no flag. The §6.5 guard now sits *before*
  Tier 1 in the code, and `ClaimDraft.source_quote` carries `min_length=1` so the
  tool schema itself rejects it.
- **§6.3 — fuzzy tier stops trusting numbers.** `"BP 130/110"` vs `"BP 190/110"`
  scored ≥ 85 → a PARAPHRASED span on the wrong vital, yellow instead of red. Tier 3
  now requires every digit token in the quote to appear verbatim in the aligned span,
  else demotes to Tier 4.
- **§7 — allergy-context exclusion.** "Allergic to penicillin" contains a drug name;
  naive `extract_drugs` fed it to the contraindication check, which then fired on every
  penicillin-allergic patient. Lexicon gains allergy-context cues as an exclusion class
  beside negation cues. The clean control that catches this regression is in the corpus.
- **§8.2, §8.7, §9.1 — the judge no longer breaks the engine.** `run_checks` was sync,
  §9.2 called evals "CPU-bound, inline," and D2 put a model call inside evals.
  `run_checks` is async; `Check` carries `severity` and `needs_client`; judge tokens
  land in `RunMetadata`.
- **§8.7 — fail closed on crashes.** One `OrchestratorError` aborted a whole corpus run
  with no record; an empty corpus divided by zero; a check that raised 500'd a
  production request. Per-case and per-check `try` boundaries; a crashed check is a
  `passed=False` result (invariant 12, applied to exceptions).

**WARNING**
- **§4.1, §4.2, §7, §9.7 — findings can anchor to claims.** Grounding stamps
  `ClinicalClaim.id`; `EvalResult.claim_ids`; extractors return mentions with their
  claim id. The two UI render channels are now derivable from the contract.
  DECISION D6: evals write to the *report*, never to `ClinicalClaim.flags`.
- **§8.7 — one name per check.** `EvalResult.check` and `fn.__name__` disagreed.
  `@register_check(name=, severity=)` stamps results; registry is a dict that rejects
  duplicates; the corpus loader validates every `expected_flags` entry against it.
- **§4.2, §5.4, §5.5, §8.7 — lineage can't lie.** `prompt_version` is a hash of the
  system prompt + tool schema; `corpus_version` a hash of the cases dir; model id is a
  dated snapshot; `CorpusRunRecord` gains `git_sha`, `judge_enabled`, token totals.
  DECISION D5: the jsonl is committed from local runs; CI dispatch uploads an artifact.
- **§8.7 — WARNING false positives are visible.** `CaseResult.unexpected_fired` (all
  severities) added as a diagnostic; the verdict stays CRITICAL-scoped and now says so.
- **§5.4 — retry policy made consistent.** Missing `tool_use` block now fails fast
  (identical retry at `temperature=0` is the same wasted spend as `max_tokens`).
  `max_tokens` coupled to `max_input_chars` in config (output copies input quotes).
- **§5.4, §9.4 — honest HTTP codes.** `OrchestratorError` split: `InputTooLongError`
  → 422, `ModelOutputError` → 502; upstream 429 → 503.
- **§9.1, §9.6 — persistence plumbing.** `persist` opens its own session (FastAPI
  ≥ 0.106 closes `yield` dependencies before background tasks run). Note `id` is
  generated in the route and returned in the response.
- **§9.8 — deployed-demo realities.** Rate limit + daily spend cap on `/summarize`;
  PHI banner + `persist_enabled` flag; the live demo is not a PHI sink.
- **§8.4 — allergy omission runs live.** `check_allergy_preserved` is reference-free:
  `allergies(raw) − allergies(note)` is a high-trust derivation by §8.1's own rule.
  `PENICILLIN_CLASS` → `ALLERGY_CLASSES` + `CROSS_REACTIVITY` with per-pair severity.
- **§9.10 (new), §15 — frontend contract + product drift.** Span rendering rule,
  UI states, `openapi-typescript`. Edit + sign-off persistence named in the backlog.

**INFO**
- **§6.3, §5.2 — magic numbers in spec code are `settings.*`.** Stated once, applied.
- **§8.4 — contraindication check reports all violations,** not the first.
- **§7 — lexicon classes are generic-only** post brand→generic normalization.
- **§8.5, §17 — corpus format (YAML per case), N set, per-species floor, coverage test.**
- **§8.7 — `score_corpus` runs cases concurrently** (`gather` + semaphore).
- **§11 — property-based round-trip on the index map; tool-schema snapshot test.**
- **§5.3 — prompt gaps closed** (contiguous span, shortest span, one fact per claim,
  negation/NKDA verbatim). **§4.1 — `grounding_score`** on PARAPHRASED claims.
- **§15 — prompt caching** added to the backlog. `timezone` import fixed.

---

## v1.1 changelog (adversarial review deltas)

Severity uses the project's own triage enum. Each delta names the section it lands in.

**CRITICAL**
- **§8.7 — corpus scoring semantics fixed.** `score_corpus` scored detection-style traps
  backwards: a fired CRITICAL flag (the pipeline *catching* the trap) counted as a case
  failure. New per-case verdict `case_passed()` consumes `expected_flags` — the answer
  key is now load-bearing, and clean controls get first-class false-positive accounting.
- **§5.4 — retry loop API contract fixed.** The correction message after a failed
  validation is now a `tool_result` block (`is_error=True`, referencing the
  `tool_use_id`). The prior plain-text user message violated the API's tool_use →
  tool_result pairing and would 400 on the first retry.
- **§4.2 — `all_critical_passed` vacuous-truth guard.** `all()` over zero CRITICAL
  results returned `True`; an unexamined note read as a safe note. Now requires at least
  one CRITICAL result to report green.
- **§8.4 — `EvalResult` instantiation fixed.** Pydantic models take keyword args only;
  the positional example crashed as written.
- **§5.4 — truncation + missing-tool-block handled.** `stop_reason == "max_tokens"` now
  raises immediately (at `temperature=0`, retrying identical input reproduces identical
  truncation — retries are wasted spend); an absent tool_use block retries instead of
  raising `StopIteration`.

**WARNING**
- **§4.1 — spine flattened.** `section` was double-encoded (a field on every claim AND
  four section-named lists — two encodings of one fact can disagree). Single encoding
  now: flat `claims` list; the `section` field is the sole source of truth; display
  groups via `by_section()`.
- **§8.7 — corpus runs are now persisted** (`evals/runs/corpus_runs.jsonl`, one
  `CorpusRunRecord` per run). The regression thesis has a queryable history for CI runs,
  not just production notes.
- **§3, §5.2 — determinism claim made honest.** `temperature=0` *minimizes variance*;
  it does not guarantee bit-identical outputs from a served API. The eval design already
  tolerates residual nondeterminism (pass-rates over a corpus, not golden-output diffs) —
  the spec now claims exactly that, no more.
- **§4.2, §5.4 — token usage captured.** `RunMetadata` carries
  `input_tokens`/`output_tokens` from `resp.usage`; the model-choice story gains a
  measured cost axis.
- **§7, §8.6 — dose extraction scoped in** (DECISION D1, vetoable). The dose-mismatch
  WARNING check had no extraction primitive; `extract_doses()` added as a
  regex/deterministic primitive.
- **§8.2, §14 — LLM-as-judge scoped** (DECISION D2, vetoable). One judge check
  (`check_assessment_support_judge`, WARNING tier, config-gated) ships in build phase 2.
- **§8.7 — check registry defined.** `evals/registry.py`: frozen `Check` dataclass +
  `@register_check` decorator. Adding a safety check is a documented one-step operation.

**INFO**
- **§9.1, §9.6 — persist is a literal sink** via FastAPI `BackgroundTasks`.
- **§9.5 — column renamed** `critical_passed` → `production_critical_passed` (per-note
  production verdict ≠ CI corpus rate; the name now says which one it is).
- **§9.8 — added:** CORS middleware, input max-length guard, logging/observability
  paragraph, migrations decision (DECISION D3: `create_all` phases 1–2 → Alembic in
  phase 3).
- **§6.2 — normalizer now delivers the §6.5 promise** (smart quotes / en-dashes mapped
  before comparison).
- **§11, §13, §14, §17 — CI made real:** GitHub Actions workflow, badge in the DoD,
  `pyproject.toml`/`uv.lock` shown in the tree (uv owns the env).
- **§4.1 — `Field(default_factory=list)`** convention for mutable defaults.

---

## 0. How to read this

The system is five layers plus a shared clinical module. Data flows in one direction:

```
raw paste ─► orchestrator ─► grounding ─► evals ─► API/persistence ─► UI
              (LLM)          (pure)       (pure+judge)   (FastAPI/PG)   (React)
                                   ▲
                          clinical/extract.py  (shared by grounding + evals)
```

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

They review, edit, sign off. That's the product.

It sits dead-center in the **ambient clinical documentation** category — the single
highest-velocity space in health AI (the ambient-scribe market did ~$600M in 2025,
~2.4× YoY). The workflow is one only someone with clinical training frames correctly.

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

> "The harness runs N synthetic encounters with deliberately planted clinical traps —
> both fidelity traps and detection traps, scored against a per-case answer key — and
> the pipeline catches X% of CRITICAL safety violations. When I change a prompt or
> drop to a cheaper model, I re-run it against the persisted run history and watch
> whether safety regressed."

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
   you can run*, not a vibe you assert. `temperature=0` minimizes output variance — it
   does not promise bit-identical replies from a served API — and the eval design
   tolerates the residual nondeterminism *by construction*: pass-rates over a corpus,
   never golden-output diffs. That tolerance is a design property, not an apology.
4. **Failure-to-ground is a signal, not an error.** A fabricated claim is the thing this
   product exists to catch. Flag it and continue; don't raise. (Contrast: an invalid
   *schema* IS an error and DOES raise — knowing which is which is the whole skill.)
5. **Scope discipline (watch the Volkswagen).** A V12 in a Volkswagen ships nothing.
   Every "real-system" refinement that isn't load-bearing for the MVP goes in the v2
   backlog (§15) — where it doubles as evidence I know the production-grade version and
   *chose* scope deliberately.

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
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum

Section = Literal["S", "O", "A", "P"]

# --- what the LLM emits: the tool contract -----------------------------------
class ClaimDraft(BaseModel):
    text: str = Field(min_length=1)
    section: Section                  # the SINGLE encoding of section membership
    source_quote: str = Field(min_length=1)
                                      # verbatim from input — the LLM emits THIS,
                                      # NOT an offset (models can't count chars).
                                      # v1.2: min_length=1 lands in the tool schema,
                                      # so the model is told; the §6.3 guard is the
                                      # second line of defense, not the first.

class SOAPNoteDraft(BaseModel):
    claims: list[ClaimDraft]          # flat. section lives on the claim, nowhere else.

# --- what grounding produces: the internal + response source of truth ---------
class SafetyFlag(str, Enum):
    UNSUPPORTED  = "unsupported"      # quote grounds nowhere → likely fabrication
    PARAPHRASED  = "paraphrased"      # matched only fuzzily → drifted, low confidence

class ClinicalClaim(ClaimDraft):                       # inherits the draft fields
    id: int                                            # v1.2: position in note.claims,
                                                       #   stamped by grounding. The
                                                       #   anchor every finding hangs on.
    source_span: tuple[int, int] | None = None         # added by grounding
    grounding_score: float | None = None               # v1.2: Tier 3 score; None for
                                                       #   exact tiers. Threshold tuning
                                                       #   needs data, not vibes.
    flags: list[SafetyFlag] = Field(default_factory=list)   # added by grounding ONLY (D6)

class SOAPNote(BaseModel):
    claims: list[ClinicalClaim]

    def by_section(self, section: Section) -> list[ClinicalClaim]:
        """Display-time grouping. Section is a rendering concern, not a storage one."""
        return [c for c in self.claims if c.section == section]
```

**DECISION D6 (v1.2, vetoable) — flag ownership is a write boundary, not just a
naming convention.** `ClinicalClaim.flags` is grounding's, full stop. Evals never
mutate a claim; they emit `EvalResult`s that *reference* claims by `id`
(`claim_ids`, §4.2). Two reasons: (1) the enriched note is persisted and returned
as-is — if evals also wrote to it, "what did grounding say?" would be unrecoverable
after the fact; (2) an eval finding can involve several claims at once (an allergy
claim *and* a prescription claim), which a per-claim flag list can't express. The
UI joins the two by `id` (§9.7, §9.10). `id` is the list index, assigned once in
`ground()`; it's stable for the life of the note because the note is immutable
after grounding.

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

class Severity(str, Enum):
    CRITICAL = "critical"    # patient-harm potential
    WARNING  = "warning"
    INFO     = "info"

class EvalResult(BaseModel):
    check: str                              # stamped by @register_check (§8.7) — the
    severity: Severity                      #   check function never spells these itself
    passed: bool
    detail: str = ""
    claim_ids: list[int] = Field(default_factory=list)
                                            # v1.2: which claims this finding is about.
                                            # [] = note-level (omission has no claim to
                                            # point at) → the banner channel (§9.7).

class EvalReport(BaseModel):
    results: list[EvalResult]

    @property
    def critical_results(self) -> list["EvalResult"]:
        return [r for r in self.results if r.severity is Severity.CRITICAL]

    @property
    def all_critical_passed(self) -> bool:
        crits = self.critical_results
        return bool(crits) and all(r.passed for r in crits)
        # bool(crits) is the vacuous-truth guard: all() over an empty list is True,
        # and "no CRITICAL check ran" must NEVER render as "safe". Absence of
        # evidence is not evidence of safety.

PreserveKind = Literal["allergy", "medication", "dose", "finding"]

class PreserveItem(BaseModel):              # v1.2 (DECISION D4): a typed expectation.
    text: str                               # the thing that must survive, e.g. "penicillin"
    kind: PreserveKind                      # severity follows kind (§8.6): allergy /
                                            #   medication / finding → CRITICAL,
                                            #   dose → WARNING. A flat list[str] could
                                            #   not say a dropped allergy and a dropped
                                            #   "TID" are different emergencies.

class EvalCase(BaseModel):                  # a synthetic fixture (zero real PHI)
    id: str
    raw_text: str
    trap: str | None                        # what's deliberately dangerous (None = clean control)
    must_preserve: list[PreserveItem] = Field(default_factory=list)  # MUST survive summarization
    must_not_add: list[str] = Field(default_factory=list)   # entities the model must NOT invent
    expected_flags: list[str] = Field(default_factory=list) # checks that SHOULD fire — consumed by
                                                            # case_passed() in §8.7. Load-bearing.
                                                            # Validated against the registry at
                                                            # corpus load (§8.5): a typo here is a
                                                            # load error, not a case that quietly
                                                            # fails forever.

class RunMetadata(BaseModel):               # threaded out of the orchestrator (+ judge)
    model: str                              # a DATED snapshot id, never an alias (§5.5)
    prompt_version: str                     # hash(system prompt + tool schema) — §5.4
    corpus_version: str | None = None       # hash(cases dir) — §8.5
    input_tokens: int | None = None         # from resp.usage — the cost axis
    output_tokens: int | None = None        #   of the model-choice story (§5.5)
    judge_input_tokens: int = 0             # v1.2: the second call is not free either;
    judge_output_tokens: int = 0            #   a cost axis blind to the judge is a lie

class SummarizationResult(BaseModel):
    draft: SOAPNoteDraft
    metadata: RunMetadata

# --- corpus run lineage (v1.1, extended v1.2) — the CI half of the regression thesis
class CaseResult(BaseModel):
    case_id: str
    passed: bool
    fired_checks: list[str]                 # every check that fired (passed=False)
    missing_expected: list[str]             # expected_flags that did NOT fire
    unexpected_fired: list[str]             # v1.2: fired but not expected, ALL severities.
                                            #   Diagnostic, not gating — a WARNING check that
                                            #   flags every clean control is visible here
                                            #   even though it doesn't fail the case.
    error: str | None = None                # v1.2: the pipeline crashed on this case.
                                            #   passed=False, and the run still completes.

class CorpusRunRecord(BaseModel):
    ran_at: datetime
    git_sha: str                            # v1.2: lineage without the code version is half
    model: str                              #   a lineage
    prompt_version: str
    corpus_version: str | None
    judge_enabled: bool                     # v1.2: the corpus runs both ways (D2); say which
    n_cases: int
    pass_rate: float
    input_tokens: int                       # v1.2: run totals — "Haiku passes at X% of
    output_tokens: int                      #   Sonnet's cost" needs the denominator
    cases: list[CaseResult]                 # per-case breakdown: debug regressions,
                                            # don't just watch a number move
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
SUMMARY_TOOL = {
    "name": "emit_soap_note",
    "description": "Return the structured SOAP summary of the encounter.",
    "input_schema": SOAPNoteDraft.model_json_schema(),   # the spine becomes the contract
}
```

### 5.2 The call (async, low-variance, forced)

```python
resp = await client.messages.create(
    model=settings.model,                                     # dated snapshot id (§5.5)
    max_tokens=settings.max_output_tokens,                    # coupled to max_input_chars
    temperature=0,                                            # minimal variance → evaluable
    system=SYSTEM_PROMPT,
    tools=[SUMMARY_TOOL],
    tool_choice={"type": "tool", "name": "emit_soap_note"},   # force the schema
    messages=messages,
)
```

- **`temperature=0`** minimizes variance so the eval suite sees stable-enough outputs;
  the corpus-level pass-rate design (§8.7) absorbs what variance remains.
- **forced `tool_choice`** means the model must populate the structure; it can't wander
  into prose.
- **async** (`AsyncAnthropic`): the LLM call is the one genuinely I/O-bound, seconds-long
  step in the system. (Reconciled across layers — the route in §9 awaits this.)
- **`max_output_tokens` is not independent of `max_input_chars` (v1.2).** The output
  is mostly *copies of the input* (every `source_quote` is a verbatim span), so output
  size scales roughly linearly with input size. `config.py` derives one from the other
  (`max_output_tokens ≈ max_input_chars / 2`, tunable) so raising the input ceiling
  can't silently create `max_tokens` truncations. Two knobs that must move together
  are one knob.

### 5.3 The system prompt — where the moat first appears in code

A generalist writes "summarize this into SOAP." The clinical version:

```
You are a clinical documentation assistant. Convert the encounter into a SOAP
note by calling emit_soap_note.

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
• Allergies and NKDA are always carried forward. Never omit an allergy.
• When uncertain, OMIT. Undergeneration is safe; fabrication is not.

SECTIONS (set each claim's `section` field)
• S — Subjective: what the patient reports (symptoms, history, complaints)
• O — Objective:  measurable findings (vitals, exam, labs)
• A — Assessment: clinical interpretation / diagnoses
• P — Plan:       orders, medications, follow-up
```

"Omit when uncertain" is a **clinical safety stance**: a missing line is recoverable; an
invented medication is a patient-safety event. The S/O/A/P definitions encode what
actually belongs where — a non-clinician gets the Assessment-vs-Plan boundary subtly
wrong and never knows.

**v1.2 additions, each aimed at a downstream layer:** *contiguous, shortest span* is
for grounding (a stitched quote can only ever reach Tier 3 or 4, so it manufactures
PARAPHRASED noise); *one fact per claim* is for extraction and anchoring (a
paragraph-sized claim makes `claim_ids` useless and lets a bad drug hide behind three
good ones); *negation verbatim* and *allergies always* are for the checks — the prompt
should try to pass the fidelity traps on purpose, and the checks exist for when it
doesn't. Prompt-level behavior and check-level detection are two layers, not one.

### 5.4 The boundary: validate, and self-correct

Tool use *steers* but does not *guarantee*. Validate at the boundary; on failure, hand the
model its own error and let it fix itself (graceful degradation around a stochastic
component — a pattern almost no pivoter portfolio shows).

**The API contract this loop must honor (v1.1):** once an assistant turn contains a
`tool_use` block, the next user message **must** answer it with a `tool_result` block
referencing the same `tool_use_id` — a plain-text correction 400s. So the validation
error travels back **through the tool-result channel**, marked `is_error=True`. That is
also the more idiomatic shape of the pattern: the model sees a failed tool execution,
not a user complaining.

```python
import hashlib, json

class OrchestratorError(Exception):
    """Base: the orchestrator could not hand over a valid draft."""

class InputTooLongError(OrchestratorError):
    """The input is the problem (truncation). Client-shaped → 422 (§9.4)."""

class ModelOutputError(OrchestratorError):
    """The model is the problem (no block / invalid after retries). Upstream-shaped → 502."""

# v1.2: the version is DERIVED, not declared. A hand-bumped "v1" string is a lineage
# that lies the first time someone edits the prompt and forgets. Hash the two things
# that actually define the call — the prompt text and the tool schema — and the
# lineage cannot drift from the code.
PROMPT_VERSION = hashlib.sha256(
    (SYSTEM_PROMPT + json.dumps(SUMMARY_TOOL, sort_keys=True)).encode()
).hexdigest()[:12]

async def summarize(raw_text: str, *, client) -> SummarizationResult:
    messages = [{"role": "user", "content": raw_text}]
    last_error: Exception | None = None

    for _ in range(settings.max_retries + 1):
        resp = await client.messages.create(
            model=settings.model, max_tokens=settings.max_output_tokens, temperature=0,
            system=SYSTEM_PROMPT, tools=[SUMMARY_TOOL],
            tool_choice={"type": "tool", "name": "emit_soap_note"},
            messages=messages,
        )

        if resp.stop_reason == "max_tokens":
            # Truncated tool input. At temperature=0 an identical retry reproduces an
            # identical truncation — retrying is pure spend. Fail fast and honest.
            raise InputTooLongError(
                "Output truncated at max_tokens — input too long for one call "
                "(transcript chunking is v2, §15)."
            )

        tool_block = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_block is None:
            # v1.2: same logic as max_tokens. Nothing in `messages` changed, so an
            # identical request at temperature=0 is an identical non-answer. The v1.1
            # `continue` here contradicted the truncation branch two lines up.
            raise ModelOutputError("Model returned no tool_use block under forced tool_choice.")

        try:
            draft = SOAPNoteDraft.model_validate(tool_block.input)     # EAFP at the boundary
            return SummarizationResult(
                draft=draft,
                metadata=RunMetadata(
                    model=settings.model,
                    prompt_version=PROMPT_VERSION,
                    input_tokens=resp.usage.input_tokens,
                    output_tokens=resp.usage.output_tokens,
                ),
            )
        except ValidationError as e:
            # This retry is NOT identical: the model now sees its own error. Worth spending.
            last_error = e
            messages += [
                {"role": "assistant", "content": resp.content},
                {"role": "user", "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "is_error": True,
                    "content": (
                        f"Validation failed: {e}. "
                        "Call emit_soap_note again with input that satisfies the schema."
                    ),
                }]},
            ]
    raise ModelOutputError(
        f"Invalid after {settings.max_retries + 1} attempts"
    ) from last_error
```

The error-handling arc, now in production: EAFP at the boundary, an exception
*hierarchy* that names the failure domain **and whose fault it is** (v1.2 — the HTTP
layer maps the subclass, not the message), `raise … from` preserving the cause. The
retry rule is now one sentence: **retry only when the next request differs from the
last one.** Truncation and a missing block don't change the request → fail fast.
A validation error feeds the model its mistake → the request changed → retry.

### 5.5 Seam & model choice

- **`client` is injected**, never imported inside the function → tests pass a fake client
  returning a canned tool-use block: no network, no key, fast, deterministic.
- **Model choice is eval-driven, not vibes — and now costed.** Start on the cheap/fast
  (Haiku) tier; run the eval suite; if a smaller model passes the clinical safety checks,
  you've *earned* the right to use it and can prove it. With `input_tokens`/
  `output_tokens` persisted per note (§4.2, §9.5), the claim upgrades from "Haiku passes
  the safety corpus" to *"Haiku passes the safety corpus at a measured fraction of
  Sonnet's cost per note."* Safety and economics, both measured.
- **`settings.model` is a dated snapshot id, never an alias (v1.2).** An alias like
  `claude-haiku-latest` can resolve to a different model next month with no diff in the
  repo — every `CorpusRunRecord.model` would then say the same thing while meaning
  different things. The regression thesis requires that the string in the lineage
  identifies exactly one set of weights. Upgrading the model is a deliberate config
  change that shows up in `git log`, next to the corpus run that justified it.

---

## 6. Layer 2 — Grounding

**Job:** `ground(draft, raw_text) -> SOAPNote`. The orchestrator *claimed* every claim has
a source; grounding **proves it** — with **zero LLM calls**, pure deterministic string
work. It constructs the enriched `ClinicalClaim` for each `ClaimDraft`.

### 6.1 The matching ladder ⭐ (the layer's keystone)

`raw_text.find(quote)` alone is **wrong**: models normalize compulsively (expand `pt`→
`patient`, fix typos, swap curly→straight quotes, collapse spaces), so an honest paraphrase
returns −1 and gets screamed at as a hallucination. The central tension of the layer:
**did the model paraphrase a real quote, or invent a fake one?** The ladder separates them:

```
Tier 1  exact substring      ─► span, no flag          (clean)
Tier 2  normalized exact      ─► span, no flag          (whitespace/case/quotes)
Tier 3  fuzzy ≥ threshold     ─► span + PARAPHRASED     (low confidence)
Tier 4  nothing ≥ threshold   ─► no span + UNSUPPORTED  (hallucination signal)
```

Tier 4 is the **first hallucination detector**, and it cost zero API calls.

### 6.2 Offset mapping (mechanics → code)

Normalizing to compare shifts every index, so a match in *normalized* space points to the
wrong place in the *original*. Keep a map back to original coordinates. (v1.1: the
normalizer now also folds the §6.5 punctuation variants — 1:1 character replacements,
so the index map is unaffected.)

```python
PUNCT_MAP = {
    "\u201c": '"', "\u201d": '"',    # curly double quotes
    "\u2018": "'", "\u2019": "'",    # curly single quotes
    "\u2013": "-", "\u2014": "-",    # en / em dash
}

def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Lowercase + collapse whitespace + fold punctuation variants,
    keeping a map: norm index -> original index."""
    out, index_map, prev_space = [], [], False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            out.append(" "); index_map.append(i); prev_space = True
        else:
            ch = PUNCT_MAP.get(ch, ch)
            out.append(ch.lower()); index_map.append(i); prev_space = False
    return "".join(out), index_map
```

**Mapping a normalized match back (the off-by-one that lives here, v1.2):** if the
normalized quote is found at `[n_start, n_end)` in the normalized source, the original
span is `(index_map[n_start], index_map[n_end - 1] + 1)` — the *last character's*
original index plus one, never `index_map[n_end]` (which may not exist, and when it does
points past collapsed whitespace). `normalized_find` owns this formula; §11's
property test (any substring round-trips to itself) is what keeps it honest.

For the fuzzy tier, use `rapidfuzz.fuzz.partial_ratio_alignment(raw_text, quote,
score_cutoff=settings.fuzzy_score_cutoff)` — it aligns the quote inside the source and
returns `src_start`/`src_end` **already in original coordinates** plus a score.
(`difflib.SequenceMatcher` is the zero-dependency, slightly rougher fallback.)

### 6.3 The ladder, assembled

```python
import re
_DIGITS = re.compile(r"\d+(?:[./]\d+)?")     # 120, 0.5, 190/110, 2.5

def _numbers_match(quote: str, span_text: str) -> bool:
    """v1.2: fuzzy is allowed to forgive letters, never digits.
    Every numeric token in the quote must appear verbatim in the aligned span."""
    span_nums = set(_DIGITS.findall(span_text))
    return all(n in span_nums for n in _DIGITS.findall(quote))

def ground_claim(draft: ClaimDraft, raw_text: str, *, claim_id: int) -> ClinicalClaim:
    quote = draft.source_quote.strip()
    base = draft.model_dump() | {"id": claim_id}

    if not quote:                                                # Tier 0 — the guard,
        return ClinicalClaim(**base, source_span=None,           # BEFORE find(): "abc".find("")
                             flags=[SafetyFlag.UNSUPPORTED])     # is 0, not -1.

    idx = raw_text.find(quote)                                   # Tier 1
    if idx != -1:
        return ClinicalClaim(**base, source_span=(idx, idx + len(quote)))

    span = normalized_find(quote, raw_text)                      # Tier 2 (uses the map)
    if span is not None:
        return ClinicalClaim(**base, source_span=span)

    align = fuzz.partial_ratio_alignment(                        # Tier 3
        raw_text, quote, score_cutoff=settings.fuzzy_score_cutoff
    )
    if align is not None and _numbers_match(quote, raw_text[align.src_start:align.src_end]):
        return ClinicalClaim(**base, source_span=(align.src_start, align.src_end),
                             grounding_score=align.score,
                             flags=[SafetyFlag.PARAPHRASED])

    return ClinicalClaim(**base, source_span=None,               # Tier 4
                         flags=[SafetyFlag.UNSUPPORTED])

def ground(draft: SOAPNoteDraft, raw_text: str) -> SOAPNote:
    return SOAPNote(claims=[
        ground_claim(c, raw_text, claim_id=i) for i, c in enumerate(draft.claims)
    ])
```

Spans are **half-open `[start, end)`** — same convention as Python slicing, so
`raw_text[start:end]` returns the quote and a whole class of off-by-one bugs disappears.

**Why the numeric guard is a clinical decision, not a string-matching one (v1.2):**
`partial_ratio("BP 130/110", "BP 190/110")` scores 89. Letters are where models
paraphrase (`pt` → `patient`); digits are where they *hallucinate* — a wrong vital, a
wrong dose, a wrong date. An 89 on a vital is not "drifted, low confidence," it is
the wrong number wearing a yellow badge instead of a red one. The ladder's job is
to separate paraphrase from invention; for numbers, any difference *is* invention.
Note the guard is deterministic string work — it lives in grounding, not evals — and
it's the first place the §3 principle ("mechanics to code") makes a *safety* call.

### 6.4 Errors-as-values, structural flags, and the eval handoff

- Grounding **almost never raises.** An ungroundable claim is a *result*, not an error
  (Principle 4). A smoke detector should not burst into flame.
- Grounding owns only **structural / provenance** flags (`UNSUPPORTED`, `PARAPHRASED`) —
  "did this come from the source at all?" The eval layer owns **clinical-semantic** flags —
  "is this set of claims medically safe?"
- **Explicit handoff (not coincidence):** the eval layer's "no hallucinated medication"
  check **consumes** grounding's `UNSUPPORTED` flag rather than re-deriving it. One layer
  establishes provenance; the next *reads* it. Two layers re-deriving the same fact can
  disagree; this can't.
- **What grounding does NOT prove (v1.2, the honest boundary):** grounding proves the
  *quote* exists in the source. It says nothing about whether the claim's *text*
  follows from that quote. `text="start amoxicillin"` / `quote="start antibiotics"`
  is a perfect Tier 1 match and a fabricated drug. That second question — is the text
  entailed by its own quote? — belongs to evals (§8.4, the claim-local consistency
  family), because answering it needs the clinical extractors, and grounding imports
  none of them. Provenance here; entailment there.

### 6.5 Edge cases (bake into tests day one)

- **Smart quotes / en-dashes** from Word (`"` `–`) — folded by `PUNCT_MAP` in §6.2;
  the tests assert it.
- **Quote longer than any clean span** (model merged two sentences) — fuzzy catches partial,
  flag low-confidence. (The v1.2 prompt now asks for contiguous, shortest spans, so
  this should be rare — the test stays because "should" is not a guarantee.)
- **Same quote appears twice** ("denies chest pain") — first-occurrence default; *know* you
  chose it.
- **Empty / whitespace-only quote** — rejected by the tool schema (`min_length=1`,
  §4.1); if one arrives anyway, the Tier 0 guard in §6.3 runs *before* `find()` and
  emits `UNSUPPORTED`. Two defenses, tests for both.
- **Fuzzy match with mismatched digits** (v1.2) — `"BP 190/110"` against a source that
  says `"BP 130/110"` → `UNSUPPORTED`, not `PARAPHRASED`. The test asserts the demotion.

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
  a false hallucination,
- **negation awareness** ("discontinue lisinopril" is NOT an active prescription; "denies
  chest pain" is NOT a positive symptom),
- **`NKDA`** ("no known drug allergies") is itself clinical information that must survive.
- **allergy-context awareness (v1.2):** "allergic to penicillin" *mentions* a drug and
  *prescribes* nothing. Without this exclusion, `extract_drugs` hands "penicillin" to
  the contraindication check, which then fires on every penicillin-allergic patient —
  a false positive on the single most important fixture in the repo. Allergy-context
  cues are a third lexicon class, beside negation cues and dose patterns.

**The primitives operate on plain strings (v1.2).** v1.1's signatures took
`list[ClinicalClaim]` / `SOAPNote`, which meant a primitive could only ever look at
one thing. The checks in §8.4 need to run the *same* extractor over three different
strings — `claim.text`, `claim.source_quote`, and `raw_text` — and compare. So:

```python
# clinical/extract.py — imports NOTHING from the rest of the project. Pure text → sets.

def extract_drugs(text: str) -> set[str]:
    """Generic drug names mentioned as active/prescribed. Brand→generic normalized.
    Excludes negated ("discontinue X", "stop X") and allergy-context ("allergic to X",
    "X allergy", "reaction to X") mentions."""

def extract_allergies(text: str) -> set[str]:
    """Allergens named in allergy context. "NKDA" → {"nkda"} — absence is information."""

def extract_doses(text: str) -> dict[str, str]:
    """drug -> dose string ("amoxicillin" -> "500 mg tid"). Number + unit + frequency
    token; regex territory. (v1.1 DECISION D1.)"""

def extract_findings(text: str) -> dict[str, bool]:
    """v1.2: finding -> polarity. "denies chest pain" -> {"chest pain": False};
    "reports chest pain" -> {"chest pain": True}. The primitive the negation-flip
    check consumes. Findings lexicon is small and corpus-driven (MVP)."""
```

Callers add the claim linkage themselves — it's one comprehension:

```python
def drug_mentions(note: SOAPNote) -> list[tuple[str, int]]:   # (drug, claim.id)
    return [(d, c.id) for c in note.claims for d in extract_drugs(c.text)]
```

This is what lets an eval finding say *which* claim (§4.2 `claim_ids`) instead of
just *that* — a `set[str]` had already forgotten.

**`clinical/lexicons.py` — the shape (v1.2):**

```python
BRAND_TO_GENERIC:  dict[str, str]          # "tylenol" -> "acetaminophen", "augmentin" -> "amoxicillin-clavulanate"
NEGATION_CUES:     set[str]                # "denies", "no", "discontinue", "stop", "d/c", "held"
ALLERGY_CUES:      set[str]                # "allergic to", "allergy", "allergies:", "reaction to", "nkda"
ALLERGY_CLASSES:   dict[str, set[str]]     # "penicillin" -> {"penicillin", "amoxicillin", "ampicillin",
                                           #                  "amoxicillin-clavulanate", "piperacillin"}
                                           # "sulfa"      -> {"sulfamethoxazole", "sulfasalazine", ...}
                                           # "nsaid"      -> {"ibuprofen", "naproxen", "ketorolac", ...}
CROSS_REACTIVITY:  dict[tuple[str, str], Severity]
                                           # ("penicillin", "cephalosporin") -> WARNING
                                           #   modern evidence: ~1–2% overall, driven by shared
                                           #   R1 side chains (cefalexin/cefadroxil with amox/ampi),
                                           #   not the old "10%" teaching. Same-class = CRITICAL;
                                           #   cross-class = the table's call. This table IS the
                                           #   clinical moat in six lines.
DRUG_CLASSES:      dict[str, str]          # "cefalexin" -> "cephalosporin" (for the cross-reactivity lookup)
DOSE_PATTERN:      re.Pattern              # number + unit + frequency token
FINDINGS:          set[str]                # "chest pain", "fever", "sob", ... (MVP: what the corpus needs)
```

All lexicon entries are **generic-only** post-normalization (v1.2): `extract_drugs`
maps brand→generic first, so a class set containing a brand name is dead weight at
best and a missed match at worst.

**MVP scope:** a small hand-curated lexicon + negation/allergy-context handling + a
dose-pattern regex + a findings list covering exactly the traps in *my* corpus.
**v2:** medspaCy / NegEx / RxNorm for robust, ontology-derived extraction.

---

## 8. Layer 4 — Evals ⭐ THE MOAT

**Job:** `await run_checks(note, raw_text, case=None, *, mode, client=None) -> EvalReport`.
Take a finished, *grounded* note and answer one question — **is this clinically safe?**
— as a verdict you can run. This is the layer a strong generalist cannot build, because
they don't know what to check for. (v1.2: async, because D2 put a model call inside it
— see §8.7.)

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

**The judge, scoped (v1.1, DECISION D2):** exactly one judge check ships in build
phase 2 — `check_assessment_support_judge`. It asks a second model call whether each
Assessment claim is *clinically supported* by its cited span (semantics grounding's
string ladder can't see: "BP 190/110" → "hypertensive urgency" grounds nowhere textually
but is sound inference — and its absence of textual grounding is exactly why a
deterministic check can't adjudicate it). WARNING tier, reference-free, gated behind
`settings.judge_enabled` so the corpus can run with and without it. This is the concrete
artifact behind the interview line above — the line needs a `git blame`-able referent.

**The judge is a network call, and the engine has to admit it (v1.2).** v1.1 declared
`run_checks` sync and §9.2 justified "evals are CPU-bound, run inline" — and then D2
put an `await client.messages.create(...)` inside evals. Both can't be true. The
resolution: `run_checks` is async; the registry marks the judge `needs_client=True`;
the route passes the same injected client it gave the orchestrator; the judge's
`usage` is added to `RunMetadata.judge_*_tokens`. The deterministic checks still run
inline inside the async function — nothing about *them* changed — but the function
that composes them now has one awaitable member, so it awaits. The §9.2 story is
amended accordingly, not contradicted.

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

### 8.4 The showpiece check (the moat, executing) + the roster

```python
@register_check(name="allergy_contraindication", severity=Severity.CRITICAL)
def check_allergy_contraindication(note, raw_text, case=None) -> list[Finding]:
    # Allergies come from the SOURCE, not just the note: a dropped allergy (§8.4,
    # allergy_preserved) is a separate finding; the contraindication is real either way.
    allergies = extract_allergies(raw_text) | {a for c in note.claims
                                               for a in extract_allergies(c.text)}
    findings: list[Finding] = []
    for drug, claim_id in drug_mentions(note):                # WHOLE note, not plan-only
        for allergen in allergies:
            if drug in ALLERGY_CLASSES.get(allergen, set()):
                findings.append(Finding(                       # v1.2: report ALL, not first
                    detail=f"{allergen} allergy on record; note prescribes {drug} "
                           f"({allergen}-class).",
                    claim_ids=[claim_id],
                ))
            elif (sev := CROSS_REACTIVITY.get((allergen, DRUG_CLASSES.get(drug, "")))):
                findings.append(Finding(
                    detail=f"{allergen} allergy on record; {drug} is "
                           f"{DRUG_CLASSES[drug]}-class (cross-reactivity risk).",
                    claim_ids=[claim_id], severity=sev,        # the table's call, not CRITICAL by default
                ))
    return findings                                            # [] = passed
```

The decorator (§8.7) turns `[]` into one `passed=True` result and a non-empty list
into one `passed=False` result per finding, each stamped with `check` and `severity`
(a finding may override severity downward, as the cross-reactivity branch does). The
check function never spells its own name — one name per check, enforced by
construction.

Catching this requires *knowing amoxicillin is a penicillin* — and knowing that a
cephalosporin on a penicillin allergy is a WARNING, not a CRITICAL, because the
~10% cross-reactivity figure everyone memorized is a 1970s artifact of contaminated
manufacturing and the modern number is ~1–2%, concentrated in shared R1 side chains.
That knowledge isn't on Stack Overflow. The fixture that tests it **is** my
background, executing.

**The roster (v1.2).** v1.1 listed severities in §8.6 and specified exactly one check.
Every check the corpus can score is now named, with what it trusts:

| check | severity | reference? | consumes | catches |
|---|---|---|---|---|
| `allergy_contraindication` | CRITICAL (table may lower) | no | `extract_allergies(raw + note)`, `drug_mentions`, `ALLERGY_CLASSES`, `CROSS_REACTIVITY` | prescribing into an allergy |
| `allergy_preserved` | CRITICAL | **no** | `extract_allergies(raw) − extract_allergies(note)` | **dropped allergy, live** |
| `hallucinated_medication` | CRITICAL | no | `claim.flags ∋ UNSUPPORTED` + `extract_drugs(claim.text)` | a drug in a claim that grounds nowhere |
| `drug_in_quote` | CRITICAL | no | `extract_drugs(claim.text) ⊆ extract_drugs(claim.source_quote)` | a drug in the text that isn't in its own quote |
| `negation_consistency` | CRITICAL | no | `extract_findings(text)` vs `extract_findings(source_quote)` polarity | "denies" → "reports" |
| `dose_consistency` | WARNING | no | `extract_doses(text)` vs `extract_doses(source_quote)` per drug | 50 mg → 500 mg |
| `assessment_support_judge` | WARNING | no (LLM) | second model call, `judge_enabled` | unsupported clinical inference (D2) |
| `must_preserve` | by `PreserveItem.kind` | **yes** | `case.must_preserve` vs `extract_*(note)` | any labeled omission |
| `must_not_add` | CRITICAL | **yes** | `case.must_not_add` vs `extract_drugs(note) ∪ extract_findings(note)` | a labeled invention |

Three things to read off the table:

1. **`allergy_preserved` is reference-free.** §8.1 said omission is reference-based
   *in general*, then gave the precise axis: how much you trust the derivation.
   "Allergic to X" / "NKDA" is about the most explicit language in a clinical note —
   `extract_allergies` over the raw text is a high-trust enumeration of one narrow
   category. So the single most dangerous omission gets a live check on real notes,
   and the *general* omission problem stays where §8.1 put it, in CI with a hand
   label. The refinement wasn't a caveat; it was a design rule, and this is it applied.
2. **The claim-local consistency family** (`drug_in_quote`, `negation_consistency`,
   `dose_consistency`) is the v1.2 keystone. Grounding proved the quote exists (§6.4);
   these prove the text doesn't say more than the quote does. Each is one extractor
   run twice and a set comparison — and each closes a hole that a Tier 1 exact match
   sailed straight through in v1.1.
3. **`must_preserve` matching rule:** an item survives if its normalized `text` is in
   the kind's extractor output over the whole note (`extract_allergies` for
   `allergy`, `extract_drugs` for `medication`, `extract_doses` values for `dose`,
   `extract_findings` keys for `finding`) — the same primitives the live checks use,
   so a fixture can't pass via a matching rule the product doesn't have. `must_not_add`
   is the mirror: any listed entity present in the note fails.

### 8.5 The synthetic corpus (`evals/cases/`) — two species of trap

Each case is a fixture carrying its own answer key (`EvalCase`, §4.2). The corpus
contains **three kinds of case**, and the runner (§8.7) scores each correctly because
it reads the answer key:

- **Fidelity traps** — test the *model's* behavior. `must_preserve` (the allergy must
  survive summarization), `must_not_add` (no invented meds). Passing means the relevant
  checks come back clean. `expected_flags: []`.
- **Detection traps** — test the *pipeline's* safety layer. The source itself contains
  the danger; a faithful summary reproduces it; the safety pass must **fire**. Passing
  means the expected flag fired. The best single fixture in the repo: a
  penicillin-allergic patient prescribed amoxicillin
  (`expected_flags: ["allergy_contraindication"]`).
- **Clean controls** — `trap: None`, `expected_flags: []`. Any CRITICAL that fires on a
  control is a false positive and fails the case — a check that flags a perfect note is
  as broken as one that misses a fabrication, and the verdict function makes that
  arithmetic, not aspiration.

The trap cases are where clinical judgment becomes the test suite; the *species
distinction* is where the scoring stays honest about what each case proves.

**Corpus mechanics (v1.2 — previously unspecified):**

- **One YAML file per case** in `evals/cases/`, loaded with `EvalCase.model_validate`.
  YAML because `raw_text` is a multi-line block and the answer key should be readable
  in a diff. Filename = `id`.
- **The loader validates the answer key against the registry.** Every entry in
  `expected_flags` must be a registered check name. A typo is a load-time error, not
  a case that fails forever and gets rationalized as "the model's fault."
- **`corpus_version` is derived**, like `prompt_version`: a hash over the sorted
  contents of `evals/cases/`. Editing a fixture changes the lineage automatically.
- **Size:** ≥ 24 cases total, ≥ 6 per species. Small enough to author by hand and
  reason about per-case; large enough that a pass-rate is a rate.
- **Coverage is unit-tested, free tier:** for every registered CRITICAL check there
  exists ≥ 1 detection trap with it in `expected_flags` and ≥ 1 clean control whose
  raw text exercises that check's extraction path (an allergy present, a drug
  prescribed, no contraindication). The corpus tests the checks; a test tests the
  corpus. A check nobody wrote a trap for is a check nobody knows works.

**The regression fixtures this pass demands** (each one is a v1.2 bug, frozen):
- `control_pcn_allergy_azithro` — penicillin allergy, azithromycin prescribed, clean.
  Fails the corpus if `extract_drugs` ever reads the allergy line as a prescription.
- `detect_drug_not_in_quote` — a claim whose text names amoxicillin and whose quote
  says "antibiotics." Tier 1 clean; `drug_in_quote` must fire.
- `detect_negation_flip` — source "denies chest pain," a claim reporting it.
- `detect_vital_drift` — source BP 130/110, claim quotes 190/110. Must be `UNSUPPORTED`,
  never `PARAPHRASED`.
- `fidelity_dropped_allergy` — allergy in source, `must_preserve: [{penicillin, allergy}]`.
  `allergy_preserved` fires live *and* `must_preserve` fires in CI: two checks, one
  omission, both correct. (`case_passed` is fine with that — see §8.7.)

### 8.6 Severity = clinical triage (the moat hiding in one enum)

```
CRITICAL   dropped allergy · hallucinated med · contraindication (same-class) · negation flip
           · drug in text absent from its quote · labeled invention
WARNING    dose mismatch · cross-class contraindication (per CROSS_REACTIVITY) ·
           unsupported assessment (judge) · dropped dose · temporal error
INFO       section misplacement · stylistic drift   (v1.2: no INFO check ships in v1 —
                                                     listed to show the tier has a meaning)
```

Triage drives everything practical: which flags interrupt the clinician, which merely
annotate, which block a deploy.

### 8.7 The dual-mode runner (one engine, two jobs) + the verdict + the lineage

**The registry (v1.1, sharpened v1.2):** checks self-register; adding a safety check is
one decorator. v1.2 changes: the name and severity are *declared once in the decorator*
and stamped onto every result (v1.1 had `EvalResult.check="allergy_contraindication"`
hand-written inside a function called `check_allergy_contraindication` — two names,
one check, and only one of them known to the registry); the registry is a dict that
refuses duplicates (pytest re-imports will hand you a doubled registry otherwise);
and a check can declare it needs the client.

```python
# evals/registry.py
from dataclasses import dataclass, field
from typing import Awaitable, Callable

@dataclass(frozen=True)
class Finding:                       # what a check RETURNS: just the facts of a violation
    detail: str
    claim_ids: list[int] = field(default_factory=list)
    severity: Severity | None = None # optional downgrade (cross-reactivity); never an upgrade

@dataclass(frozen=True)
class Check:
    name: str
    severity: Severity
    fn: Callable[..., list[Finding] | Awaitable[list[Finding]]]
    requires_reference: bool
    needs_client: bool

REGISTRY: dict[str, Check] = {}

def register_check(*, name: str, severity: Severity,
                   requires_reference: bool = False, needs_client: bool = False):
    def deco(fn):
        if name in REGISTRY:
            raise RuntimeError(f"duplicate check name: {name}")
        REGISTRY[name] = Check(name, severity, fn, requires_reference, needs_client)
        return fn
    return deco
# runner.py imports checks.py for the side effect of registration;
# checks.py imports only register_check + Finding. No cycle.
```

**The engine** (v1.2: async, fail-closed per check — production gets the
reference-free subset):

```python
async def run_checks(note, raw_text, case=None, *,
                     mode: Literal["production", "ci"], client=None) -> EvalReport:
    selected = [c for c in REGISTRY.values()
                if (mode == "ci" or not c.requires_reference)
                and (not c.needs_client or (client is not None and settings.judge_enabled))]
    results: list[EvalResult] = []
    for check in selected:
        try:
            out = check.fn(note, raw_text, case, client=client) if check.needs_client \
                  else check.fn(note, raw_text, case)
            findings = await out if inspect.isawaitable(out) else out
        except Exception:
            # v1.2: a crashed check is NOT a passed check and NOT a 500. Invariant 12
            # applied to exceptions: absence of a verdict is not a verdict of safe.
            logger.exception("check %s crashed", check.name)
            results.append(EvalResult(check=check.name, severity=check.severity,
                                      passed=False, detail="check_error"))
            continue
        if not findings:
            results.append(EvalResult(check=check.name, severity=check.severity, passed=True))
        for f in findings:
            results.append(EvalResult(check=check.name, severity=f.severity or check.severity,
                                      passed=False, detail=f.detail, claim_ids=f.claim_ids))
    return EvalReport(results=results)
```

Why `passed=False` on a crash rather than skipping: the alternative — silently
dropping the check — is exactly the vacuous-truth bug from v1.1 wearing a stack
trace. A crashed CRITICAL check in production turns the note red with
`detail="check_error"`, which is loud, honest, and fixable. A skipped one turns the
note green, which is the worst outcome this system can produce.

**The per-case verdict (v1.1 — the CRITICAL fix).** The old scorer appended
`report.all_critical_passed` per case — correct for fidelity traps, **inverted** for
detection traps, where the desired outcome is a fired flag (`passed=False`). The
showpiece penicillin fixture would have counted as a *failure* precisely when the
pipeline caught it, and the README number would have punished the pipeline for working.
The verdict now consumes the answer key:

```python
def case_passed(report: EvalReport, case: EvalCase) -> bool:
    expected = set(case.expected_flags)
    fired    = {r.check for r in report.results if not r.passed}
    return expected <= fired and all(          # every expected flag fired, AND
        r.passed
        for r in report.results                # every CRITICAL we did NOT expect
        if r.severity is Severity.CRITICAL     # to fire came back clean
        and r.check not in expected
    )
```

Read it twice — it's one boolean doing three jobs: detection traps pass when their flag
fires (`expected <= fired`), fidelity traps and clean controls pass when nothing
CRITICAL fires unexpectedly, and a false positive on a control fails the case with no
special-casing.

**The verdict is CRITICAL-scoped, on purpose, and now says so (v1.2).** An unexpected
WARNING does not fail a case — a corpus that fails on every borderline dose regex
would be a corpus nobody trusts. But invisible is not the same as tolerated:
`CaseResult.unexpected_fired` records every unexpected fire at every severity, so
"the dose check flags 40% of clean controls" is a number you can see in the run
record even though it doesn't move the pass rate. Gate on CRITICAL; *watch*
everything.

(Note the `fidelity_dropped_allergy` fixture in §8.5: `allergy_preserved` fires live
and `must_preserve` fires in CI. Two CRITICALs, `expected_flags: []`, case fails —
correctly, because the model dropped the allergy. If instead the fixture is authored
as a detection trap with both names in `expected_flags`, it passes when both fire.
The answer key decides which question the case asks. That's the point of having one.)

**The scorer, with lineage (v1.1, hardened v1.2):** a corpus run is an *event with
provenance*, not a number that scrolls away. Every run produces a `CorpusRunRecord`
— "did safety regress when I switched models?" becomes a query over history for CI
runs, exactly as §9.5 already made it for production notes.

v1.2 fixes three ways the v1.1 scorer could fail to produce a record at all: one
`OrchestratorError` on one case unwound the whole run; an empty corpus divided by
zero; and the sequential `await` made a 24-case run take 24× one call.

```python
async def score_corpus(cases: list[EvalCase], *, client) -> CorpusRunRecord:
    if not cases:
        raise ValueError("empty corpus — refusing to emit a 100% pass rate over nothing")

    sem = asyncio.Semaphore(settings.corpus_concurrency)

    async def run_one(case: EvalCase) -> tuple[CaseResult, RunMetadata | None]:
        async with sem:
            try:
                result = await summarize(case.raw_text, client=client)
                note   = ground(result.draft, case.raw_text)
                report = await run_checks(note, case.raw_text, case, mode="ci", client=client)
            except OrchestratorError as e:
                # v1.2: a case the pipeline can't even summarize is a FAILED case
                # with a reason, not an aborted run. The other 23 still count.
                return CaseResult(case_id=case.id, passed=False, fired_checks=[],
                                  missing_expected=sorted(case.expected_flags),
                                  unexpected_fired=[], error=repr(e)), None
        expected = set(case.expected_flags)
        fired    = {r.check for r in report.results if not r.passed}
        return CaseResult(
            case_id=case.id,
            passed=case_passed(report, case),
            fired_checks=sorted(fired),
            missing_expected=sorted(expected - fired),
            unexpected_fired=sorted(fired - expected),
        ), result.metadata

    pairs = await asyncio.gather(*(run_one(c) for c in cases))
    case_results = [cr for cr, _ in pairs]
    metas        = [m for _, m in pairs if m is not None]
    if not metas:
        raise RuntimeError("every case failed before summarization — no lineage to record")

    record = CorpusRunRecord(
        ran_at=datetime.now(timezone.utc),
        git_sha=current_git_sha(),                       # env in CI, `git rev-parse` locally
        model=metas[0].model,                            # constant across the run
        prompt_version=metas[0].prompt_version,
        corpus_version=corpus_version(cases),            # hash of the fixtures
        judge_enabled=settings.judge_enabled,
        n_cases=len(case_results),
        pass_rate=sum(c.passed for c in case_results) / len(case_results),
        input_tokens=sum(m.input_tokens or 0 for m in metas)
                     + sum(m.judge_input_tokens for m in metas),
        output_tokens=sum(m.output_tokens or 0 for m in metas)
                      + sum(m.judge_output_tokens for m in metas),
        cases=case_results,
    )
    append_jsonl(settings.runs_path, record)             # the lineage
    return record
```

**DECISION D5 (v1.2, vetoable) — where the lineage lives.** A `.jsonl` appended on a
GitHub Actions runner is deleted with the runner. Two honest options: (a) corpus runs
happen locally, `corpus_runs.jsonl` is committed alongside the change that prompted
them (the run record and the prompt/model diff land in the *same commit* — that's a
strong story); (b) the manual-dispatch workflow uploads the record as a build
artifact and a small script pulls artifacts into the jsonl. **Chosen: (a) for v1**,
with the workflow uploading an artifact as a backup. Reason: the run is already a
deliberate, paid, human-triggered act; making the human also `git add` the receipt
costs nothing and puts the evidence next to the claim. `git_sha` in the record makes
either option queryable later.

- **production:** the reference-free subset runs on every real note → a **live safety
  layer**; its CRITICAL flags are the red badges in the UI.
- **ci:** the full suite runs across the synthetic corpus → a **scorecard with a
  per-case breakdown** (`missing_expected` tells you *which* trap slipped, not just
  that the number moved).

Same code, two masters. The eval harness was never a testing afterthought — it's a core
component that happens to run in two modes, and it's what makes the model-choice and
prompt-change decisions evidence-based.

### 8.8 Honest mirror (state this, don't hide it)

Clinical-semantic evaluation is **genuinely unsolved at the frontier.** The LLM-judge checks
have their own false-positive/false-negative rates; a truly rigorous version would
*meta-evaluate the evaluators* (do the checks agree with a human clinician?). Don't oversell
the harness as bulletproof. The strength isn't claiming I solved clinical safety — it's
understanding the problem deeply enough to know I *haven't*, and building honest guardrails
anyway. That humility reads as more senior than any accuracy number.

---

## 9. Layer 5 — API + persistence

Less *conceptual* weight than the layers above; its value is **craft and credibility.**
This is where the project reads as "shipped software" vs "school assignment," and the
difference is entirely the boring stuff done right. It's Phase 2 material (FastAPI, SQL)
doing load-bearing work.

### 9.1 The route is a composition root (no logic lives here)

```python
class SummarizeRequest(BaseModel):          # HTTP-boundary shape; lives in api.py
    raw_text: str = Field(
        min_length=settings.min_input_chars,    # degenerate-input guard (§10)
        max_length=settings.max_input_chars,    # v1.1: oversized paste fails honestly
    )                                            # at validation (422), not as a
                                                 # confusing token-limit error mid-call.
                                                 # Chunking stays v2.

class SummarizeResponse(BaseModel):
    note_id: UUID                            # v1.2: minted HERE, before persist runs —
    note: SOAPNote                           #   the client can reference what it just got
    report: EvalReport
    metadata: RunMetadata                    # v1.2: model / prompt_version / tokens visible
                                             #   to the UI and to anyone curl-ing the demo

@app.post("/summarize", response_model=SummarizeResponse)
async def summarize_endpoint(
    req: SummarizeRequest,
    background_tasks: BackgroundTasks,
    client = Depends(get_client),
):
    note_id = uuid4()
    result = await summarize(req.raw_text, client=client)                     # orchestrator
    note   = ground(result.draft, req.raw_text)                               # grounding
    report = await run_checks(note, req.raw_text, mode="production",          # evals (live subset)
                              client=client)                                  #   client: for the judge
    background_tasks.add_task(persist, note_id, req.raw_text, note, report, result.metadata)
    return SummarizeResponse(note_id=note_id, note=note, report=report,       # sink runs AFTER this
                             metadata=result.metadata)
```

A handful of lines that wire the pipeline in order. **The thinness is the signal** — a
six-line route instead of a 200-line god-handler is the visual proof of "dependencies point
inward." (v1.1: `persist` rides a `BackgroundTask`, so "the sink runs after the response"
is now literally true in the framework's execution order, not a discipline the route
promises to keep — see §9.6.) (v1.2: the id is minted in the route, not by the DB
default — the response has to carry it, and the response is built before the row
exists. `NoteRecord.id` loses its `default=uuid4` accordingly.)

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

### 9.4 Error translation at the HTTP boundary

```
InputTooLongError        → 422   the INPUT is the problem (truncated at max_tokens)
ModelOutputError         → 502   the MODEL is the problem (no block / invalid after retries)
Anthropic RateLimitError → 503   upstream is throttling; Retry-After if the SDK exposes it
Anthropic APIError       → 502   upstream provider failed (not my bug)
unexpected Exception     → 500   logged in full internally, generic message out
```

```python
@app.exception_handler(InputTooLongError)
async def handle_input_too_long(request, exc):
    return JSONResponse(status_code=422,
                        content={"error": "input_too_long", "detail": str(exc)})

@app.exception_handler(ModelOutputError)
async def handle_model_output_error(request, exc):
    return JSONResponse(status_code=502,
                        content={"error": "model_output_invalid", "detail": str(exc)})
```

The route never leaks a stack trace; it speaks HTTP semantics. 422-vs-502 says *different
true things about whose fault it was* — which is why v1.2 split `OrchestratorError`
(§5.4): v1.1 mapped *all* of it to 422, so a model that returned garbage three times
was reported as the client's malformed request. That's a lie in a status code, and the
spec's own standard for this section is honesty about fault.

### 9.5 Persistence: hybrid relational-envelope + JSONB

A SOAP note is a **document-shaped aggregate** — read and written whole; you never query
"every claim across all notes where section='A'." Normalizing into a claims table builds
query power you have no query for (Volkswagen). So: relational envelope, JSONB payload.

```python
class NoteRecord(Base):
    __tablename__ = "notes"
    id                        = Column(UUID, primary_key=True)   # v1.2: minted in the route (§9.1)
    created_at                = Column(DateTime, server_default=func.now())
    raw_text                  = Column(Text)
    model_used                = Column(String)      # ← regression metadata
    prompt_version            = Column(String)      # ← regression metadata
    input_tokens              = Column(Integer)     # ← v1.1: the cost axis (§5.5)
    output_tokens             = Column(Integer)
    production_critical_passed = Column(Boolean)    # ← v1.1 rename: PER-NOTE verdict from
                                                    #   the PRODUCTION (reference-free) mode
    note                      = Column(JSONB)       # ← the whole validated SOAPNote
    report                    = Column(JSONB)       # ← the whole EvalReport
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
- **note-level findings** (`EvalResult` with `claim_ids == []`: omissions, a crashed
  check, the dropped allergy that has no claim to hang on) → a **top-of-note safety
  banner.**

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
- **Logging / observability** (v1.1) — stdlib `logging` configured once in `api.py`:
  per-request id, model, latency, token counts. "Logged in full internally" (§9.4) now
  has a referent. Structured/JSON logging → v2.
- **Migrations** (v1.1, DECISION D3) — `Base.metadata.create_all` for build phases 1–2
  (schema churn is high, data is disposable); **Alembic adopted in phase 3** when
  Postgres becomes real and the schema stabilizes. The ladder is the decision: create_all
  isn't a gap, it's a phase.
- **Secrets** — API key in env, never in code (`.env` gitignored, `.env.example` committed —
  the reflex carries over from the APIs arc; matters more here, clinical-adjacent).
- **Oversized transcripts** → rejected honestly at the boundary via `max_length` (§9.1);
  chunking to *accept* them → v2.
- **The wallet (v1.2).** A deployed `/summarize` with no auth and a paid API key
  behind it is a denial-of-wallet endpoint. Minimum viable defense, both required:
  a per-IP rate limit (`slowapi`, a few requests/minute) *and* a daily spend cap
  enforced in code (`settings.daily_token_budget`; a counter in the DB or in-process;
  when exhausted the route returns 503 `budget_exhausted` and the README says so).
  Neither is "auth" (v2). Both are what a reviewer from a health-AI company will
  check for within thirty seconds of seeing a live link.
- **The paste box is a PHI intake (v1.2).** The repo has zero real PHI. The *deployed
  demo* has a text box, and someone will paste a real note into it. Two consequences:
  (1) the UI carries a visible "synthetic / de-identified text only — this is a demo,
  not a HIPAA environment" banner above the box; (2) `settings.persist_enabled`
  exists and the public demo runs with it **off** — the pipeline runs, the note is
  returned, nothing is written. Persistence is demonstrated in the integration tests
  and in a locally-run instance, not by accumulating strangers' clinical text on a
  free-tier Postgres. Knowing to make that call is the clinical-adjacent judgment
  the whole project is supposed to prove.

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
  `/openapi.json` and emits `frontend/src/api.d.ts`. `SOAPNote`, `EvalReport`,
  `SummarizeResponse` exist exactly once, in `schemas.py`; the TypeScript is a build
  artifact. That's what makes the §12 receipt's last line true rather than aspirational.
- **One highlight at a time.** Spans can overlap (two claims from one sentence) and
  coincide (the duplicate-quote case, §6.5). The UI never paints all spans onto the
  source at once — it highlights the span of the claim under the cursor (or the one
  clicked), and nothing else. This sidesteps overlap rendering entirely and matches
  the product motion (§1: "hover → highlight"). A claim with `source_span: None`
  highlights nothing and shows its `UNSUPPORTED` badge; that absence *is* the signal.
- **Findings join by `claim.id`.** The claim card shows grounding flags plus every
  `EvalResult` whose `claim_ids` contains its id; the banner shows every result with
  `claim_ids == []`. The UI does no clinical reasoning; it renders two lists.
- **Five states, all designed:** loading; result; empty (`claims == []` → "no
  clinical content found," §10); 422 input error (message from `detail`); 502/503
  upstream error ("the model didn't produce a valid note — try again"). No state
  is a blank page or a raw JSON dump.
- **Read-only in v1.** "Review, edit, sign off" (§1) is the product; edit and
  sign-off *persistence* is v2 (§15) — the v1 UI is a review surface. Naming that
  here is what makes it a decision instead of an omission.
- **The PHI banner** (§9.8) is above the paste box, always, not a dismissible toast.

---

## 10. Cross-cutting concerns

- **`config.py` (pydantic-settings):** centralize operational knobs — `model` (dated
  id), `max_input_chars` → derived `max_output_tokens`, `fuzzy_score_cutoff`,
  `max_retries`, `min_input_chars`, `judge_enabled`, `persist_enabled`,
  `corpus_concurrency`, `daily_token_budget`, `rate_limit`, `runs_path`, CORS
  origins. Clinical lexicons live in `clinical/lexicons.py`. Kills the magic-number
  smell. (v1.2: the literal `85`, `2000`, and `2` in this spec's code samples are
  `settings.*` in the repo — a spec that bans magic numbers and then prints them is
  a spec whose examples aren't the code.)
- **Degenerate input:** empty / non-clinical `raw_text` ("hello") → a valid *empty*
  `SOAPNote` (`claims=[]` — one empty list on the v1.1 spine) + a defined UI state
  ("no clinical content found") + the min/max-length guard at the route (§9.1). Define
  the zero-claim path so it's graceful, not surprising.
- **No dedup / idempotency:** same paste twice = two rows. Correct for MVP; *know* it;
  caching → v2.

---

## 11. Testing strategy — three tiers, three clocks

The whole-system view reveals a split the per-layer view hid:

| Tier | What | Determinism | Cost | Cadence |
|---|---|---|---|---|
| **Unit** | pure functions: grounding ladder, individual eval checks, extraction, `case_passed` | deterministic | free | **every commit** |
| **Integration** | route + fake client (`dependency_overrides`) + test DB | deterministic | free | **every commit** |
| **Eval-corpus** | `score_corpus` — real API calls over synthetic traps | **stochastic** | **$** + slow | **pre-deploy / nightly, manual trigger** |

Naming this cadence split is itself a production-AI signal: evals are CI, but a *different
kind* of CI than unit tests, and the architecture accounts for it. The eval-corpus run is
the gate that answers "did safety regress?" before a deploy.

**The workflow file (v1.1):** the first two tiers run in **GitHub Actions**
(`.github/workflows/ci.yml`: `uv sync` → `pytest` → `mypy`) on every push. The corpus
tier is deliberately NOT in the push workflow — it spends real money; it runs on manual
dispatch / pre-deploy. The green badge in the README is the cheapest "shipped software"
signal in the repo. And note the pleasing symmetry: `case_passed` is itself unit-tested
in the free tier — the verdict logic that scores the expensive tier is verified by the
cheap one.

**Free-tier tests the v1.2 review demanded** (each guards a specific bug this pass
found or a claim this spec makes):

- **Property-based, on the index map** (`hypothesis`): for any `raw_text` and any
  non-empty substring `q` of it, `ground_claim(q)` returns a span `s` with
  `raw_text[s[0]:s[1]] == q` at Tier 1; and for any text, `normalize_with_map` maps
  every normalized index back to an original index whose character normalizes to the
  same thing. Two properties, thousands of generated cases, zero hand-written
  fixtures — the round-trip formula in §6.2 either holds or it doesn't.
- **Tool-schema snapshot:** `SUMMARY_TOOL["input_schema"]` is compared to a committed
  JSON file. Any change to `ClaimDraft` shows up as a reviewed diff *and* changes
  `prompt_version` (§5.4). Schema drift is loud twice.
- **Corpus coverage** (§8.5): every registered CRITICAL check has a detection trap
  and an exercising control. Runs on every commit; costs nothing; fails when a check
  is added without a fixture.
- **Corpus load:** every fixture parses as `EvalCase`; every `expected_flags` entry
  is a registered name.
- **Fail-closed engine:** a check that raises yields `passed=False, detail="check_error"`
  and the other checks still run. Empty corpus → `ValueError`.
- **The sink actually sinks:** the integration test asserts a `notes` row with the
  returned `note_id` exists after the response — the §9.6 session trap would pass
  every other test in the suite.
- **Numeric guard:** `"BP 190/110"` against a `130/110` source → `UNSUPPORTED`.
- **Allergy-context exclusion:** `extract_drugs("allergic to penicillin") == set()`.

---

## 12. The "one spine, many jobs" receipt

One data-modeling decision in the skeleton phase, propagating without re-definition:

```
SOAPNoteDraft  ──►  LLM tool contract              (orchestrator)
               └─►  post-call validation            (orchestrator boundary)

SOAPNote       ──►  grounding output / source of truth
               ├─►  persistence shape                (DB, JSONB)
               ├─►  HTTP response contract           (API)
               ├─►  auto-generated OpenAPI docs       (free)
               └─►  the frontend's type source-of-truth

EvalCase       ──►  fixture answer key               (corpus authoring)
               └─►  the per-case verdict input        (case_passed — v1.1: the answer
                                                       key is consumed, not decorative)
```

Get the data contract right at the beginning → citations, grounding, validation,
persistence, the API, and the docs all become mechanical.

---

## 13. Repo / module structure

```
notepilot/
├── pyproject.toml          ← uv project; runtime deps under [project], dev under groups
├── uv.lock                 ← the environment's source of truth
├── .github/
│   └── workflows/ci.yml    ← unit + integration on push (corpus tier: manual, $)
├── backend/
│   ├── schemas.py          ← the spine. imports nothing; imported by everything.
│   ├── config.py           ← operational knobs (pydantic-settings)
│   ├── orchestrator.py     ← raw text → SummarizationResult (async, tool use)
│   ├── grounding.py        ← SOAPNoteDraft → SOAPNote (pure, the ladder)
│   ├── clinical/
│   │   ├── extract.py      ← extract_drugs / _allergies / _doses / _findings — pure str → set;
│   │   │                       imports nothing (v1.2)
│   │   └── lexicons.py     ← BRAND_TO_GENERIC, NEGATION_CUES, ALLERGY_CUES, ALLERGY_CLASSES,
│   │                           CROSS_REACTIVITY, DRUG_CLASSES, DOSE_PATTERN, FINDINGS (§7)
│   ├── evals/
│   │   ├── registry.py     ← Check + Finding dataclasses, @register_check(name=, severity=) (v1.2)
│   │   ├── checks.py        ← the §8.4 roster, one function per check (self-registering)
│   │   ├── runner.py        ← run_checks (async, dual-mode, fail-closed) + case_passed + score_corpus
│   │   ├── loader.py        ← v1.2: YAML → EvalCase; validates expected_flags; corpus_version()
│   │   ├── cases/           ← one YAML per synthetic encounter: fidelity traps, detection traps,
│   │   │                       clean controls (§8.5)
│   │   └── runs/            ← corpus_runs.jsonl — committed from local runs (D5)
│   ├── rag/                 ← phase 4 only; directory does not exist until then (v1.2 — an
│   │                           empty module in the tree is a promise the code hasn't made)
│   ├── api.py               ← FastAPI routes (composition root) + logging + rate limit
│   └── db.py                ← persistence (sink) — SessionLocal, NoteRecord, persist()
├── frontend/                ← React: paste → SOAP view → hover-highlight + safety banner
│   └── src/api.d.ts         ← GENERATED by openapi-typescript (§9.10); never hand-edited
├── tests/                   ← unit + integration (deterministic, every commit)
│   ├── snapshots/tool_schema.json   ← §11 schema snapshot
│   └── ...                          ← test_grounding (incl. hypothesis), test_extract,
│                                       test_checks, test_runner, test_corpus_coverage, test_api
├── .env.example            ← committed; real .env gitignored
└── README.md               ← the product layer (who/what-pain/v2) + scorecard + CI badge
```

**The law made visible:** dependencies point *inward* toward `schemas.py`. The domain knows
nothing about FastAPI, Postgres, or Anthropic. (Alembic's `alembic/` directory joins the
tree in phase 3 — see §9.8, D3.)

---

## 14. Build sequence (layered — the Volkswagen safeguard)

1. **MVP / the spine.** paste → FastAPI endpoint → LLM tool call → `SOAPNoteDraft` back →
   display. No grounding, no DB, no evals. Proves the loop runs. *(Closest to done — the
   authenticated Anthropic call already exists from the APIs arc; this is that brick + a
   route + a render.)*
2. **Grounding + the eval harness.** The matching ladder (with the Tier 0 and numeric
   guards); `clinical/extract.py` on plain strings; the full §8.4 roster — the
   contraindication check with its cross-reactivity table, `allergy_preserved`, the
   three claim-local consistency checks, `must_preserve` / `must_not_add`; the
   synthetic corpus (all three case species + the five v1.2 regression fixtures,
   §8.5) + loader + coverage test + `case_passed` + hardened `score_corpus` + run
   lineage (D5); the one scoped judge check behind its config flag (D2), which is
   what makes `run_checks` async. **The moat walks in here** — and in v1.2 it walks
   in with nine named checks instead of one.
3. **Full-stack real.** Postgres persistence (Alembic adopted here — D3), the React
   review UI (inline highlights + safety banner), GitHub Actions CI + badge, deployed
   with a live link.
4. **RAG deepening.** Retrieve a reference corpus (drug interactions, guidelines) to
   cross-check the summary. The retrieval muscle — a *deepening*, not MVP bloat.

---

## 15. v2 backlog (deliberate non-features — I know the prod version, I chose scope)

- Streaming token output (conflicts with whole-object grounding — §9.8)
- RxNorm / medspaCy ontology-derived extraction (replaces hand lexicons — §7)
- Locality-based duplicate-quote resolution (§6.5)
- Auth, multi-tenancy, real EHR / FHIR write-back (§9.8)
- Transcript chunking for token limits (§5.4, §9.8 — until then, honest rejection)
- Dedup / idempotency / caching (§10)
- Meta-evaluation of the evaluators (§8.8)
- Structured / JSON logging (§9.8)
- Additional LLM-judge checks beyond the scoped one (§8.2)
- **Edit + sign-off persistence** — `PATCH /notes/{id}`, clinician edits, signed
  state. The product's third verb; the v1 UI is a review surface (§9.10) (v1.2)
- **`GET /notes/{id}`** — retrieval of a persisted note; `note_id` in the response
  (§9.1) is the hook, the read path is v2 (v1.2)
- **Prompt caching** on the system prompt + tool schema block — identical on every
  call; measurable input-token reduction; changes the cost axis but not the
  architecture (v1.2)
- **Real auth** — the v1 rate limit + spend cap (§9.8) protect the wallet, not the
  data; per-user auth arrives with the persistence story (v1.2)
- **INFO-tier checks** (section misplacement, stylistic drift) — the tier is
  defined, no check ships in v1 (§8.6) (v1.2)

---

## 16. Curriculum mapping (nothing wasted)

```
APIs & HTTP arc            ✓ ──► the authenticated LLM call (orchestrator)
Type Hints arc             ✓ ──► the Pydantic spine (schemas.py)
Error Handling arc         ✓ ──► OrchestratorError, EAFP boundary, HTTP translation
Iterators/Generators       ✓ ──► pipeline composition
Testing arc                ✓ ──► the three-tier strategy; case_passed IS the bridge
                                  (eval = a test — fuzzy asserts over a corpus)
Phase 2: FastAPI/React/SQL ──► the shell (api.py, frontend/, db.py, Alembic)
Phase 3: RAG / evals       ──► layers 2 (deepening) and 4 (the moat)
```

Every brick laid or about to be laid has a home in this thing.

---

## 17. Definition of done (portfolio-grade)

- [ ] Pipeline runs end-to-end: paste → grounded, safety-flagged, persisted note
- [ ] `schemas.py` is the only thing the domain layers import from each other;
      `clinical/extract.py` imports nothing at all
- [ ] Grounding is pure + unit-tested: ladder + offset mapping (property-based) +
      punctuation folding + Tier 0 empty guard + numeric guard + flag cases
- [ ] Every claim carries an `id`; every `EvalResult` carries `claim_ids`; the UI joins
      on it (both render channels demonstrable, §9.7)
- [ ] The §8.4 roster ships: contraindication (with cross-reactivity table),
      `allergy_preserved` live, the three claim-local consistency checks,
      `must_preserve` / `must_not_add` in CI, the judge behind its flag
- [ ] Eval corpus: ≥ 24 cases, ≥ 6 per species, one YAML each; loader validates
      `expected_flags`; coverage test green; the five v1.2 regression fixtures present
- [ ] `case_passed` consumes `expected_flags` and is itself unit-tested (incl. the
      inversion case: a fired expected flag = a PASS); `unexpected_fired` recorded
- [ ] `score_corpus` emits a `CorpusRunRecord` with `git_sha`, `judge_enabled`, token
      totals, per-case breakdown incl. `error`; survives a failing case; refuses an
      empty corpus; record committed per D5; reruns on prompt/model change
- [ ] `prompt_version` and `corpus_version` are derived hashes; `settings.model` is a
      dated snapshot id
- [ ] `all_critical_passed` guards vacuous truth (zero CRITICAL results ≠ green);
      `run_checks` fails closed on a crashed check
- [ ] Whole-note safety extraction (never trusts the section)
- [ ] Token usage captured per note incl. judge tokens (`input_tokens`/`output_tokens`
      persisted)
- [ ] Integration test green with a fake client + test DB (no network); asserts the
      persisted row exists (`note_id` from the response)
- [ ] Errors translated to honest HTTP codes (422 input / 502 model / 503 throttled);
      `/health` endpoint live; CORS configured; rate limit + daily spend cap live
- [ ] Tool-schema snapshot test committed
- [ ] GitHub Actions CI green on push (unit + integration); badge in README
- [ ] Deployed, live link, `persist_enabled=false`, PHI banner above the paste box;
      secrets in env
- [ ] `frontend/src/api.d.ts` generated from `/openapi.json`; five UI states designed
- [ ] README carries the product layer (who / what pain / v2) + the scorecard sentence
      (v1.1 wording: species-aware, lineage-backed) + the cost line (§5.5)
- [ ] Clean conventional-commit git history

---

*The bricks have been laid. v1.1 exists because one of them got interrogated. v1.2
exists because the interrogation was pointed at what the checks could actually see —
and found they'd been trusting a quote to vouch for a sentence. Now the sentence
answers for itself. 🧱⚔️◡̈*
