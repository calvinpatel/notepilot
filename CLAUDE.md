# CLAUDE.md — NotePilot

Clinical-encounter → grounded, safety-checked SOAP summarizer. Flagship portfolio
project. FastAPI + Postgres + React; Anthropic API via tool use.

## Source of truth

`PROJECT_01_NOTEPILOT.md` is the canonical build spec; its header states the current
version. It wins every conflict — including conflicts with this file and with in-session
requests. `PROJECT_01_NOTEPILOT_CHANGELOG.md` is its history: every `L#` and `D#` the spec
cites resolves there. The changelog says *why*; the spec says *what is*. Implement against
the spec.

- Before implementing anything, check the relevant spec section. Cite it ("§6.1", "D12",
  "L35") when explaining a decision.
- If a request deviates from the spec, **flag the deviation before writing code** and
  ask whether we're amending the spec or the request. Never silently drift.
- **If the spec contradicts itself, stop.** Don't pick a winner in-session. Quote both
  statements to Cal; the resolution is a spec patch (see "Changing the spec"), and the
  code follows the patched text.
- If the spec itself seems wrong or has a gap, say so directly: finding flaws is welcome,
  hiding them is not.
- **The spec and this file move together.** A spec revision changes this file only when an
  invariant is added, removed, renumbered, or retitled, or its standing instruction here
  changes; then both land in one commit.

## Working relationship

Cal is the author of record and a capable engineer; Claude Code is a full collaborator
with no restricted zones: write code anywhere in the repo when asked.

- **Read the request, do that thing.** Cal decides per request whether he wants a
  design discussion, a review, a walkthrough, scaffolding, or full implementation.
  Don't hedge an implementation request into an explanation, and don't pre-empt a
  discussion request with code.
- **Never unsolicited.** Don't write or change code outside the scope of the current
  request. If something adjacent needs doing, flag it and let Cal decide.
- **Clinical reasoning stays visible.** When writing clinical logic (severity assignments,
  check semantics), state the clinical rationale alongside the code so each call is an
  explicit decision on the record, not a silent default.
- **Clinical entries arrive VERBATIM.** Every entry in `clinical/lexicons.py`, D9's R1
  rungs and D14's unspecified-penicillin rule included, is drafted in the design room and
  signed off by Cal there. It lands from a VERBATIM block with its own rationale comment,
  under a `# Clinical sign-off:` line that heads its table. Never author, reword, or
  reorder an entry in a session; if code needs an entry the request doesn't carry, stop
  and say which. A spec default is not a clinical sign-off.
- **Standing order: nitpick everything.** Style, naming, edge cases, design smells.
  Cal explicitly wants this. Review with senior-engineer rigor, not politeness.

## Architectural invariants (never violate, flag any code that does)

Each invariant's statement lives in the spec, §3.1: read it there. The numbers and titles
match; a line here adds Claude Code's standing instruction where the invariant has one.

1. **Dependencies point inward at `schemas.py`; vendors stay at the edge.** → §3.1. If a
   change would make a domain module import an edge module, stop and flag it.
2. **Grounding is pure and makes zero LLM calls.** → §3.1.
3. **Every pipeline LLM call pins what shapes its output — summarize AND the judge.** →
   §3.1. If the SDK or the API rejects a call-config field, never "fix" it by deleting the
   field; flag it, because removing one is a spec change.
4. **Errors-as-values inside the pipeline; raise at boundaries.** → §3.1. Knowing which is
   which is the whole skill — enforce it in review.
5. **Safety extraction scans the WHOLE note.** → §3.1.
6. **Flag ownership is a write boundary (D6), enforced by the types.** → §3.1. Never loosen
   `frozen` to make a check easier to write.
7. **LLM-as-judge is never the sole gate on a CRITICAL check.** → §3.1.
8. **Persistence is a sink.** → §3.1.
9. **Spans are half-open `[start, end)`** → §3.1.
10. **No magic numbers.** → §3.1.
11. **Corpus scoring consumes `expected_flags` via `case_verdict()`** → §3.1.
    `all_critical_passed` alone is NEVER the per-case verdict — "simplifying" back to it
    silently inverts every detection trap (caught in v1.1 review; do not reintroduce it).
12. **Empty never reads as safe.** → §3.1.
13. **`clinical/` imports nothing from the spine.** → §3.1.
14. **Grounding proves the quote exists; the consistency family proves the text agrees with
    the SOURCE SPAN** → §3.1.
15. **Lineage is derived, never declared.** → §3.1.
16. **Retry only when the next request differs from the last.** → §3.1. Never zero the
    SDK's transport retries to "enforce" this invariant.
