# CLAUDE.md — NotePilot

Clinical-encounter → grounded, safety-checked SOAP summarizer. Flagship portfolio
project. FastAPI + Postgres + React; Anthropic API via tool use.

## Source of truth

`PROJECT_01_NOTEPILOT_v1_3.md` (v1.3 — design-room walkthrough, September 2026) is the
canonical build spec. It supersedes v1.2 and wins every conflict — including conflicts
with this file and with in-session requests.

- Before implementing anything, check the relevant spec section. Cite it ("§6.1", "D12",
  "L35") when explaining a decision.
- If a request deviates from the spec, **flag the deviation before writing code** and
  ask whether we're amending the spec or the request. Never silently drift.
- If the spec itself seems wrong or has a gap, say so directly. Cal has upgraded specs
  before (the cross-reactivity gap in the testing capstone; the v1.3 walkthrough found
  five CRITICALs); finding flaws is welcome, hiding them is not.
- **The spec and this file move together.** A spec revision that touches an invariant, a
  module boundary, or the phase list lands in the same commit as this file's update.

## Working relationship

Cal is the author of record and a capable engineer; Claude Code is a full collaborator
with no restricted zones. There is no "moat layer" gating and no builder mode —
write code anywhere in the repo (`evals/`, `clinical/`, `grounding.py` included) when
asked.

- **Read the request, do that thing.** Cal decides per request whether he wants a
  design discussion, a review, a walkthrough, scaffolding, or full implementation.
  Don't hedge an implementation request into an explanation, and don't pre-empt a
  discussion request with code.
- **Never unsolicited.** Don't write or change code outside the scope of the current
  request. If something adjacent needs doing, flag it and let Cal decide.
- **Clinical reasoning stays visible.** The moat is Cal's clinical judgment rendered as
  code, and it's his to manage — not a reason to withhold help. When writing clinical
  logic (lexicon entries, drug-class membership, severity assignments, check
  semantics), state the clinical rationale alongside the code so each call is an
  explicit decision on the record, not a silent default.
- **Clinical defaults need Cal's sign-off.** D9 (R1 side-chain rungs) and D14 (the
  unspecified-penicillin rule) are evidence-based defaults drafted in the design room.
  When authoring `clinical/lexicons.py`, write each entry with its rationale in a comment
  and flag it for Cal's review. A spec default is not a clinical sign-off.
- **Standing order: nitpick everything.** Style, naming, edge cases, design smells.
  Cal explicitly wants this. Review with senior-engineer rigor, not politeness.

## Architectural invariants (never violate, flag any code that does)

1. **Dependencies point inward at `schemas.py`; vendors stay at the edge.** `schemas.py`
   imports nothing; everything imports it. DOMAIN modules (`schemas.py`, `grounding.py`,
   `clinical/`, `evals/`) know nothing about FastAPI, Postgres, or Anthropic. EDGE
   modules (`orchestrator.py`, `judge_client.py`, `api.py`, `db.py`) are adapters — the
   only places a vendor's wire format may appear. When the domain needs a network call it
   declares a `Protocol` (`evals/judge.py: Judge`) and an edge module implements it
   (spec §0, L17). If a change would make a domain module import an edge module, stop
   and flag it.
2. **Grounding is pure and makes zero LLM calls.** Deterministic string work only.
   Judgment to the model, mechanics to code — never ask the LLM to count characters,
   find offsets, or compare drug names.
3. **`temperature=0` on every pipeline LLM call — summarize AND the judge.** Correctness
   requirement (evals need stable outputs), not a preference. Forced `tool_choice` on
   the summarize call.
4. **Errors-as-values inside the pipeline; raise at boundaries.** An ungroundable claim
   is a *result* (`UNSUPPORTED` flag), not an exception. A model that can't produce a
   valid draft IS an exception at the orchestrator boundary: `OrchestratorError` →
   `ModelOutputError` → `OutputTruncatedError`, each carrying the `usage` it cost; EAFP;
   `raise … from`. Once a valid draft exists, nothing reaches the user as an exception:
   grounding returns flags, checks fail closed, persist logs and swallows. Knowing which
   is which is the whole skill — enforce it in review.
5. **Safety extraction scans the WHOLE note.** The S/O/A/P section is the model's
   judgment call, display-only. Any safety check that reads only one section is a bug.
