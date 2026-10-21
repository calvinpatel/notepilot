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

Every safety check is proven against 21 injected cases on every commit, for free. Then 24 synthetic encounters, each run 3 times against the real model, measure what the model actually does: in all three runs below it kept every labeled safety-critical fact in all 24 fidelity-trap runs, and the pipeline surfaced every planted source danger (24 of 24). The first two runs each failed 9 of 72 on one pattern (below), which v1.7's prompt change aimed at and did not move; v1.8 changed what the checks read, and all 72 of its runs pass.

**Three corpus runs.** All on `claude-haiku-5-5` over `corpus_version` 040ccf7c0d67, on a clean tree, 72 model calls each, about two cents each at list price. The 2b baseline ran 2026-10-17 03:10 UTC at commit `26a69b0` (`prompt_version` f568c08861a1, `checks_version` 9a1ce00b525b): 91 seconds of model time, 107,763 input and 16,056 output tokens. The v1.7 run ran 2026-10-17 23:26 UTC at commit `4877d3d` (`prompt_version` a99d6d205d0e, `checks_version` 52f147266aef): 90 seconds of model time, 115,251 input and 15,406 output tokens. The v1.8 run ran 2026-10-20 22:27 UTC at commit `8f3d8dd` (`prompt_version` a99d6d205d0e, `checks_version` 9e6fc18db331): 95 seconds of model time, 115,251 input and 15,558 output tokens. All three records, every run's draft included, are in [`backend/evals/runs/corpus_runs.jsonl`](backend/evals/runs/corpus_runs.jsonl). The baseline is scored here under v1.7's definitions, from its own rows; a test holds that rescoring.

| metric | what it measures | n × k | 2b baseline | v1.7 | v1.8 |
|---|---|---|---|---|---|
| detection recall | planted source dangers the pipeline surfaces | 8 × 3 | 100% (24/24) | 100% (24/24) | 100% (24/24) |
| control specificity | clean notes that stay clean | 8 × 3 | 87.5% (21/24) | 87.5% (21/24) | 100% (24/24) |
| model fidelity | fidelity traps passed | 8 × 3 | 75% (18/24) | 75% (18/24) | 100% (24/24) |
| fidelity caught | of the runs where the model lost or added a labeled fact, those a live check flagged | 0 such runs | — | — | — |

24 cases × 3 runs is a regression tripwire, not an accuracy estimate: it shows whether a prompt or model change made things worse on these cases, not how often the model is right in general.

**What the misses were.** In the first two runs, all 9 failing runs are one pattern, and none is the model losing a fact. The model splits a sentence such as "Metformin held for CT with contrast today, resume in 48 hours." into two claims and writes one like "Resume metformin in 48 hours", citing only "resume in 48 hours". The claim is clinically right, but its quote doesn't contain the drug, so the drug-in-quote check, which flags a claim naming a drug its own quote doesn't contain, fires at CRITICAL. No preserved-fact check fired on any of the 216 model calls: every labeled allergy, medication status, pertinent negative, and rule-out survived. So no run gives fidelity caught a denominator; under its first definition, the baseline scored that same false positive as 100%.

**What v1.7 tried, and what it measured.** v1.7's prompt asks that a medication's status and its plan be one claim, quoted whole. The re-run shows the model taking half of it: the status claim now cites the whole sentence ("Metformin held" from "Metformin held, resume in 48 hours if creatinine is stable"), and a second claim still carries the plan with a short quote. The rule didn't move the 9 failures, and three more wordings probed live before v1.8 didn't either.

**What v1.8 changed, and what it measured.** v1.8 left the prompt alone and changed what the checks read: each check reads the source text a claim's quote was matched to, widened to its whole clause, where the hold sits beside the planned restart. So "Resume metformin in 48 hours if creatinine is stable" citing "resume in 48 hours if creatinine is stable" passes, while a claim continuing the held drug still fires. Under v1.8 all 72 runs pass. The model didn't change: it still splits the plan off, and v1.8's own drafts, scored under v1.7's checks, fail the same 9 runs. The number moved because the checks now read the split correctly, not because the model stopped making it. Verdicts were stable in all three runs: no case changed verdict across its three runs, though 16 of the 24 varied their wording at the baseline, 10 under v1.7, and 13 under v1.8.

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
