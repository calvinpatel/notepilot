"""The check engine, the per-case verdict, and the checks' lineage (spec §8.7).

run_checks runs the selected checks on one note. It fails closed per check (invariant 12): a
check that raises, returns a finding above its severity (L38), or names a claim the note
lacks (L115) becomes one errored result, logged in L69's form (L113), and the rest still run.

case_verdict scores one case's report against the case's answer key (invariant 11).
case_result and errored_case build a corpus run's row for one repeat of a case, and
corpus_metrics reads a run's rows into its rates (L3, L205, L206).

CHECKS_VERSION hashes the source that decides verdicts, so a corpus run records which checks
judged it (L45, L114).
"""

import hashlib
import inspect
import json
import logging
from pathlib import Path
from typing import Final, Literal

# the import registers the roster: its side effect is the point (§8.7)
import backend.evals.checks  # noqa: F401
from backend.evals.judge import Judge
from backend.evals.registry import REGISTRY, stamp
from backend.schemas import (
    CaseResult,
    CaseStatus,
    ChecksConfig,
    CorpusMetrics,
    EvalCase,
    EvalReport,
    EvalResult,
    Severity,
    SOAPNote,
    SOAPNoteDraft,
    SummarizationResult,
    TokenUsage,
)
from backend.tracebacks import format_frames

logger = logging.getLogger(__name__)


def checks_version(root: Path) -> str:
    """Twelve hex digits over root's checks source: evals/, clinical/, grounding.py, schemas.py.

    schemas.py counts (L189): it holds verdict logic, all_critical_passed and EvalResult's
    errored-never-passes validator. Its other edits move the version too, which errs safe.

    Source is the .py files (L114): case YAMLs have corpus_version, and runs/corpus_runs.jsonl
    changes on every run. Each file enters with its path relative to root, so a moved or
    renamed file moves the version; the paths are sorted, since listing order varies by
    filesystem.
    """
    files = [root / "grounding.py", root / "schemas.py"]
    for package in ("evals", "clinical"):
        files.extend((root / package).rglob("*.py"))  # nothing, while a package doesn't exist
    payload = sorted(
        (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in files
    )
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:12]


# over backend/, computed at import (§8.7)
CHECKS_VERSION: Final = checks_version(Path(__file__).resolve().parents[1])


async def run_checks(
    note: SOAPNote,
    raw_text: str,
    case: EvalCase | None = None,
    *,
    mode: Literal["production", "ci"],
    config: ChecksConfig,
    judge: Judge | None = None,
) -> EvalReport:
    """Run the selected checks on one note (§8.7).

    Selected: every check in ci mode, the reference-free ones in production, and a judged
    check only when a judge is given (L49). Every check gets the config (L190), which the
    caller builds at the edge (L187), and the report carries it (L334), as it carries a given
    judge's usage and version (L7, L336).
    """
    selected = [
        c
        for c in REGISTRY.values()
        if (mode == "ci" or not c.requires_reference) and (not c.needs_judge or judge is not None)
    ]
    claim_ids = {c.id for c in note.claims}
    results: list[EvalResult] = []
    for check in selected:
        try:
            out = (
                check.fn(note, raw_text, case, config=config, judge=judge)
                if check.needs_judge
                else check.fn(note, raw_text, case, config=config)
            )
            findings = await out if inspect.isawaitable(out) else out
            stamped = [stamp(check, f) for f in findings]  # a bad finding is a bad check
            if any(i not in claim_ids for r in stamped for i in r.claim_ids):  # L115
                raise ValueError(f"{check.name}: a finding names a claim the note lacks")
        except Exception as exc:
            # Not a passed check, and not a 500. Logged in L69's form: the message and
            # exc_info can carry note content (L53). CancelledError is a BaseException, so
            # it passes through.
            logger.error(
                "check_crashed code=check_errored check=%s exc_type=%s frames=%s",
                check.name,
                type(exc).__name__,
                format_frames(exc),
            )
            results.append(
                EvalResult(
                    check=check.name,
                    severity=check.severity,
                    passed=False,
                    errored=True,
                    detail="check errored",
                )
            )
            continue
        results.extend(
            stamped or [EvalResult(check=check.name, severity=check.severity, passed=True)]
        )
    return EvalReport(
        results=results,
        checks_run=frozenset(c.name for c in selected),
        checks_version=CHECKS_VERSION,
        judge_usage=judge.usage if judge is not None else TokenUsage(),
        checks_config=config,
        judge_version=judge.version if judge is not None else None,
    )