6. **Flag ownership is a write boundary (D6), enforced by the types.** Grounding owns
   `ClinicalClaim.flags` (`UNSUPPORTED`, `PARAPHRASED`) and nothing else ever writes to
   it. `ClinicalClaim` and `SOAPNote` are frozen; `flags` and `claims` are tuples. Evals
   emit `EvalResult`s that *reference* claims via `claim_ids`; they consume grounding's
   flags, never re-derive them, never mutate a claim. Never loosen `frozen` to make a
   check easier to write.
7. **LLM-as-judge is never the sole gate on a CRITICAL check.** The judge is WARNING-tier;
   a judge that errors or times out changes no CRITICAL verdict.
8. **Persistence is a sink.** `persist()` runs as a background task after the response
   is assembled, in its own session; a write failure is logged, never 500s the user.
   The pipeline never reads from the DB.
9. **Spans are half-open `[start, end)`** — Python slicing convention, always.
10. **No magic numbers.** Operational knobs → `config.py` (pydantic-settings). Clinical
    knowledge — including `NEGATION_WINDOW` — → `clinical/lexicons.py`.
11. **Corpus scoring consumes `expected_flags` via `case_verdict()`** (spec §8.7) — a
    tri-state: `passed` / `failed` / `not_applicable`. A fired expected flag is a PASS
    for a detection trap. `all_critical_passed` alone is NEVER the per-case verdict —
    "simplifying" back to it silently inverts every detection trap (caught in v1.1
    review; do not reintroduce it). An errored check never satisfies an expected flag
    (L43); an expected check that didn't run is `not_applicable`, never `failed` (L44).
12. **Empty never reads as safe.** `all_critical_passed` guards vacuous truth — zero
    CRITICAL results returns False. A check that raises inside `run_checks` becomes
    `EvalResult(passed=False, errored=True)` — never a skipped check, never a 500, never
    a magic `detail` string. The same law, other roads: an empty note from clinical
    input is a WARNING, not green; "not checked" never renders as "passed"; a metric over
    an empty denominator is `None`, not 1.0.
13. **`clinical/` imports nothing from the spine.** `extract.py` imports only
    `lexicons.py`; `lexicons.py` imports nothing (severities stored as plain strings).
    Extractors take plain strings and return multi-valued results; the checks run the
    same extractor over `claim.text`, the source span, and `raw_text`, and compare.
14. **Grounding proves the quote exists; the consistency family proves the text agrees
    with the SOURCE SPAN** — `raw_text[claim.source_span]`, never the model's
    `source_quote` (spec §6.4, L35). At Tier 3 the quote is the model's claim about the
    source; the span is the source. A Tier 1 exact match is not evidence the text is true.
15. **Lineage is derived, never declared.** `prompt_version` = hash(system prompt + tool
    schema + correction template + call config); `corpus_version` = hash(cases dir);
    `checks_version` = hash(`evals/` + `clinical/` + `grounding.py`); `settings.model` =
    a dated snapshot id; `git_dirty` recorded on every corpus run. A hand-bumped version
    string is a lie waiting for someone to forget.
16. **Retry only when the next request differs from the last.** Validation error → the
    model sees its mistake → retry (`max_validation_retries`, §5.4). `max_tokens` or a
    missing block → identical request at `temperature=0` → fail fast. Transport retries
    (429/5xx) are the SDK's (`sdk_transport_retries`, §5.2) — a different loop with a
    different name. Never zero the SDK's to "enforce" this invariant.
17. **The omission law (D17).** Every CRITICAL check documents, per input, what happens
    when the model omits that input — a docstring and a test. An omission that silences
    the check must be covered by another live check or declared a CI-only gap. A new
    CRITICAL check without its omission row is incomplete (spec §8.4).
18. **Scribe, not consultant (D7, L50).** The prompt never lets the model state a
    clinical judgment the clinician didn't: Assessment is clinician-stated, certainty
    verbatim, patient self-diagnosis is Subjective. "Omit when uncertain" never applies
    to safety-critical facts — allergies/NKDA and every medication started, stopped, or
    changed at this visit. Review every prompt edit against this.
19. **PHI never leaves through the side doors.** Raw text, note content, and exception
    messages that may carry them never reach a log line or an HTTP body. Error bodies are
    `{error, request_id}`; `OrchestratorError` is logged by `code` without `exc_info`;
    checks log by name; validation errors are stringified with `include_input=False`
    (spec §9.4, §9.8). This is the runtime twin of "zero PHI in the repo."
