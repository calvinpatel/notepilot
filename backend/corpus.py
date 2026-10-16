"""A corpus run: every model case summarized and scored k times, with its lineage (spec §8.7).

EDGE (L188): settings, the API, git, and runs/ meet here. The pure halves live in
evals/runner.py; this module only orchestrates them.

A run spends money on every call, and the record is written last, so plan_run refuses four
things before the first call (L235): no model cases, a duplicated case id, a tree git can't
read, and a runs_path that can't take the record. After the calls, one case's exception
becomes one errored row (L46, L208), and a run where every case failed still writes its
record.
"""

import asyncio
import logging
import subprocess
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from backend.config import settings
from backend.evals.judge import Judge
from backend.evals.loader import corpus_version
from backend.evals.runner import (
    CHECKS_VERSION,
    case_result,
    corpus_metrics,
    errored_case,
    run_checks,
)
from backend.grounding import ground
from backend.orchestrator import PROMPT_VERSION, LLMClient, OrchestratorError, summarize
from backend.schemas import (
    CaseResult,
    CorpusRunRecord,
    EvalCase,
    SummarizationResult,
    TokenUsage,
)
from backend.tracebacks import format_frames

logger = logging.getLogger(__name__)


def current_git_sha() -> str:
    """HEAD's commit; CalledProcessError outside a checkout, where git exits 128 (L207)."""
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def git_is_dirty() -> bool:
    """Whether the tree differs from HEAD: tracked changes and untracked files (L207, L236).

    --untracked-files=normal overrides status.showUntrackedFiles, which would otherwise hide
    an untracked case YAML. Ignored files never count. --no-optional-locks keeps the read
    from taking index.lock under another git process on the same checkout.
    """
    out = subprocess.run(
        ["git", "--no-optional-locks", "status", "--porcelain", "--untracked-files=normal"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out != ""


def prepare_runs_path(path: Path) -> None:
    """Make path's parent and refuse a path that isn't a file, before the first call.

    Never creates the file: an empty untracked record shows in git status, so the run's own
    output would read as a dirty tree (L235). A parent blocked by a file raises OSError from
    mkdir.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.is_file():
        raise ValueError(f"runs_path={path} exists and is not a file: the record can't land")


def append_jsonl(path: Path, record: BaseModel) -> None:
    """One record, one line: JSON escapes the newlines inside its strings (L238)."""
    with path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")


@dataclass(frozen=True)
class RunPlan:
    """What plan_run settled before any spend: the cases to run and the tree they ran on."""

    model_cases: tuple[EvalCase, ...]
    git_sha: str
    git_dirty: bool


def plan_run(cases: list[EvalCase]) -> RunPlan:
    """The pre-spend refusals: no model case, a duplicated id, an unreadable tree, a bad runs_path.

    Each raises before the first call (L207, L235). The model cases are sorted by id, so a
    run's rows diff by (case, repeat) whatever order the caller passed. Injected cases are
    pytest's (§8.5).
    """
    model_cases = tuple(sorted((c for c in cases if c.draft is None), key=lambda c: c.id))
    if not model_cases:
        raise ValueError("no model cases — refusing to emit metrics over nothing")
    duplicated = sorted(i for i, n in Counter(c.id for c in model_cases).items() if n > 1)
    if duplicated:
        raise ValueError(f"duplicate model case ids {duplicated}: the record counts distinct ids")
    git_sha, git_dirty = current_git_sha(), git_is_dirty()
    prepare_runs_path(settings.runs_path)
    return RunPlan(model_cases=model_cases, git_sha=git_sha, git_dirty=git_dirty)


async def score_corpus(
    cases: list[EvalCase],
    *,
    client: LLMClient,
    judge_factory: Callable[[], Judge] | None,
) -> CorpusRunRecord:
    """Summarize and score every model case corpus_repeats times; append and return the record.

    Calls run concurrently, at most corpus_concurrency in flight (D11, L202). Each repeat's
    row keeps its cost, its draft, and summarize's wall time (L186, L201, L203).
    """
    plan = plan_run(cases)
    config = settings.checks_config()  # L187: built once, here, and recorded whole
    sem = asyncio.Semaphore(settings.corpus_concurrency)

    async def run_one(case: EvalCase, repeat: int) -> tuple[CaseResult, TokenUsage]:
        async with sem:
            result: SummarizationResult | None = None
            wall_s: float | None = None
            started = time.perf_counter()  # L201: inside the semaphore
            try:  # L208: every step inside
                result = await summarize(case.raw_text, client=client)
                wall_s = time.perf_counter() - started
                judge = judge_factory() if judge_factory is not None else None  # per case
                note = ground(result.draft, case.raw_text, config=config)
                report = await run_checks(
                    note, case.raw_text, case, mode="ci", config=config, judge=judge
                )
                row = case_result(case, repeat, report, result, summarize_wall_s=wall_s)
                return row, report.judge_usage
            except OrchestratorError as e:  # summarize raised: its clock stops here
                failed = errored_case(
                    case,
                    repeat,
                    e.code,
                    usage=e.usage,
                    validation_attempts=e.validation_attempts,
                    draft=None,
                    summarize_wall_s=time.perf_counter() - started,
                )
                return failed, TokenUsage()
            except Exception as e:  # L46: an APIError on one case can't discard the rest
                logger.error(  # L113: L69's form, never the message
                    "case_crashed code=case_errored case=%s exc_type=%s frames=%s",
                    case.id,
                    type(e).__name__,
                    format_frames(e),
                )
                # L186, L203: a crash after summarize returned keeps the cost and the draft
                meta = result.metadata if result is not None else None
                failed = errored_case(
                    case,
                    repeat,
                    type(e).__name__,
                    usage=None if meta is None else meta.usage,
                    validation_attempts=None if meta is None else meta.validation_attempts,
                    draft=None if result is None else result.draft,
                    summarize_wall_s=(time.perf_counter() - started if wall_s is None else wall_s),
                )
                return failed, TokenUsage()

    pairs = await asyncio.gather(
        *(run_one(c, r) for c in plan.model_cases for r in range(settings.corpus_repeats))
    )
    results = [row for row, _ in pairs]
    record = CorpusRunRecord(
        ran_at=datetime.now(UTC),
        git_sha=plan.git_sha,
        git_dirty=plan.git_dirty,  # L45, L207
        model=settings.model,
        prompt_version=PROMPT_VERSION,  # L46: known without a successful call,
        corpus_version=corpus_version(list(plan.model_cases)),  # so an all-failed run is
        checks_version=CHECKS_VERSION,  # still recorded: the one most need to see
        checks_config=config,
        judge_enabled=judge_factory is not None,
        repeats=settings.corpus_repeats,
        concurrency=settings.corpus_concurrency,  # L202
        n_cases=len(plan.model_cases),
        metrics=corpus_metrics(results),
        usage=sum((r.usage for r in results if r.usage is not None), TokenUsage()),  # L186
        judge_usage=sum((j for _, j in pairs), TokenUsage()),
        cases=results,
    )
    append_jsonl(settings.runs_path, record)
    return record
