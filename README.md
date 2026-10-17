# NotePilot

**Clinical encounter text → grounded SOAP note, with a safety eval harness that catches what the model gets wrong.**

NotePilot takes free-text from a patient encounter (a transcript, a clinician's dictation, a scribe's notes) and produces a structured SOAP note. Every claim in the note is grounded back to the source text, and a deterministic safety layer checks the output for the classes of error that matter clinically — a dropped allergy, a contraindicated prescription, a severity that got downgraded in summarization.

> **Status:** Phase 1 — MVP spine — is done, tagged `v0.1-spine`: the pipeline runs end-to-end. Phase 2a — the safety layer, proven for free — is done, tagged `v0.2a-safety`: grounding and the deterministic checks run on every note. Phase 2b — the regression thesis goes live — is done, tagged `v0.2b-corpus`: 24 model cases run against the real model, with the baseline [scorecard](#safety-scorecard) below. See [Roadmap](#roadmap).

---

## Who it's for, and what pain it solves

Clinicians spend a large share of each visit documenting rather than treating. LLM summarizers can draft that documentation in seconds, but a note that *reads* correct and *is* wrong is worse than no note at all: the errors are silent, the clinician signs it under time pressure, and the mistake lands in the chart.

NotePilot's bet is that the summarizer is the easy part. The product is the layer around it that makes the output **verifiable** — where each sentence came from, and which safety checks it passed or failed — so a clinician can review in seconds instead of re-reading the whole encounter.

## What makes it different

- **Grounding, not vibes.** Every SOAP field is mapped back to spans of the source text via a deterministic matching ladder. Unsupported claims are flagged, not silently kept.
- **A safety eval harness as a first-class artifact.** A synthetic corpus of encounters with planted traps (fidelity traps, detection traps, and clean controls) scores every build. The number on the scorecard is the product's safety record, not a marketing claim.
- **Judgment to the model, mechanics to the code.** The LLM does the summarization. Allergy extraction, drug-class lookups, contraindication checks, and severity comparison are plain Python — testable, deterministic, and auditable.
- **Dual-mode runner.** The same checks run in CI against the corpus and in production against live output, so what's tested is what ships.

## Architecture

```
raw encounter text
       │
       ▼
 orchestrator.py ── Anthropic tool use ──► SOAPNoteDraft
       │
       ▼
 grounding.py ─── matching ladder ───────► SOAPNote  (each claim ↔ source spans)
       │
       ▼
 evals/runner.py ─ safety checks ────────► SummarizationResult
       │
       ▼
 api.py (FastAPI) ────────────────────────► review UI (React)
```

Dependencies point inward toward `backend/schemas.py`. The domain models know nothing about FastAPI, Postgres, or Anthropic.

```
backend/
├── schemas.py        the spine — Pydantic contracts shared by every layer
├── config.py         settings (pydantic-settings)
├── orchestrator.py   text → SOAPNoteDraft (LLM call)
├── grounding.py      SOAPNoteDraft → SOAPNote (pure)         [phase 2]
├── clinical/         extraction primitives + lexicons        [phase 2]
├── evals/            checks, registry, runner, trap corpus   [phase 2]
├── api.py            FastAPI routes (composition root)
└── db.py             persistence                             [phase 3]
tests/                unit + integration, deterministic, every commit
```

## Safety scorecard

Every safety check is proven against 21 injected cases on every commit, for free. Then 24 synthetic encounters, each run 3 times against the real model, measure what the model actually does: it kept every labeled safety-critical fact in all 24 fidelity-trap runs, the pipeline surfaced every planted source danger (24 of 24), and clean notes stayed clean 21 of 24 times. All 9 failing runs, 6 fidelity and 3 control, trace to one strict check firing on correct claims (below); the next prompt revision is measured against this run.

**Baseline, run 2026-10-17 03:10 UTC.** `claude-haiku-5-5`, `prompt_version` f568c08861a1, at commit `26a69b0` on a clean tree; `corpus_version` 040ccf7c0d67, `checks_version` 9a1ce00b525b. 72 model calls, 91 seconds of model time, 107,763 input and 16,056 output tokens: about two cents at list price. The full record, every run's draft included, is [`backend/evals/runs/corpus_runs.jsonl`](backend/evals/runs/corpus_runs.jsonl).

| metric | what it measures | n × k | result |
|---|---|---|---|
| detection recall | planted source dangers the pipeline surfaces | 8 × 3 | 100% (24/24) |
| control specificity | clean notes that stay clean | 8 × 3 | 87.5% (21/24) |
| model fidelity | fidelity traps passed | 8 × 3 | 75% (18/24) |
| fidelity caught | failed fidelity runs a live check flagged | 6 failed runs | 100%, but see below |

24 cases × 3 runs is a regression tripwire, not an accuracy estimate: it shows whether a prompt or model change made things worse on these cases, not how often the model is right in general.

**What the misses were.** All 9 failing runs are one pattern, and none is the model losing a fact. The model split a sentence such as "Metformin held for CT with contrast today, resume in 48 hours." into two claims and wrote "Resume metformin in 48 hours", citing only "resume in 48 hours". The claim is clinically right, but its quote doesn't contain the drug, so the drug-in-quote check, which flags a claim naming a drug its own quote doesn't contain, fires at CRITICAL. No preserved-fact check fired on any of the 72 runs: every labeled allergy, medication status, pertinent negative, and rule-out survived. So the fidelity-caught 100% counts that same false positive, not a caught model error, and measures nothing yet.

The fix chosen changes the prompt: it asks the model to quote every drug a claim names. It and a fidelity-caught that counts only real model errors are recorded for the next revision, which re-runs this corpus ([#9](https://github.com/calvinpatel/notepilot/issues/9), entries 20 and 21); this table will then show both runs. Verdicts were stable: no case changed verdict across its three runs, though 16 of the 24 varied their wording.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | MVP spine: paste → FastAPI → LLM tool call → `SOAPNoteDraft` → display | done (`v0.1-spine`) |
| 2 | Grounding ladder, safety checks, synthetic trap corpus, run lineage | **in progress**: 2a done (`v0.2a-safety`), 2b done (`v0.2b-corpus`) |
| 3 | Postgres persistence, React review UI (inline highlights + safety banner), CI + live deploy | planned |
| 4 | RAG cross-check against drug-interaction and guideline references | planned |

Out of scope for v1: EHR integration, real patient data, multi-user auth. NotePilot is a portfolio project and is not a medical device.

## Running it locally

Requires [uv](https://docs.astral.sh/uv/) and an Anthropic API key.

```bash
git clone git@github.com:calvinpatel/notepilot.git
cd notepilot
uv sync
cp .env.example .env        # then add your ANTHROPIC_API_KEY
uv run uvicorn backend.api:app --reload
```

Open http://127.0.0.1:8000/docs for the API.

```bash
uv run pytest               # unit + integration (no API calls)
uv run ruff check .         # lint
```

## Author

Calvin Patel — [calvinpatel.dev](https://calvinpatel.dev) · [GitHub](https://github.com/calvinpatel)

Neuroscience BS (UCLA) · MHS (UMSOM) · building AI products where clinical judgment is the moat.