20. **A test's tier is decided by what's stochastic in its path.** Injected cases
    (`EvalCase.draft` set) are deterministic and run free on every commit; model cases
    are paid. A danger the *model* creates (a fabrication, a flip) is tested by injecting
    it — never by a model case that hopes the model will make it (spec §8.5, L42).

## Sanctioned shapes outside `schemas.py`

New pipeline data shapes go in `schemas.py`. Two sanctioned exceptions, nothing else:

- **HTTP edge shapes** (`SummarizeRequest`, `SummarizeResponse`) live in `api.py`.
- **Check-internal shapes** (`Finding`, `Check`) live in `evals/registry.py` — they never
  cross a layer boundary.

Anything else outside `schemas.py`: flag it.

## Decisions beyond spec v1.3 (implementation-level, not spec amendments)

Recorded here so the design room (claude.ai Project) and the build room agree. Each entry
cites the spec it touches and names the test that enforces it. The next spec revision
absorbs these, and this section empties again. Deferred amendments that are NOT active in
the build live in the GitHub issue "spec v1.4: deferred amendments", not here.

**What may go here.** An entry may *fill* a detail the spec leaves unspecified, or
*resolve a conflict between two statements in the spec*, citing both and naming which
wins and why. An entry may never override a spec statement that nothing else in the spec
contradicts. That is an amendment, and it waits for the next revision. If a proposed
entry fails this test, flag it; don't record it.

- **I1 — Phase-1 display is a static page** (fill: §14's "minimal display"; §13 names no
  phase-1 UI). `GET /` in `api.py` (EDGE) serves `backend/static/index.html`: textarea →
  `fetch("/summarize")` → `draft.claims` grouped by `section` client-side. All four
  sections always render; an empty one shows "none stated" (D7). Output labeled
  "DRAFT — unverified" (inv. 12). One-line PHI warning above the textarea (the §9.10
  banner is phase 3). Same-origin, so no CORS in phase 1. No `by_section`, no `SOAPNote`:
  the phase-1 `schemas.py` fence holds (§14). Claims render via `textContent`, never
  `innerHTML`: every `source_quote` copies the paste verbatim, so markup in the paste
  would execute. `backend/static/` is a path §13 doesn't list; it is sanctioned here and
  deleted when `frontend/` replaces it in phase 3.
  Test: `GET /` → 200, `text/html`; the served file contains no `innerHTML`.

- **I2 — Unexpected errors log structure, never messages** (conflict: §9.4's 500 row,
  "logged in full, internally," vs L53 in §9.4/§9.8 and inv. 19. L53 wins: the spec's
  PHI rule beats one table cell; v1.4 amends the row). The 500 path logs
  `code="internal_error"`, `request_id`, `exc_type=type(exc).__name__`, and frames as
  `file:line:function` from `traceback.extract_tb`. Never `exc_info`, `str(exc)`, or a
  chained cause. Frames carry no PHI; messages can (a chained `ValidationError` carries
  `input_value`). Implement as a catch-all middleware that runs inside the request-id
  middleware, NOT `@app.exception_handler(Exception)`: Starlette's
  `ServerErrorMiddleware` calls that handler and then re-raises for the server to log,
  so uvicorn prints the full traceback anyway. Specific handlers (`ModelOutputError`,
  SDK errors) stay `exception_handler`s.
  Test: a route raising an exception whose message is a sentinel → 500
  `{error, request_id}`; the sentinel appears in no `caplog` record and not in the body.
  With the default `TestClient`, the wrong implementation fails this test by re-raising.