17. **The omission law (D17).** → §3.1.
18. **Scribe, not consultant (D7, L50).** → §3.1. Review every prompt edit against this.
19. **PHI never leaves through the side doors.** → §3.1.
20. **A test's tier is decided by what's stochastic in its path.** → §3.1.

## Changing the spec

Implementation truth lives in the spec. This file holds instructions, and it has no
staging area for decisions.

- **Patch (v1.x.y)** — fills a detail the spec leaves unspecified, or resolves a conflict
  between two spec statements (cite both, name the winner, say why). Cal approves the
  resolution first. Then edit the spec **in place**, in the section the decision belongs
  to; bump the header version; add a changelog entry under the next `L#`, with severity.
  It lands in the same commit as the code that depends on it.
- **Minor (v1.x)** — anything that changes a statement nothing else in the spec
  contradicts. That is an amendment: flag it and log it on the GitHub issue "spec:
  deferred amendments." Never implement it ahead of the revision.
- New spec text cites ledger ids (`L82`), not version numbers; the changelog maps ids to
  versions.
- When a proposed commit touches the spec, the changelog, or this file, say that the
  design room's copies in project knowledge need re-uploading.

## Build sequence gate (the Volkswagen safeguard)

Build order is spec §14, phase by phase, strictly sequential.

**Current phase: 2b — the regression thesis goes live.** *(Update this line as phases
complete.)*

- **Closing a phase** follows §14's preamble; each tag is named in its phase's heading.
- If a request belongs to a later phase or the §15 backlog, say so and point there
  instead of building it. Deliberate non-features are part of the portfolio story;
  building them early destroys that story.

## Commands

```bash
uv sync --locked                 # install/sync env (uv owns .venv; never pip install)
uv add <pkg> / uv add --dev <pkg>
uv run pytest                    # unit + injected corpus + integration —
                                 #   deterministic, free
uv run pytest tests/ -x -q       # fast fail during TDD loops
uv run ruff check . && uv run ruff format --check .   # lint + format; clean before commit
uv run mypy backend/ tests/      # strict (L91); tests/ holds the fake side of the
                                 #   LLMClient seam (§5.5, L74)
uv run uvicorn backend.api:app --reload  # local app. ⚠️ every summarize is a REAL API
                                         # call: the phase-close smoke run (§14, L81)
                                         # only with Cal's go-ahead.
```

**`score_corpus` (§8.7) makes REAL API calls, × `corpus_repeats`: never run it
unprompted.** It runs only with Cal's go-ahead, never in the push workflow (§11).

CI runs the gates on every push (§11, L96).

Tests never hit the network: orchestrator tests use an injected fake client (canned
tool-use block); judge tests use a fake `Judge` (canned verdicts); route tests use
`dependency_overrides`.

## Conventions

- Conventional commits, atomic. History is part of the portfolio. One tag per phase.
- Pydantic models: draft/enriched family per spec §4. New pipeline data shapes go in
  `schemas.py`; the three sanctioned exceptions are in spec §13. Flag anything else.
- Secrets: `.env` (gitignored), `.env.example` (committed). API key never in code —
  clinical-adjacent repo, zero tolerance.
- Synthetic data only in `evals/cases/`. **Zero real PHI, ever, anywhere in the repo** —
  including in examples, tests, commit messages, and comments.
- Coverage is a flashlight, not a trophy.
- Corpus cases follow §8.5: clean controls beside the traps, one planted danger per trap
  (D16).

## Working a step

A request carries only its step; the standing rules are this section's. Text in a block
labeled VERBATIM lands in the repo exactly as given; everything else in a request is
instruction. If VERBATIM text can't land as given, stop and say why.

The plan reports by exception: measurements, deviations from the request, adapted
substitutions, judgment calls, and the exact form of any code the request doesn't give
verbatim. It has no context section, and it names VERBATIM edits and commit messages
rather than repeating them. It names every invariant its step touches, read from the spec's
§3.1.

### Measure, don't recall

- SDK and framework shapes are measured against the installed packages: a scratch script,
  its output quoted in the plan. If a measurement contradicts the request, stop and
  say so.
- Scratch scripts live in the session scratchpad, never the repo, and run from the repo
  root as `PYTHONPATH=. NOTEPILOT_IGNORE_DOTENV=1 ANTHROPIC_API_KEY=test-dummy-key uv run
  python <script>`. The project has no `[build-system]`, so nothing installs `backend`;
  the two variables give a scratch run the settings `tests/conftest.py` gives pytest.
