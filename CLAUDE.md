# CLAUDE.md — NotePilot

Clinical-encounter → grounded, safety-checked SOAP summarizer. Flagship portfolio
project. FastAPI + Postgres + React; Anthropic API via tool use.

## Source of truth

`PROJECT_01_NOTEPILOT_v1_2.md` (v1.2 — second adversarial review pass, September 2026) is
the canonical build spec. It wins every conflict — including conflicts with this file and with
in-session requests.

- Before implementing anything, check the relevant spec section. Cite it (e.g. "§6.1")
  when explaining a decision.
- If a request deviates from the spec, **flag the deviation before writing code** and
  ask whether we're amending the spec or the request. Never silently drift.
- If the spec itself seems wrong or has a gap, say so directly. Cal has upgraded specs
  before (the cross-reactivity gap in the testing capstone); finding flaws is welcome,
  hiding them is not.

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
- **Standing order: nitpick everything.** Style, naming, edge cases, design smells.
  Cal explicitly wants this. Review with senior-engineer rigor, not politeness.

## Architectural invariants (never violate, flag any code that does)

1. **Dependencies point inward at `schemas.py`.** It imports nothing; everything imports
   it. Domain layers know nothing about FastAPI, Postgres, or Anthropic. If a change
   would make `grounding.py` import from `api.py`, stop and flag it.
2. **Grounding is pure and makes zero LLM calls.** Deterministic string work only.
   Judgment to the model, mechanics to code — never ask the LLM to count characters,
   find offsets, or compare drug names.
3. **`temperature=0` on all pipeline LLM calls.** Correctness requirement (evals need
   stable outputs), not a preference. Forced `tool_choice` on the summarize call.
4. **Errors-as-values inside the pipeline; raise at boundaries.** An ungroundable claim
   is a *result* (`UNSUPPORTED` flag), not an exception. An invalid schema at the
   orchestrator boundary IS an exception (`OrchestratorError`, EAFP, `raise … from`).
   Knowing which is which is the whole skill — enforce it in review.
5. **Safety extraction scans the WHOLE note.** The S/O/A/P section is the model's
   judgment call, display-only. Any safety check that reads only one section is a bug.
6. **Flag ownership is a write boundary (spec D6):** grounding owns `ClinicalClaim.flags`
   (`UNSUPPORTED`, `PARAPHRASED`) and nothing else ever writes to it. Evals emit
   `EvalResult`s that *reference* claims via `claim_ids`. Evals *consume* grounding's
   flags, never re-derive them, never mutate a claim.
7. **LLM-as-judge is never the sole gate on a CRITICAL check.**
8. **Persistence is a sink.** `persist()` runs after the response is assembled; a write
   failure is logged, never 500s the user. The pipeline never reads from the DB.
9. **Spans are half-open `[start, end)`** — Python slicing convention, always.
10. **No magic numbers.** Operational knobs → `config.py` (pydantic-settings). Clinical
    knowledge → `clinical/lexicons.py`.
11. **Corpus scoring consumes `expected_flags`.** The per-case verdict is `case_passed()`
    (spec §8.7): a fired expected flag is a PASS for detection traps. `all_critical_passed`
    alone is NEVER the per-case verdict — "simplifying" back to it silently inverts the
    scoring of every detection-style trap. This exact regression was caught in review;
    do not reintroduce it.
12. **Empty never reads as safe.** `all_critical_passed` must guard vacuous truth — zero
    CRITICAL results returns False, not True. `all()` over an empty list is True; absence
    of evidence is not evidence of safety. Same law, applied to exceptions: a check that
    raises inside `run_checks` becomes `passed=False, detail="check_error"`, never a
    skipped check and never a 500 (spec §8.7).
13. **`clinical/extract.py` imports nothing and operates on plain strings.** The checks run
    the same extractor over `claim.text`, `claim.source_quote`, and `raw_text` and compare.
    A primitive that takes a `SOAPNote` can only look at one thing; that's the v1.1 gap.
14. **Grounding proves the quote exists; the claim-local consistency checks prove the text
    doesn't say more than the quote.** Both are required. A Tier 1 exact match is not
    evidence that the claim's `text` is true (spec §6.4, §8.4).
15. **Lineage is derived, never declared.** `prompt_version` = hash(prompt + tool schema),
    `corpus_version` = hash(cases dir), `settings.model` = a dated snapshot id. A
    hand-bumped version string is a lie waiting for someone to forget.
16. **Retry only when the next request differs from the last.** Validation error → the
    model sees its mistake → retry. `max_tokens` / missing block → identical request at
    `temperature=0` → fail fast (spec §5.4).

## Build sequence gate (the Volkswagen safeguard)

Build order is spec §14 and it is strictly sequential:

1. MVP spine (paste → route → LLM tool call → draft → display)
2. Grounding + eval harness
3. Full-stack real (Postgres, React UI, deploy)
4. RAG deepening

**Current phase: 1 — MVP spine.** *(Update this line as phases complete.)*

If a request belongs to a later phase or the v2 backlog (§15: streaming, auth,
RxNorm/medspaCy, dedup, chunking, duplicate-quote locality, meta-evaluation), say so
and point at the backlog instead of building it. Deliberate non-features are part of
the portfolio story; building them early destroys that story.

## Commands

```bash
uv sync                          # install/sync env (uv owns .venv; never pip install)
uv add <pkg> / uv add --dev <pkg>
uv run pytest                    # unit + integration — deterministic, free, every commit
uv run pytest tests/ -x -q       # fast fail during TDD loops
uv run mypy backend/             # type-check; the spine must stay clean
uv run python -m backend.evals.runner   # ⚠️ score_corpus: REAL API calls, costs $,
                                        # slow. NEVER run unprompted. Pre-deploy /
                                        # nightly cadence only. Always confirm first.
                                        # Every run appends a CorpusRunRecord to
                                        # evals/runs/corpus_runs.jsonl (lineage).
```

CI: GitHub Actions (`.github/workflows/ci.yml`) runs unit + integration + mypy on push.
The corpus tier is deliberately excluded from the push workflow (it costs money) — manual
dispatch / pre-deploy only.

Tests never hit the network: orchestrator tests use an injected fake client (canned
tool-use block); route tests use `dependency_overrides` + a test DB.

## Conventions

- Conventional commits, atomic. History is part of the portfolio.
- Pydantic models: draft/enriched family per spec §4. New pipeline data shapes go in
  `schemas.py` — nowhere else.
- Type hints everywhere; mypy clean before commit.
- Secrets: `.env` (gitignored), `.env.example` (committed). API key never in code —
  clinical-adjacent repo, zero tolerance.
- Synthetic data only in `evals/cases/`. **Zero real PHI, ever, anywhere in the repo** —
  including in examples, tests, commit messages, and comments.
- TDD where it fits (red → green → refactor); coverage is a flashlight, not a trophy.
- Every eval corpus needs clean controls alongside trap cases — a check that flags a
  perfect note is as broken as one that misses a fabrication.

## Definition of done

Spec §17 is the checklist. When Cal asks "is this done?", audit against §17
line-by-line, not vibes.