- **I3 — The default 422 handler is replaced** (fill: §9.4 fixes the body shape;
  FastAPI's default handler returns `exc.errors()`, whose `input` is the entire paste).
  A `RequestValidationError` handler returns 422 `{"error": "input_invalid",
  "request_id": ...}` and logs by code only.
  Test: an oversized and an undersized paste, each containing a sentinel → 422 with the
  correct body; the sentinel appears in neither the body nor the logs.

- **I4 — Upstream failures are attributed by status** (conflict: §9.4's row
  `anthropic.APIError (other) → 502 upstream_error, "not my bug"` vs §9.4's rule that
  each code "says a different true thing about whose fault it was" and §5.4's hierarchy
  naming whose fault it is. The rule wins: a 401 from a bad key is not upstream's bug;
  v1.4 amends the row). `APIStatusError` 4xx except 429 → 500 `internal_error`, logged
  with `upstream_status` (our request or config: schema, key, access, model id, size).
  5xx except 529 → 502 `upstream_error`. 529 → 503 `upstream_busy` (same meaning as
  `RateLimitError`). A connection failure that is not a timeout (`APIConnectionError`,
  not `APITimeoutError`) takes §9.4's residual `APIError` row → 502 `upstream_error`.
  All other §9.4 rows are unchanged.
  Test: one per mapping, with the fake client raising each status. `APIConnectionError`
  gets its own test: it reaches 502 through a different MRO branch than a 5xx, and
  `APITimeoutError` subclasses it, so the pair of tests pins the 504 handler winning.

- **I5 — The model's output ceiling is a config knob** (fill: L16 requires validating
  `max_output_tokens` against the model's ceiling at boot; the spec names no source, and
  the SDK exposes none). `config.py` declares `model_max_output_tokens` directly beside
  `model`, with a comment that the two change together. A validator rejects settings
  whose derived `max_output_tokens` exceeds it.
  Test: settings with `max_input_chars` past the ceiling raise at construction.