- Every pytest run sets `PYTHONPYCACHEPREFIX` to a fresh, empty directory. CPython trusts
  bytecode whose recorded source mtime and size still match, so a same-length edit made
  and restored within one second can run stale. The prefix also takes pytest's rewritten
  test bytecode. Set it per invocation, as
  `PYTHONPYCACHEPREFIX="$(mktemp -d "$TMPDIR/pyc.XXXXXX")" uv run pytest`: an exported
  prefix outlives its run, and inside the sandbox `mktemp -d` without a `$TMPDIR`
  template fails.
- Reports state only numbers measured in this session: test counts, line numbers, hashes.
- `gates` means the checks in `.github/workflows/ci.yml`, run locally with the same
  commands.

### Edits and commits

- Repo files change through the Edit tool, so each change passes Cal's approval; Write
  only creates a file that doesn't exist yet. Never `sed -i`, a shell redirect, or a
  script. Mutation rows are the one exception, and the reverse: the driver writes them,
  never the Edit tool.
- Propose commits. Never commit, stage, or run a git command that changes the index or the
  working tree. A proposal is the commit's path list and its full message; the body says
  what the diff does, nothing it doesn't, and leaves nothing out.
- When two of a step's commits touch the same file, stop at a stage gate after the first:
  propose it, and make the next commit's edits only after Cal says it's committed.
- The Edit tool writes a `\uXXXX` escape as the character it names. VERBATIM text that
  holds one is checked byte for byte after the edit; a decoded escape is a deviation to
  report, with how it was restored.

### Tests

- A change in behavior starts with its tests: write them, run them, and show the red run's
  output. A red run is shown, never inferred.
- Objects a test constructs (SDK errors, messages) come from typed builder functions, as
  in `tests/fakes.py`; never an untyped helper or a `cast`.
- A wiring test, one that proves a value travels from where it's set to where it's used,
  uses a value the code can't reach by default: a non-default setting, a test-local
  exception class (never a builtin, which other code can raise).
- Leak tests plant sentinels in values, never keys, and scan `caplog.text`: every record
  as rendered, `exc_info` included. Every logging test calls
  `caplog.set_level(logging.DEBUG)`.
- Every 500 test asserts its own log line: the catch-all turns any `Exception` into a 500,
  so a 500 alone proves nothing.
- mypy strict is the type gate. Never add `# type: ignore` to quiet the editor's pyright:
  mypy reports an ignore it doesn't need, and CI fails.
- Ruff enforces only the rules `pyproject.toml` selects; don't restyle code or add
  `# noqa` for any other.

### Mutation rows

A row names a file, an exact pattern, its replacement, and the assertion meant to kill it.

- One driver script in the scratchpad runs all of a step's rows, once, with its output
  written to a file.
- Every row runs the whole suite, with `PYTHONHASHSEED=0` and
  `--continue-on-collection-errors`, under its own `PYTHONPYCACHEPREFIX`, deleted after
  the row. A narrower run can't show a kill the row didn't target; a fixed seed holds set
  order still across rows; a mutant that breaks one file's import still runs the rest.
- Kills are read from `--junitxml` by test id, with each failure's exception type. A kill
  that raises instead of failing its assertion is reported as an exception kill; the
  request marks the ones it expects.
- Each pattern matches exactly once, written against the ruff-formatted source. Report any
  substitution you adapt.
- Before each row the driver saves the file's bytes and sha256, writes the mutant inside
  `try`, restores the saved bytes in `finally`, and checks the hash: the files are
  uncommitted, so git can't restore them. The moment the driver exits, before anything
  else, hash every file any row touched. A driver killed mid-row leaves its mutant in
  place, and only this check catches it.
- Each mutant dies at its targeted assertion; report the failing line for each row. A row
  that edits the test file itself shifts its lines, so read the kill line from the mutant
  text. If a row dies anywhere else, stop and say so; never reshape a test to fit.
- A mutant no test can tell apart gets a distinguishing test, or is reported as
  equivalent, with the reason.
- The gates run last, after the driver has exited and its hashes are checked. A hash that
  matches the pre-driver file is not a gate run.

### What code, tests, and comments may say

- Comments and docstrings claim only what's true and tested: no exhaustiveness ("every",
  "only", "never") that a test doesn't assert.
- No mutation-row ids or review pointers. No version numbers (cite ledger ids), and no
  claims about code that doesn't exist yet.

## Definition of done

Two checklists, two questions. **"Is phase N done?"** → that phase's exit criteria in
spec §14. **"Is the project done?"** → spec §17. Audit line by line, not vibes; if it's
unclear which question Cal is asking, audit the current phase.
