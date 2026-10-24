# NotePilot

**Clinical encounter text → grounded SOAP note, with a safety eval harness that catches what the model gets wrong.**

NotePilot takes free-text from a patient encounter (a transcript, a clinician's dictation, a scribe's notes) and produces a structured SOAP note. Every claim in the note is grounded back to the source text, and a deterministic safety layer checks the output for the classes of error that matter clinically — a dropped allergy, a contraindicated prescription, a wrong side, a severity that got downgraded in summarization.

> **Status:** Phase 1 — MVP spine — is done, tagged `v0.1-spine`: the pipeline runs end-to-end. Phase 2a — the safety layer, proven for free — is done, tagged `v0.2a-safety`: grounding and the deterministic checks run on every note. Phase 2b — the regression thesis goes live — is done, tagged `v0.2b-corpus`: 24 model cases run against the real model, with the baseline [scorecard](#safety-scorecard) below. Phase 2c — the semantic backstop — is done, tagged `v0.2c-judge`: a second model call checks each claim against its source, at WARNING and off by default, with its first live measurement in the scorecard. See [Roadmap](#roadmap).

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

Every safety check is proven against 24 injected cases on every commit, for free. Then 24 synthetic encounters, each run 3 times against the real model, measure what the model actually does: in all six runs below it kept every labeled safety-critical fact in all 24 fidelity-trap runs, and the pipeline surfaced every planted source danger (24 of 24). The first two runs each failed 9 of 72 on one pattern (below), which v1.7's prompt change aimed at and did not move; v1.8 changed what the checks read, and all 72 of its runs pass, as do all 72 under v1.9, which added a wrong-side check, and under 2c, which added a semantic judge, with the judge off and on.

**Six corpus runs.** All on `claude-haiku-5-5` over `corpus_version` 040ccf7c0d67, on a clean tree, 72 model calls each, about two cents each at list price. The 2b baseline ran 2026-10-17 03:10 UTC at commit `26a69b0` (`prompt_version` f568c08861a1, `checks_version` 9a1ce00b525b): 91 seconds of model time, 107,763 input and 16,056 output tokens. The v1.7 run ran 2026-10-17 23:26 UTC at commit `4877d3d` (`prompt_version` a99d6d205d0e, `checks_version` 52f147266aef): 90 seconds of model time, 115,251 input and 15,406 output tokens. The v1.8 run ran 2026-10-20 22:27 UTC at commit `8f3d8dd` (`prompt_version` a99d6d205d0e, `checks_version` 9e6fc18db331): 95 seconds of model time, 115,251 input and 15,558 output tokens. The v1.9 run ran 2026-10-22 21:56 UTC at commit `6870541` (`prompt_version` a99d6d205d0e, `checks_version` 671078539429): 115 seconds of model time, 115,251 input and 15,398 output tokens. The 2c runs ran 2026-10-24 at commit `f2b2363` (`prompt_version` a99d6d205d0e, `checks_version` a7da5c8c930b), first with the judge off (04:06 UTC: 91 seconds of model time, 115,251 input and 15,535 output tokens), then on (04:10 UTC: 94 seconds, 115,251 input and 15,521 output tokens, and the judge's 292 calls, 288,072 input and 14,308 output tokens, `judge_version` 87fd74dbdba8). All six records, every run's draft included, are in [`backend/evals/runs/corpus_runs.jsonl`](backend/evals/runs/corpus_runs.jsonl). The baseline is scored here under v1.7's definitions, from its own rows; a test holds that rescoring.

| metric | what it measures | n × k | 2b baseline | v1.7 | v1.8 | v1.9 | 2c | 2c judged |
|---|---|---|---|---|---|---|---|---|
| detection recall | planted source dangers the pipeline surfaces | 8 × 3 | 100% (24/24) | 100% (24/24) | 100% (24/24) | 100% (24/24) | 100% (24/24) | 100% (24/24) |
| control specificity | clean notes that stay clean | 8 × 3 | 87.5% (21/24) | 87.5% (21/24) | 100% (24/24) | 100% (24/24) | 100% (24/24) | 100% (24/24) |
| model fidelity | fidelity traps passed | 8 × 3 | 75% (18/24) | 75% (18/24) | 100% (24/24) | 100% (24/24) | 100% (24/24) | 100% (24/24) |
| fidelity caught | of the runs where the model lost or added a labeled fact, those a live check flagged | 0 such runs | — | — | — | — | — | — |

24 cases × 3 runs is a regression tripwire, not an accuracy estimate: it shows whether a prompt or model change made things worse on these cases, not how often the model is right in general.

**What the misses were.** In the first two runs, all 9 failing runs are one pattern, and none is the model losing a fact. The model splits a sentence such as "Metformin held for CT with contrast today, resume in 48 hours." into two claims and writes one like "Resume metformin in 48 hours", citing only "resume in 48 hours". The claim is clinically right, but its quote doesn't contain the drug, so the drug-in-quote check, which flags a claim naming a drug its own quote doesn't contain, fires at CRITICAL. No preserved-fact check fired on any of the 288 model calls: every labeled allergy, medication status, pertinent negative, and rule-out survived. So no run gives fidelity caught a denominator; under its first definition, the baseline scored that same false positive as 100%.

**What v1.7 tried, and what it measured.** v1.7's prompt asks that a medication's status and its plan be one claim, quoted whole. The re-run shows the model taking half of it: the status claim now cites the whole sentence ("Metformin held" from "Metformin held, resume in 48 hours if creatinine is stable"), and a second claim still carries the plan with a short quote. The rule didn't move the 9 failures, and three more wordings probed live before v1.8 didn't either.

**What v1.8 changed, and what it measured.** v1.8 left the prompt alone and changed what the checks read: each check reads the source text a claim's quote was matched to, widened to its whole clause, where the hold sits beside the planned restart. So "Resume metformin in 48 hours if creatinine is stable" citing "resume in 48 hours if creatinine is stable" passes, while a claim continuing the held drug still fires. Under v1.8 all 72 runs pass. The model didn't change: it still splits the plan off, and v1.8's own drafts, scored under v1.7's checks, fail the same 9 runs. The number moved because the checks now read the split correctly, not because the model stopped making it.

**What v1.9 changed, and what it measured.** v1.9 added a deterministic wrong-side check: it reads the side each claim charts at a site (left, right, or bilateral, and forms like "RLQ") and fires at CRITICAL when the claim's side isn't one its source supports, under a verbatim quote too. It also changed how the checks read contracted negations ("doesn't", "never"), refused and held medication orders, denied allergies, a finding affirmed after a negation, a workup's confirming answer, and a later order's "as needed". Under v1.9 all 72 runs pass again, and none of it moved a verdict: v1.9's drafts score the same under v1.8's checks, and v1.8's under v1.9's. The wrong-side check fired on none of the 72 runs.

**What 2c added, and what it measured.** 2c added a semantic judge: a second, separate model call for each claim, asking whether the claim says only what the clause it cites says, under a strict written rule (a claim that adds a route, a unit, a diagnosis, or any other detail the source doesn't state fails). It reports at WARNING, never CRITICAL, and no case expects it, so a model's judgment never decides a verdict above. With the judge off and on, all 72 runs pass, and both runs' drafts score the same under v1.9's checks. In the judged run the judge read 292 claims and flagged one run of 72: a draft that turned "Tylenol 1 g tid prn" into "Tylenol 1 g PO TID as needed", adding a route the source doesn't give, which no deterministic check reads. To check the judge, the author labeled all 118 distinct claims of the judged run against the judge's rule, in shuffled order and without the judge's verdicts: he labels that claim not entailed and the other 117 entailed. So the judge's one flag was right, and it passed nothing the labels call wrong. The limits: one labeler, the author, not a clinician panel; that claim's label wasn't blind, since it had already been named as the judge's likely flag; 89 of the 118 claims copy their source nearly word for word, so this run is easy for a judge (on 62 hand-written hard pairs it agreed with the labels on 173 of 186 verdicts); and a judged record names the run the judge flagged, not the claim, so that claim is read from the draft. The judge costs 292 calls a run, about 2.5 times summarize's input tokens. The wrong-side check fired on none of these runs either, and no draft charted a side in the forms that check reads least well (a side after its site, or sides joined by "/" or "&"), so these runs don't test that gap.

Verdicts were stable in all six runs: no case changed verdict across its three runs, though 16 of the 24 varied their wording at the baseline, 10 under v1.7, 13 under v1.8, 10 under v1.9, and 11 in each 2c run.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | MVP spine: paste → FastAPI → LLM tool call → `SOAPNoteDraft` → display | done (`v0.1-spine`) |
| 2 | Grounding ladder, safety checks, synthetic trap corpus, run lineage, semantic judge | done (`v0.2a-safety`, `v0.2b-corpus`, `v0.2c-judge`) |
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