- **I6 — Phase-1 HTTP scope is named** (fill: §14's "every §9.4 row reachable in phase
  1"). Reachable: 422 `input_invalid` · 502 `output_truncated` · 502
  `model_output_invalid` · 503 `upstream_busy` · 504 `upstream_timeout` · 502
  `upstream_error` · 500 `internal_error`. Not reachable until phase 3: 429
  `rate_limited`, 503 `budget_exhausted`. The HTTP test module lists both sets at the
  top. `request_id` is minted per request by middleware (`uuid4().hex` on
  `request.state.request_id`); every error body and log line carries it.
  Test: the 502 `model_output_invalid` row is reached twice — a response with no tool
  block, and `stop_reason="refusal"` with no tool block — so the refusal path is a
  pinned behavior, not an accident of the missing-block branch.

- **I7 — `LLMClient` declares explicit kwargs** (conflict: §5.5 says the Protocol
  exposes `messages.create(**kwargs)` AND that "mypy checks the seam every test depends
  on." No loose signature satisfies both: `**kwargs: Any` alone rejects `AsyncAnthropic`;
  `*args: Any, **kwargs: Any` is treated as `...` and checks nothing. "mypy checks the
  seam" wins). The Protocol's `create` declares exactly the keywords the orchestrator
  passes (`model`, `system`, `tools`, `messages`, `temperature`, `tool_choice`,
  `max_tokens`), typed with the SDK's own param types so contravariance can't bite
  (allowed: the orchestrator is EDGE, inv. 1). `messages` is declared as a read-only
  `@property` on `LLMClient`, not a bare attribute: a bare protocol attribute is settable,
  and the SDK's `messages` is a cached property. Test fakes build real
  `anthropic.types.Message` objects, so the fake can't drift from the wire format.
  Test: mypy over `backend/` and `tests/` (see Commands), forced by binding sites on
  both sides. `get_client() -> LLMClient` returns `AsyncAnthropic(...)`, and the fake in
  `tests/` is bound to an `LLMClient`-typed name; without both, mypy checks only half
  the seam.

- **I8 — Parallel tool use is disabled on the summarize call** (conflict: §5.4 states
  the API contract — once an assistant turn contains a `tool_use` block, the next user
  message must answer it with a `tool_result` for the same id — while its loop answers
  only the first block; §5.2's `CALL_CONFIG` forces the tool but leaves parallel tool
  use on, so a two-block response makes the retry 400, which I4 reports as our 500. The
  contract wins, and the unanswerable state is prevented rather than handled).
  `CALL_CONFIG["tool_choice"]` is `{"type": "tool", "name": "emit_soap_note",
  "disable_parallel_tool_use": True}`. It lives in `CALL_CONFIG`, so it is inside
  `PROMPT_VERSION` automatically (inv. 15).
  Test: the fake records the kwargs of every `create` call; `tool_choice` carries the
  flag on every attempt, validation retries included.

- **I9 — The phase-1 response is an edge shape** (fill: §9.1 says the phase-1 route
  returns `{draft, metadata}` without naming its type). `SummarizeResponse` in `api.py`
  (sanctioned above) declares `draft: SOAPNoteDraft` and `metadata: RunMetadata`; the
  route never uses `SummarizationResult` as its `response_model`. The domain return type
  and the wire contract are different jobs: in phase 2a the edge shape becomes
  `note_id` + `note` + `report` + `metadata` (§9.1) and nothing in `schemas.py` changes.
  Test: the happy-path route test asserts the body's top-level keys are exactly
  `{"draft", "metadata"}`.

## Build sequence gate (the Volkswagen safeguard)

Build order is spec §14 and it is strictly sequential:

1. **MVP spine** — paste → route → LLM tool call → draft → display
2. **2a — the safety layer, proven for free** — grounding, extraction, the reference-free
   roster, the injected corpus
3. **2b — the regression thesis goes live** — model corpus, `case_verdict`, repeats,
   lineage, the four metrics
4. **2c — the semantic backstop** — the entailment judge
5. **3 — full-stack real** — Postgres, React UI, deploy
6. **4 — RAG deepening** — designed in spec v1.4 before any code

**Current phase: 1 — MVP spine.** *(Update this line as phases complete.)*

- **Closing a phase:** audit its §14 exit criteria line by line, CI green, update the line
  above, tag it (`v0.1-spine`, `v0.2a-safety`, `v0.2b-corpus`, `v0.2c-judge`,
  `v0.3-shipped`, `v0.4-rag`).
- **"Phase" means build phase only.** Curriculum units are *Arcs* (spec §16).
- If a request belongs to a later phase or the §15 backlog (streaming, auth,
  RxNorm/medspaCy, dedup, chunking, duplicate-quote locality, meta-evaluation,
  reaction-type extraction, `about:` on expected flags, a shared budget counter), say so
  and point at the backlog instead of building it. Deliberate non-features are part of
  the portfolio story; building them early destroys that story.

## Commands

```bash
uv sync                          # install/sync env (uv owns .venv; never pip install)
uv add <pkg> / uv add --dev <pkg>
uv run pytest                    # unit + injected corpus + integration — deterministic, free
uv run pytest tests/ -x -q       # fast fail during TDD loops
uv run ruff check . && uv run ruff format --check .   # lint + format; clean before commit
uv run mypy backend/ tests/      # type-check; the spine AND the test fakes — the fake
                                 #   client lives in tests/, and I7's seam is only
                                 #   checked if mypy reads both sides of it
uv run python -m backend.evals.runner   # ⚠️ score_corpus: REAL API calls, costs $,
                                        # slow. MODEL cases only (injected cases run in
                                        # pytest), × corpus_repeats (default 3) — cost
                                        # scales with k. NEVER run unprompted. Pre-deploy
                                        # / manual cadence only. Always confirm first.
                                        # Every run appends a CorpusRunRecord to
                                        # evals/runs/corpus_runs.jsonl (lineage, D5).
```

CI: GitHub Actions (`.github/workflows/ci.yml`) runs ruff + mypy (`backend/` and `tests/`)
+ pytest on every push **from phase 1**. The model corpus is deliberately excluded from the
push workflow (it costs money) — manual dispatch / pre-deploy only.

Tests never hit the network: orchestrator tests use an injected fake client (canned
tool-use block); judge tests use a fake `Judge` (canned verdicts); route tests use
`dependency_overrides` (plus a test DB from phase 3).

## Conventions

- Conventional commits, atomic. History is part of the portfolio. One tag per phase.
- Pydantic models: draft/enriched family per spec §4. New pipeline data shapes go in
  `schemas.py` (sanctioned exceptions above).
- Type hints everywhere; mypy clean before commit.
- Secrets: `.env` (gitignored), `.env.example` (committed). API key never in code —
  clinical-adjacent repo, zero tolerance.
- Synthetic data only in `evals/cases/`. **Zero real PHI, ever, anywhere in the repo** —
  including in examples, tests, commit messages, and comments.
- TDD where it fits (red → green → refactor); coverage is a flashlight, not a trophy.
- Every eval corpus needs clean controls alongside trap cases — a check that flags a
  perfect note is as broken as one that misses a fabrication.
- One planted danger per trap (D16): no incidental entities that could trip the same
  check.

## Definition of done

Two checklists, two questions. **"Is phase N done?"** → that phase's exit criteria in
spec §14. **"Is the project done?"** → spec §17. Audit line by line, not vibes; if it's
unclear which question Cal is asking, audit the current phase.