def case_verdict(report: EvalReport, case: EvalCase) -> CaseStatus:
    """The case's status against its answer key, its expected_flags (§8.7; invariant 11).

    not_applicable when no check ran (L117) or an expected check didn't run (L44). Otherwise
    failed when an expected check errored or any CRITICAL errored (L43); passed when every
    expected check fired and every CRITICAL that fired was expected; else failed.
    CRITICAL-scoped on purpose: an unexpected WARNING doesn't fail a case.
    """
    expected = set(case.expected_flags)
    # L117: a run that checked nothing scores no case; L44: nor one an expected check missed
    if not report.checks_run or not expected <= report.checks_run:
        return "not_applicable"
    errored = {r.check for r in report.results if r.errored}
    if errored & expected or any(r.errored for r in report.critical_results):
        return "failed"
    fired = {r.check for r in report.results if not r.passed and not r.errored}
    fired_critical = {r.check for r in report.critical_results if not r.passed and not r.errored}
    return "passed" if expected <= fired and fired_critical <= expected else "failed"


def case_result(
    case: EvalCase,
    repeat: int,
    report: EvalReport,
    result: SummarizationResult,
    *,
    summarize_wall_s: float,
) -> CaseResult:
    """One repeat's row when summarize returned and the checks ran (§8.7).

    The status is case_verdict's. Each list of check names is sorted (L228), and each fired
    check maps to the claims it fired on, sorted (L335).
    """
    expected = set(case.expected_flags)
    fired_results = [r for r in report.results if not r.passed and not r.errored]
    fired = {r.check for r in fired_results}
    return CaseResult(
        case_id=case.id,
        repeat=repeat,
        species=case.species,
        status=case_verdict(report, case),
        fired_checks=sorted(fired),
        fired_critical=sorted(
            {r.check for r in fired_results if r.severity is Severity.CRITICAL}  # L224
        ),
        missing_expected=sorted(expected - fired),
        unexpected_fired=sorted(fired - expected),
        usage=result.metadata.usage,
        validation_attempts=result.metadata.validation_attempts,
        summarize_wall_s=summarize_wall_s,
        draft=result.draft,
        errored_checks=sorted({r.check for r in report.results if r.errored}),
        fired_claim_ids={
            c: sorted({i for r in fired_results if r.check == c for i in r.claim_ids})
            for c in sorted(fired)
        },
    )


def errored_case(
    case: EvalCase,
    repeat: int,
    code: str,
    *,
    usage: TokenUsage | None,
    validation_attempts: int | None,
    draft: SOAPNoteDraft | None,
    summarize_wall_s: float,
) -> CaseResult:
    """One repeat's row when the pipeline failed: failed, with the error's code (L205, L53).

    No check result reached the row, so it names no fired or errored check, records no claim
    ids (L335), and every expected flag is missing (L228). The cost and the draft are
    whatever survived (L186, L203).
    """
    return CaseResult(
        case_id=case.id,
        repeat=repeat,
        species=case.species,
        status="failed",
        fired_checks=[],
        fired_critical=[],
        missing_expected=sorted(set(case.expected_flags)),
        unexpected_fired=[],
        usage=usage,
        validation_attempts=validation_attempts,
        summarize_wall_s=summarize_wall_s,
        draft=draft,
        error=code,
    )


def _rate(rows: list[CaseResult]) -> float | None:
    """Repeats passed over repeats applicable; None when no repeat is applicable (L205)."""
    applicable = [row for row in rows if row.status != "not_applicable"]
    if not applicable:
        return None
    return sum(row.status == "passed" for row in applicable) / len(applicable)


def corpus_metrics(results: list[CaseResult]) -> CorpusMetrics:
    """A corpus run's rates and flaky cases, read from its rows (§8.7; L3, D11).

    fidelity_caught reads each row's fired_critical against the registry. Its denominator is
    the fidelity repeats where a reference check fired at CRITICAL, so the model lost or added
    a labeled fact (L253); a repeat among them is caught when a reference-free check fired at
    CRITICAL too (L206, L224). An errored check is not a catch (L230). A case is flaky when its
    pass fraction over its applicable repeats without a pipeline error is strictly between 0
    and 1 (L229, L254).
    """
    by_species = {
        species: [row for row in results if row.species == species]
        for species in ("detection", "control", "fidelity")
    }
    labeled_errors = [
        row
        for row in by_species["fidelity"]
        if any(REGISTRY[check].requires_reference for check in row.fired_critical)
    ]
    caught = [
        row
        for row in labeled_errors
        if any(not REGISTRY[check].requires_reference for check in row.fired_critical)
    ]
    by_case: dict[str, list[CaseResult]] = {}
    for row in results:
        if row.error is None:  # L254: an upstream failure isn't the reply varying
            by_case.setdefault(row.case_id, []).append(row)
    flaky = [
        case_id
        for case_id, rows in by_case.items()
        if (rate := _rate(rows)) is not None and 0 < rate < 1
    ]
    return CorpusMetrics(
        detection_recall=_rate(by_species["detection"]),
        control_specificity=_rate(by_species["control"]),
        model_fidelity=_rate(by_species["fidelity"]),
        fidelity_caught=len(caught) / len(labeled_errors) if labeled_errors else None,
        pass_rate=_rate(results),
        flaky_cases=sorted(flaky),
    )
