# NotePilot

**Clinical encounter text → grounded SOAP note, with a safety eval harness that catches what the model gets wrong.**

NotePilot takes free-text from a patient encounter (a transcript, a clinician's dictation, a scribe's notes) and produces a structured SOAP note. Every claim in the note is grounded back to the source text, and a deterministic safety layer checks the output for the classes of error that matter clinically — a dropped allergy, a contraindicated prescription, a severity that got downgraded in summarization.

> **Status:** Phase 1 — MVP spine. Pipeline runs end-to-end; grounding and the eval harness land in Phase 2. See [Roadmap](#roadmap).

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

_Populated when the eval harness lands in Phase 2. Reported as pass rate over the synthetic corpus, broken down by check and by case species._

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | MVP spine: paste → FastAPI → LLM tool call → `SOAPNoteDraft` → display | **in progress** |
| 2 | Grounding ladder, safety checks, synthetic trap corpus, run lineage | planned |
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
