# PROJECT 01 — NotePilot · Spec changelog

The history of `PROJECT_01_NOTEPILOT.md`: what changed in each version, and why. The spec
states what the system *is*; this file records how it got there. Newest first.

**Reading the ids.** `L#` is the delta ledger: one id per change, numbered continuously
across versions (v1.3's walkthrough opened it at L1; v1.3.1 continues at L68; v1.3.2 at L82; v1.3.3 at L94; v1.3.4 at L97; v1.3.5 at L98; v1.3.6 at L99; v1.3.7 at L100; v1.3.8 at L101; v1.3.9 at L102; v1.3.10 at L103), so
an id never needs its version to be unambiguous. `D#` is a decision record, vetoable like every D.
Where a decision also has a DECISION block in the spec, the block is the current statement
and the entry here is its origin. Severity uses the project's own triage enum. v1.1 and v1.2
predate the ledger; their deltas are cited by section.

**Versioning.** Patch (v1.3.x): fills a detail the spec leaves unspecified, or resolves a
conflict between two spec statements, citing both and naming which wins. Minor (v1.x):
anything else. Every change gets the next `L#`.

---

## v1.3.10 — a misspelled case key is a load error (patch)

Theme: one fill found while planning phase 2a. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L103 §4.2, §8.5 — the case contract forbids unknown keys.** Fill: §8.5 makes a
  misspelled `expected_flags` entry a load error, but `EvalCase`, `PreserveItem`, and
  `NotAddItem` declared no `extra` policy, and Pydantic ignores unknown keys by default. A
  misspelled `draft:` left `draft=None`, silently turning an injected case into a model
  case: skipped by the free tier, then billed by the corpus run. A misspelled
  `must_preserve:` left a fidelity trap with nothing to check, a vacuous pass. All three
  forbid extra keys, as `ClaimDraft` and `SOAPNoteDraft` already do. `PreserveItem` and
  `NotAddItem` take it when they land, with the reference checks.

---

## v1.3.9 — the verdict is on the wire (patch)

Theme: one fill found while planning phase 2a. No invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L102 §4.2, §9.3 — `all_critical_passed` is serialized.** Fill: §4.2 declared the
  verdict a plain `@property`, which Pydantic does not serialize, so the response would
  carry `results` without the verdict. Every consumer (the 2a page, the phase-3 UI, a
  persisted report) would recompute it, and a recomputation is free to drop the
  vacuous-truth guard that keeps an empty or warning-only report from reading as passed
  (invariant 12). It is now a `computed_field`: in the body, and in the serialization
  schema `openapi-typescript` reads. mypy rejects decorators stacked on `@property`, so
  the line carries `# type: ignore[prop-decorator]`, the form Pydantic documents; strict
  mode reports the ignore if mypy ever stops needing it.

---

## v1.3.8 — the spec stops tracking the build (patch)

Theme: one conflict found at the phase-1 close. No invariant moves. CLAUDE.md changes in
the same commit for the close itself (its "Current phase" line), not for this patch.

**INFO**
- **L101 header, §14 — the spec stops tracking the build.** Conflict: the header's status,
  "skeleton / pre-build," and §14's Phase 1 note, "closest to done," vs §14's close
  procedure, which records build state in CLAUDE.md's "Current phase" line and a tag per
  phase. Only §14's record has a step that keeps it current; the other two go stale as the
  build moves. §14 wins: the header states the design's status and points at §14's record,
  and the Phase 1 note is removed.

---

## v1.3.7 — the static page has no blank outcome (patch)

Theme: one fill found while designing step 5's page. No invariant moves; CLAUDE.md is
unchanged.

**INFO**
- **L100 §9.10 — the static page has no blank outcome.** Fill: L92 covered a non-2xx whose
  body carries `error` and `request_id`. Two outcomes had no state: a fetch that rejects,
  which has no status and no body, and a response whose body lacks those fields. Anything
  but a result now renders its HTTP status, plus the code and request id when the body has
  both; a fetch with no response renders a fixed line that names no code, so it can't be
  read as one of §9.4's. §9.10's phase-1 paragraph cites ledger ids, not versions.

---

## v1.3.6 — the upstream status handler is total (patch)

Theme: one fill found while designing step 4c's handlers. No invariant moves; CLAUDE.md is
unchanged.

**INFO**
- **L99 §9.4, §11, §14 — the upstream status handler is total.** Fill: L71 mapped 4xx
  except 429, 5xx except 529, and 529, leaving the `APIStatusError` handler undefined for a
  429 that arrives as the base class and for any status outside 4xx/5xx. The SDK's factory
  builds `RateLimitError` for every 429, but the handler still needs an answer for each
  status it can receive. 429 joins 529 at 503 `upstream_busy`, checked first because 429 is
  also a 4xx; anything outside 4xx/5xx → 502 `upstream_error`. The handler branches on the
  status, never the subclass. Measured on SDK 1.9: the factory never builds
  `ServiceUnavailableError` or `DeadlineExceededError`, so an upstream 503 or 504 arrives as
  `InternalServerError` and maps to 502; 504 `upstream_timeout` stays our own client's
  timeout (L54). The status handler forwards no headers: `Retry-After` stays on
  `RateLimitError`'s row, the one behavior its handler does not share with the status
  handler. L71's test gains a base-class 429, 399 and 600, the factory's 503 and 504, a
  529 with `Retry-After` that the response drops, and a `RateLimitError` with and without
  it.

---

## v1.3.5 — framework error headers (patch)

Theme: one fill found while designing step 4b's handler. No invariant moves; CLAUDE.md is
unchanged.

**INFO**
- **L98 §9.4, §11, §14 — framework errors keep their headers.** Fill: L80 named the status
  the replacement handler keeps and was silent on headers, while FastAPI's default handler
  forwards `exc.headers`. A literal reading drops them and sends a 405 without `Allow`,
  which RFC 9110 requires. The handler forwards the exception's headers, as §9.4 already
  does for `Retry-After`. L80's test gains `Allow: POST` on the 405 and a 400 `http_error`
  case (a JSON body that is not valid UTF-8, which FastAPI raises as an `HTTPException`),
  so each of the handler's three branches has a test. "Routing codes" becomes "framework
  codes," since the 400 is not a routing error.

---

## v1.3.4 — refusal stop reason (patch)

Theme: one fill found while designing step 3c's loop. No statement changes, and no
invariant moves; CLAUDE.md is unchanged.

**WARNING**
- **L97 §5.4, §11, §14 — a refusal fails fast before the block lookup.** Fill: §5.4 handled
  both truncation stop reasons and a missing block, and §9.4 (L73) pinned a refusal with no
  block. A refusal *with* a tool block was unspecified: the loop would validate output the
  API had cut off, returning it as a success if it happened to validate, or buying
  validation retries against a classifier that fires again on the same input. Gated first,
  the block is never validated and the retry would be identical (invariant 16 as written).
  Same exception and code as L73's case; §9.4 is unchanged. `pause_turn`, `stop_sequence`
  and `end_turn` need no branch; a test pins every `StopReason` value to a decided path.

**Housekeeping (no ledger id — no behavior changes)**
- L49's v1.3 summary line names two of its three changes. It also covered §4.2 and §5.4:
  `OrchestratorError` carries the `usage` spent, failed attempts included — the meaning
  §4.2, §5.4, and §14 cite it for.

---

## v1.3.3 — Phase 1 build fills (patch)

Theme: three details the Phase 1 build would otherwise have decided silently, found while
sequencing the build. All three are fills; no statement changes and no invariant moves.
CLAUDE.md's CI sentence is updated in the same commit (L96); nothing else in it changes.

**WARNING**
- **L94 §5.2, §10, §14 — the output/input ratio is a knob, and the derived value is not.**
  Fill: §5.2 derived `max_output_tokens` as `≈ max_input_chars / 2`, "tunable," while
  invariant 10 bans magic numbers and §10 named no knob for the ratio — `config.py` could
  only hardcode the 2 or invent an unnamed knob. Now `output_tokens_per_input_char`
  (`gt=0`, default `0.5`, so behavior is unchanged) and
  `max_output_tokens = math.ceil(max_input_chars * ratio)`, a read-only property: as a field
  it could be set from the environment on its own, reopening "two knobs that must move
  together." Tests: a non-positive ratio raises at construction; the derived value is not
  in `Settings.model_fields`. (Rejected: a module constant — "tunable" makes it operational,
  and operational knobs live in `config.py`.)

**INFO**
- **L95 §5.2, §13, §14 — `get_client` lives in `orchestrator.py`.** Fill: §5.2 and §5.5
  specified its behavior and no module. It sits beside the `LLMClient` Protocol it returns,
  as a plain cached factory with no FastAPI import; `api.py` applies `Depends`. The module
  that owns the vendor format constructs the vendor client, and the orchestrator stays
  framework-free.
- **L96 §11, §13, §14; CLAUDE.md CI — CI runs the format check.** Fill: the spec's workflow
  said "ruff," CLAUDE.md's commands ran both `ruff check` and `ruff format --check`, and
  nothing said which one CI enforces. Both run in CI; a commit that is clean locally is
  clean on push.

---

## v1.3.2 — Phase 1 pre-build pass (patch)

Theme: a last pass over Phase 1 content before any code. Two findings came from outside the
spec — the Python SDK's 1.0 release (Aug 2026) and Anthropic's model-id scheme — and the
rest are gaps and one self-conflict in the Phase 1 surface. No design changes: every
invariant holds as stated; L82 changes how invariant 3 reaches the wire, not what it says.
CLAUDE.md invariants 3 and 15 are updated in the same commit.

**CRITICAL**
- **L82 §5.2, §5.5, §8.2, §13, §14 — `temperature` travels in `extra_body`.** Fill: the spec
  never constrained the SDK version, and SDK 1.0 removed the typed `temperature` / `top_p` /
  `top_k` parameters (`TypeError` at the call). The API still accepts the field on the
  models this call shape targets. `CALL_CONFIG` carries `extra_body={"temperature": 0}`,
  typed on our side by `SamplingBody`; the `LLMClient` Protocol declares `extra_body`; a
  fake-client test pins the value on every attempt; the smoke run records the SDK version.
  `anthropic>=1.9,<2` in `pyproject.toml`. Guard in CLAUDE.md inv. 3: deleting the field to
  satisfy the SDK is a silent invariant violation. (Rejected: pinning `anthropic<1`, which
  keeps the typed kwarg but starts the repo on a superseded major.)

**WARNING**
- **L83 §5.1, §5.2, §5.4 — the call config is typed.** Conflict: §5.4's sample
  (`messages: list[dict]`, an untyped tool dict, `**CALL_CONFIG` inferred as
  `dict[str, object]`) vs L74's SDK-typed Protocol and §14's "mypy clean" — six errors under
  `--strict`. The seam wins: `CallConfig` TypedDict, `SUMMARY_TOOL: ToolParam`,
  `messages: list[MessageParam]`. Runtime values and the `PROMPT_VERSION` recipe unchanged.
- **L84 §4.2, §5.2, §5.5, §10, §14, §17; CLAUDE.md inv. 15 — "pinned," not "dated."** Fill:
  "dated snapshot id" glossed "never an alias," and the gloss is false from the Claude 4.6
  generation on, where the dateless id is the pinned snapshot. The rule is unchanged; the
  word is corrected, and a date-suffix validator is ruled out.
- **L85 §5.2, §14 — L72's rationale corrected; the smoke run verifies the ceiling.** Fill:
  L72 said the SDK exposes no output ceiling; the Models API reports `max_tokens`. The knob
  stays declared (a boot-time fetch would put the network in CI); the L81 smoke run
  compares it against `models.retrieve(settings.model).max_tokens`.
- **L86 §4.1 — the claim's text is non-blank, like its quote.** Fill: `text` used
  `min_length=1`, so `"   "` validated and rendered as an invisible claim; L25 had already
  ruled whitespace empty at this boundary for the quote. `Quote` → `NonBlankStr`, used by
  both. `strip_whitespace` is not in the JSON schema: the tool schema is unchanged.
- **L87 §9.1, §9.4, §10 — the degenerate-input guard counts content.** Fill: a
  whitespace-only paste longer than `min_input_chars` passed the guard and bought a paid
  call. A validator checks the stripped length without mutating `raw_text` (spans index the
  exact paste from 2a). L70's test gains the whitespace case.

**INFO**
- **L88 §5.4, §11 — `model_context_window_exceeded` fails fast.** Fill: a second truncation
  stop reason; with a partial tool block it would have retried with a larger context.
  `TRUNCATION_STOPS` covers both.
- **L89 §4.2 — spine types declare domains.** Fill: L77's rule, applied to config only, now
  covers `TokenUsage` (`ge=0`, frozen) and `RunMetadata.validation_attempts` (`ge=1`).
- **L90 §14 — the Phase 1 `schemas.py` fence names its aliases.** Fill: the "ONLY" list
  omitted `Section` and `NonBlankStr`; a literal audit would have failed it.
- **L91 §13, §14; CLAUDE.md Commands — mypy runs strict.** Fill: "mypy clean" had no
  configuration; default mode missed the bare `list[dict]` that `--strict` catches.
- **L92 §9.10 — the static page renders errors.** Fill: L68's page had no non-2xx state; it
  now shows the `error` code and `request_id`, so the smoke run can't fail blank.
- **L93 §13 — the repo tree names the three documents.** Fill: §13 listed every module but
  not CLAUDE.md, the spec, or this changelog — the files the build reads most. All three sit
  at the root: CLAUDE.md must, to auto-load, and it cites the other two by bare filename.

---

## v1.3.1 — implementation decisions absorbed (patch)

Theme: the first build-room pass against v1.3 found details the spec left open and places
where it contradicted itself. They lived in CLAUDE.md as "decisions beyond spec v1.3," where
the spec-wins precedence rule ranked them *below* the text they corrected. This patch moves
each into the section it belongs to. No design changes. `(was I#)` maps each entry to its
former CLAUDE.md id; the `I#` ids are retired.

**CRITICAL**
- **L69 (was I2) §9.4, §9.8 — the 500 path logs structure, never messages.** Conflict: the
  §9.4 table's "logged in full, internally" vs L53's PHI rule. L53 wins; the row is fixed.
  Catch-all middleware inside the request-id middleware, not an `Exception` handler.
- **L70 (was I3) §9.4 — the default 422 handler is replaced.** Fill: FastAPI's default body
  echoes the entire paste as `input`.
- **L77 (was I10) §5.2, §10 — configuration fails at boot; the key is passed explicitly.**
  Fill: pydantic-settings never exports `.env` to `os.environ`, so an implicit key 401s
  everywhere except a shell that exports it. Required `SecretStr`; every knob declares its
  domain.

**WARNING**
- **L71 (was I4) §9.4 — upstream failures are attributed by status.** Conflict: the single
  `APIError` → "not my bug" row vs §9.4's rule that each code says whose fault it was. The
  rule wins: 4xx except 429 → 500, 5xx except 529 → 502, 529 → 503.
- **L74 (was I7) §5.5 — `LLMClient` declares explicit kwargs.** Conflict: `**kwargs` vs "mypy
  checks the seam." No loose signature satisfies both; the seam wins.
- **L75 (was I8) §5.2 — parallel tool use is disabled.** Conflict: §5.4's tool_result pairing
  contract vs a loop that answers only the first block. Prevented in `CALL_CONFIG`.
- **L78 (was I11) §5.2 — the client is built once per process.** Fill: FastAPI calls
  dependencies per request; `@functools.cache` on `get_client`.
- **L79 (was I12) §9.4, §9.8 — log fields render in the message.** Conflict: §9.4's `extra=`
  sample vs the requirement that every log line carries code and request id. The requirement
  wins; the sample is fixed.
- **L81 (was I14) §14 — phase 1 closes with one live smoke run.** Fill: nothing verified the
  real request shape against the real API.

**INFO**
- **L68 (was I1) §9.10, §13, §14 — the phase-1 display is a static page.** Fill: §14's
  "minimal display." `backend/static/` is sanctioned until `frontend/` lands.
- **L72 (was I5) §5.2, §10 — the model's output ceiling is a config knob.** Fill: L16 named no
  source for the ceiling.
- **L73 (was I6) §9.4 — phase-1 HTTP reach is named.** Fill: "every §9.4 row reachable in
  phase 1"; request-id middleware; the refusal path pinned.
- **L76 (was I9) §9.1, §9.10 — the phase-1 response is an edge shape.** Fill: §9.1 named no
  type. Also reconciles §9.10, which placed `SummarizeResponse` in `schemas.py` against §9.1
  and CLAUDE.md's sanctioned list.
- **L80 (was I13) §9.4 — framework default error bodies are replaced.** Fill: "every body has
  one shape" vs FastAPI's `{"detail": ...}` on 404/405.

**Housekeeping (no ledger id — no behavior changes)**
- The changelogs moved out of the spec into this file. The spec header states where history
  lives and the versioning rule.
- The sanctioned-shapes rule moved from CLAUDE.md into §13; the two spec comments that cited
  CLAUDE.md for it now cite §13.
- The spec file drops the version from its name (`PROJECT_01_NOTEPILOT.md`); the header
  carries the version.

---

## v1.3 changelog (design-room walkthrough deltas)

Severity uses the project's own triage enum. `L#` is the walkthrough ledger id; each delta
names the section it lands in. Theme of this pass: **v1.1 fixed the scoring; v1.2 fixed
what the checks can see; v1.3 fixes what the checks *assume* — where a danger comes from,
what the model is allowed to omit, and which question a test is actually asking.**

**DECISIONS (vetoable, like every D)**
- **D7 — the model is a scribe, not a consultant (§5.3).** Assessment records only what the
  clinician stated, certainty verbatim; a patient's self-diagnosis is Subjective; an empty A
  is a valid note. Reasons: authorship, product category (documentation, not decision
  support), and a prompt that no longer contradicts itself.
- **D8 — the judge stays, reframed as entailment (§8.2).** `text_entailment_judge`: is each
  claim's text entailed by its source span? One batched call, WARNING, behind an injected
  `Judge` protocol. v1.2's showcase ("BP 190/110 → hypertensive urgency") is now a
  detection trap, not sound inference.
- **D9 — cross-reactivity is keyed on the R1 side chain (§7).** The evidence the table cites
  is side-chain-level; now the table is too.
- **D10 — a dropped NKDA is a WARNING (§8.4).** Undocumented status prompts a re-ask; it is
  not a missed allergy. NKA ≠ NKDA in the lexicon.
- **D11 — corpus repeats (§8.7).** `corpus_repeats` (default 3), per-case pass fraction,
  flaky cases named, n and k beside every number.
- **D12 — `diagnosis_in_quote` ships (§8.4).** After D7 an invented assessment is a
  fabrication, and the judge can't gate a CRITICAL (inv. 7) — so a deterministic backstop.
  Certainty upgrade = CRITICAL, downgrade = WARNING.
- **D13 — `med_status_consistency` ships (§8.4).** Presence belongs to `drug_in_quote`;
  active-vs-stopped belongs to this check. One error, one finding.
- **D14 — the unspecified penicillin allergy, and reaction type (§7, §8.8).** "PCN allergy":
  penicillins CRITICAL, every cephalosporin WARNING ("specify to refine"). Reaction type is
  not extracted in v1 — a stated limitation.
- **D15 — `quote_informativeness` ships (§8.4).** A deterministic floor under the judge for
  degenerate quotes; lexicon entities count as informative ("NKDA").
- **D16 — one planted danger per trap (§8.5).** An authoring rule instead of an `about`
  field; the residual gap is stated in §8.8; `about` → backlog.
- **D17 — the omission law (§8.4; CLAUDE.md inv. 17).** Every CRITICAL check states, per
  input, what happens when the model omits it; an omission that silences the check is
  covered by another live check or declared a CI-only gap.

**CRITICAL**
- **§8.5, §4.2, §11 — injected-draft cases (L42).** v1.2 asked raw text to make a good model
  fabricate on cue; at `temperature=0` it mostly won't, so every fabrication trap would fail
  nearly every run. `EvalCase.draft` injects the planted mistake, skips the model, and runs
  free on every commit. The paid corpus now measures only model behavior.
- **§8.7, §4.2 — an error never satisfies an expectation (L43).** A crashed expected check
  was `passed=False`, therefore *fired*: the showpiece trap passed on a crash.
  `EvalResult.errored` replaces the magic `detail="check_error"`.
- **§6.4, §8.4 — consistency checks compare against the source span, not the model's quote
  (L35).** A Tier 3 quote could smuggle a swapped drug or a flipped "denies" under a yellow
  badge. `claim.text` vs `raw_text[source_span]`.
- **§7, §8.4 — the same-drug allergy was invisible (L30).** Allergens were matched as named
  against a class-keyed table: "allergic to amoxicillin" + amoxicillin passed. Allergens now
  normalize like drugs, and the check resolves drug → class → R1.
- **§8.4 — the contraindication survives the model dropping the drug (L51).** Drugs are read
  from the note ∪ `new_prescriptions(raw)`; a raw-only finding goes to the banner.

**WARNING**
- **§2, §4.2, §8.7, §17 — four metrics, never one (L3).** Detection recall, control
  specificity, model fidelity, fidelity caught. `pass_rate` is kept and never quoted alone.
- **§5.3 — never omit safety-critical facts (L50); D7's Assessment definition (L20).**
- **§5.4, §9.4 — the orchestrator boundary (L12, L13, L14).** The `try` wraps
  `model_validate` only; usage is summed across attempts, with `validation_attempts`;
  truncation on an input the route already accepted is `OutputTruncatedError` → 502, not 422.
- **§4.1 — D6 is enforced, not promised (L6).** Frozen `ClinicalClaim` / `SOAPNote`; flags
  and claims are tuples.
- **§4.2, §8.2, §9.5 — judge tokens have a write path (L7):** `EvalReport.judge_usage`.
- **§0, §13, CLAUDE.md inv. 1 — domain vs edge (L17).** The orchestrator and the judge
  client are edge adapters; evals call a `Judge` protocol, never the vendor format.
- **§6.2 — the index map survives Unicode (L26);** µ/μ folded. **§6.3 — Tier 3 runs in
  normalized space (L27).**
- **§7 — negation has a scope rule (L31),** and finding cues are split from
  medication-status cues. **`new_prescriptions` (L41)** powers live
  `new_prescription_preserved` (WARNING) and L51.
- **§8.4 — polarity in the reference checks (L36);** contraindication findings carry the
  allergy claim's id (L37).
- **§8.7 — tri-state `case_verdict` with not-applicable cases (L44); `checks_version` +
  `git_dirty` (L45); per-case catch parity and recorded all-failed runs (L46).**
- **§8.5 — Assessment fixtures (L23):** invented-A trap, hedged-A and empty-A controls.
- **§9.4, §9.8 — PHI-safe logs and error bodies (L53); LLM timeouts → 504 (L54); the spend
  cap reserves before spending (L56).**
- **§8.4, §10 — an empty note from clinical input is not green (L55).**
- **§9.5 — production lineage parity (L57).**
- **§5.2, §10 — `max_validation_retries` (L5).** Validation retries are ours; transport
  retries are the SDK's. Two loops, two names.
- **§14 — phase 2 split into 2a / 2b / 2c (L59); CI from phase 1 (L60); every phase has exit
  criteria (L61).**

**INFO**
- L1 §1 v1 is a review surface · L2 §1 unsourced market figure cut · L4 §3 principle 6
  named · L8 §4.1 `grounding_score` kept on near-misses · L9/L10 §4.2 explicit `species`,
  typed `must_not_add` · L11 §4.2 every `RunMetadata` field has a producer · L15 §5.4
  `PROMPT_VERSION` hashes the full call config · L16 §5.2 derived `max_output_tokens`
  validated at boot · L19 §5.5 the client is a `Protocol` · L24 §9.10 empty A renders ·
  L25 §4.1 quote stripped at the boundary · L29 §0 diagram fixed · L33 §7 parsed doses,
  multi-valued extractors · L38 §8.7 downgrade-only severity enforced · L40 §8.2 judge
  batched · L49 §8.6/§8.7 orphan tier entry removed, judge is a parameter · L58
  §9.8/§9.10 proxy headers, new UI states, edge-shape sanction · L62 §11 property tests
  restated · L63 §16 "Arc" vs "Phase" · L64 §17 DoD contradiction fixed.

**Found while drafting v1.3**
- **L65 (INFO) §7, §13:** `extract.py` necessarily imports `lexicons.py`; v1.2 said it
  "imports nothing." Now: `extract.py` imports only `lexicons.py`, and `lexicons.py`
  imports nothing — severities are stored as strings, so `clinical/` never imports the spine.
- **L66 (INFO) §8.5:** `detect_vital_drift` expected no eval check — it tests grounding's
  numeric guard. Moved to `tests/test_grounding.py`.
- **L67 (INFO) §7:** `ALLERGY_CLASSES` (class → members) and `DRUG_CLASSES` (member → class)
  were two encodings of one relation, free to disagree. One map: `DRUG_CLASS`.

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
