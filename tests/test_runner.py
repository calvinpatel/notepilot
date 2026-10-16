"""Pins the check engine, the per-case verdict, the checks' lineage, and a corpus run's rows
and metrics (spec §8.7; L38, L43–L45, L49, L113–L115, L205, L206, L224, L228–L230).
"""

import asyncio
import logging
from pathlib import Path
from typing import Literal

import pytest

from backend.evals.judge import Judge
from backend.evals.registry import Check, Finding, register_check
from backend.evals.runner import (
    CHECKS_VERSION,
    case_result,
    case_verdict,
    checks_version,
    corpus_metrics,
    errored_case,
    run_checks,
)
from backend.schemas import (
    CaseResult,
    CaseStatus,
    ChecksConfig,
    ClinicalClaim,
    EvalCase,
    EvalReport,
    EvalResult,
    RunMetadata,
    Severity,
    SOAPNote,
    SOAPNoteDraft,
    Species,
    SummarizationResult,
    TokenUsage,
)
from tests.fakes import CHECKS_CONFIG, FakeJudge

_C, _W = Severity.CRITICAL, Severity.WARNING
RAW = "raw text"
MESSAGE_SENTINEL = "sentinel-msg-5f02"
CAUSE_SENTINEL = "sentinel-cause-a7c1"


def _note(*ids: int) -> SOAPNote:
    claims = (
        ClinicalClaim(id=i, text=f"claim {i}", section="S", source_quote=f"quote {i}") for i in ids
    )
    return SOAPNote(claims=tuple(claims))


def _case() -> EvalCase:
    return EvalCase(id="case-1", species="control", raw_text=RAW, trap=None)


def _errored(check: str, severity: Severity) -> EvalResult:
    """The one result a check that fails closed becomes (invariant 12)."""
    return EvalResult(
        check=check, severity=severity, passed=False, errored=True, detail="check errored"
    )


def _clean(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
) -> list[Finding]:
    return []


def _judged_clean(
    note: SOAPNote,
    raw_text: str,
    case: EvalCase | None = None,
    *,
    config: ChecksConfig,
    judge: Judge,
) -> list[Finding]:
    return []


class _Crash(Exception):
    """A local type: a hard-coded exc_type literal can't match a builtin's name."""


def _crashing(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
) -> list[Finding]:
    try:
        raise ValueError(CAUSE_SENTINEL)
    except ValueError as cause:
        raise _Crash(MESSAGE_SENTINEL) from cause


# --- selection and results ----------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "with_judge", "selected"),
    [
        ("production", False, {"plain"}),
        ("production", True, {"plain", "judged"}),
        ("ci", False, {"plain", "reference"}),
        ("ci", True, {"plain", "reference", "judged", "reference-judged"}),
    ],
    ids=["production", "production-judged", "ci", "ci-judged"],
)
async def test_run_checks_selects_by_mode_and_judge(
    registry: dict[str, Check],
    mode: Literal["production", "ci"],
    with_judge: bool,
    selected: set[str],
) -> None:
    register_check(name="plain", severity=_W)(_clean)
    register_check(name="reference", severity=_W, requires_reference=True)(_clean)
    register_check(name="judged", severity=_W, needs_judge=True)(_judged_clean)
    register_check(name="reference-judged", severity=_W, requires_reference=True, needs_judge=True)(
        _judged_clean
    )
    report = await run_checks(
        _note(), RAW, mode=mode, config=CHECKS_CONFIG, judge=FakeJudge() if with_judge else None
    )
    assert report.checks_run == selected  # L44: what ran, so "didn't run" isn't "didn't fire"
    assert {r.check for r in report.results} == selected


@pytest.mark.anyio
async def test_run_checks_passes_each_check_its_arguments(registry: dict[str, Check]) -> None:
    seen: dict[str, tuple[object, ...]] = {}

    @register_check(name="plain", severity=_W)
    def plain(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
    ) -> list[Finding]:
        seen["plain"] = (note, raw_text, case, config)
        return []

    @register_check(name="judged", severity=_W, needs_judge=True)
    async def judged(
        note: SOAPNote,
        raw_text: str,
        case: EvalCase | None = None,
        *,
        config: ChecksConfig,
        judge: Judge,
    ) -> list[Finding]:
        seen["judged"] = (note, raw_text, case, config, judge)
        return []

    # a config of its own, so `is` proves the one passed in is the one each check gets (L190)
    config = ChecksConfig(fuzzy_score_cutoff=73.5, min_quote_content_tokens=4)
    note, case, judge = _note(1), _case(), FakeJudge()
    await run_checks(note, RAW, case, mode="ci", config=config, judge=judge)
    want_plain = (note, RAW, case, config)
    assert [a is b for a, b in zip(seen["plain"], want_plain, strict=True)] == [True] * 4
    want_judged = (note, RAW, case, config, judge)
    assert [a is b for a, b in zip(seen["judged"], want_judged, strict=True)] == [True] * 5


@pytest.mark.anyio
async def test_run_checks_turns_findings_into_results_and_a_clean_check_into_a_pass(
    registry: dict[str, Check],
) -> None:
    register_check(name="clean", severity=_C)(_clean)

    @register_check(name="findings", severity=_C)
    async def findings(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
    ) -> list[Finding]:
        return [Finding(detail="detail-1", claim_ids=(2,)), Finding(detail="detail-2", severity=_W)]

    report = await run_checks(_note(1, 2), RAW, mode="production", config=CHECKS_CONFIG)
    assert report.results == [
        EvalResult(check="clean", severity=_C, passed=True),
        EvalResult(check="findings", severity=_C, passed=False, detail="detail-1", claim_ids=(2,)),
        EvalResult(check="findings", severity=_W, passed=False, detail="detail-2"),
    ]


@pytest.mark.anyio
async def test_the_report_carries_the_judges_usage_and_checks_version(
    registry: dict[str, Check],
) -> None:
    usage = TokenUsage(input_tokens=7, output_tokens=3)
    judged = await run_checks(
        _note(), RAW, mode="production", config=CHECKS_CONFIG, judge=FakeJudge(usage=usage)
    )
    unjudged = await run_checks(_note(), RAW, mode="production", config=CHECKS_CONFIG)
    assert (judged.judge_usage, unjudged.judge_usage) == (usage, TokenUsage())  # L7
    assert judged.checks_version == CHECKS_VERSION  # L45


# --- fail-closed (invariant 12) -----------------------------------------------


@pytest.mark.anyio
async def test_a_check_that_raises_becomes_one_errored_result_and_the_rest_run(
    registry: dict[str, Check],
) -> None:
    register_check(name="crash", severity=_C)(_crashing)
    register_check(name="after", severity=_W)(_clean)
    report = await run_checks(_note(), RAW, mode="production", config=CHECKS_CONFIG)
    assert report.results == [
        _errored("crash", _C),
        EvalResult(check="after", severity=_W, passed=True),
    ]
    assert report.checks_run == {"crash", "after"}


@pytest.mark.anyio
async def test_a_crashed_check_is_logged_by_structure_never_its_message(
    registry: dict[str, Check], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    register_check(name="crash", severity=_C)(_crashing)
    await run_checks(_note(), RAW, mode="production", config=CHECKS_CONFIG)
    assert MESSAGE_SENTINEL not in caplog.text  # L113: no str(exc), no exc_info
    assert CAUSE_SENTINEL not in caplog.text  # nor the chained cause
    ours = [r for r in caplog.records if r.name == "backend.evals.runner"]
    assert len(ours) == 1
    assert (ours[0].levelno, ours[0].exc_info) == (logging.ERROR, None)
    fields = ours[0].getMessage().split(" ")
    assert fields[:4] == ["check_crashed", "code=check_errored", "check=crash", "exc_type=_Crash"]
    assert len(fields) == 5 and fields[4].startswith("frames=")
    frames = fields[4].removeprefix("frames=").split(">")
    # L69's frames: the engine outermost, the check's raise innermost
    assert frames[0].startswith("backend/evals/runner.py:") and frames[0].endswith(":run_checks")
    assert frames[-1].startswith("tests/test_runner.py:") and frames[-1].endswith(":_crashing")


@pytest.mark.anyio
async def test_a_finding_above_its_checks_severity_errors_the_check(
    registry: dict[str, Check],
) -> None:
    @register_check(name="upgrade", severity=_W)
    def upgrade(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
    ) -> list[Finding]:
        return [Finding(detail="detail-1", severity=_C)]

    report = await run_checks(_note(), RAW, mode="production", config=CHECKS_CONFIG)
    assert report.results == [_errored("upgrade", _W)]  # L38


@pytest.mark.anyio
@pytest.mark.parametrize(
    "claim_ids", [(3,), (-1,), (1, 3)], ids=["past-the-last", "negative", "one-of-two"]
)
async def test_a_finding_naming_a_claim_the_note_lacks_errors_the_check(
    registry: dict[str, Check], claim_ids: tuple[int, ...]
) -> None:
    # L115: no claim card would show it, and it isn't note-level, so it would render nowhere
    @register_check(name="stray", severity=_C)
    def stray(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
    ) -> list[Finding]:
        return [Finding(detail="detail-1", claim_ids=claim_ids)]

    report = await run_checks(_note(1, 2), RAW, mode="production", config=CHECKS_CONFIG)
    assert report.results == [_errored("stray", _C)]


@pytest.mark.anyio
async def test_cancellation_passes_through(registry: dict[str, Check]) -> None:
    # CancelledError is a BaseException: the per-check except must not absorb it
    @register_check(name="cancelled", severity=_C)
    async def cancelled(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
    ) -> list[Finding]:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await run_checks(_note(), RAW, mode="production", config=CHECKS_CONFIG)


# --- CHECKS_VERSION (L45, L114, L189) ---------------------------------------


_BASE = {
    "grounding.py": "g",
    "schemas.py": "s",
    "evals/runner.py": "r",
    "clinical/extract.py": "e",
}


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_checks_version_is_computed_over_backend() -> None:
    assert CHECKS_VERSION == checks_version(Path(__file__).resolve().parents[1] / "backend")


def test_checks_version_is_twelve_hex_digits_with_or_without_clinical(tmp_path: Path) -> None:
    without = {rel: text for rel, text in _BASE.items() if not rel.startswith("clinical/")}
    for name, files in (("with", _BASE), ("without", without)):
        version = checks_version(_tree(tmp_path / name, files))
        assert len(version) == 12 and set(version) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    "rel",
    ["grounding.py", "schemas.py", "evals/runner.py", "clinical/extract.py", "evals/cases/new.py"],
)
def test_checks_version_moves_with_hashed_source(tmp_path: Path, rel: str) -> None:
    before = checks_version(_tree(tmp_path / "before", _BASE))
    after = checks_version(_tree(tmp_path / "after", {**_BASE, rel: "edited"}))
    assert before != after


@pytest.mark.parametrize(
    "rel",
    [
        "evals/cases/case-1.yaml",  # corpus_version's
        "evals/runs/corpus_runs.jsonl",  # appended by every corpus run
        "evals/__pycache__/runner.cpython-314.pyc",
        "api.py",
    ],
)
def test_checks_version_ignores_everything_else(tmp_path: Path, rel: str) -> None:
    before = checks_version(_tree(tmp_path / "before", _BASE))
    assert checks_version(_tree(tmp_path / "after", {**_BASE, rel: "x"})) == before


def test_checks_version_moves_when_a_file_moves(tmp_path: Path) -> None:
    # same name, same bytes, another directory: the relative path is what differs
    one = checks_version(_tree(tmp_path / "one", {**_BASE, "evals/one/check.py": "same"}))
    two = checks_version(_tree(tmp_path / "two", {**_BASE, "evals/two/check.py": "same"}))
    assert one != two


# --- case_verdict (L43, L44) --------------------------------------------------


def _detection(*expected: str) -> EvalCase:
    return EvalCase(
        id="trap-1",
        species="detection",
        raw_text=RAW,
        trap="planted",
        expected_flags=list(expected),
    )


def _fidelity() -> EvalCase:
    return EvalCase(id="fidelity-1", species="fidelity", raw_text=RAW, trap="dropped")


def _fired(check: str, severity: Severity) -> EvalResult:
    return EvalResult(check=check, severity=severity, passed=False, detail="detail-1")


def _clean_result(check: str, severity: Severity) -> EvalResult:
    return EvalResult(check=check, severity=severity, passed=True)


def _report(results: list[EvalResult], ran: set[str] | None = None) -> EvalReport:
    """checks_run defaults to the checks the results name, as run_checks reports it."""
    checks_run = frozenset(ran if ran is not None else {r.check for r in results})
    return EvalReport(results=results, checks_run=checks_run, checks_version="version-1")


# §8.7's verdict table, row by row, then the edges its prose states
@pytest.mark.parametrize(
    ("case", "report", "status"),
    [
        (_detection("contra"), _report([_fired("contra", _C)]), "passed"),
        (_detection("contra"), _report([_clean_result("contra", _C)]), "failed"),
        (_detection("contra"), _report([_errored("contra", _C)]), "failed"),
        (_detection("judge"), _report([_fired("other", _C)], ran={"other"}), "not_applicable"),
        (_fidelity(), _report([_clean_result("allergy", _C)]), "passed"),
        (_fidelity(), _report([_fired("allergy", _C)]), "failed"),
        (_case(), _report([_fired("dose", _W)]), "passed"),
        (_case(), _report([_fired("drug", _C)]), "failed"),
        (_detection("judge"), _report([_errored("judge", _W)]), "failed"),
        (_case(), _report([_errored("drug", _C)]), "failed"),
        (_case(), _report([_errored("judge", _W)]), "passed"),
        (_detection("contra"), _report([_fired("contra", _W)]), "passed"),
        (
            _detection("contra", "drug"),
            _report([_fired("contra", _C), _clean_result("drug", _C)]),
            "failed",
        ),
        (_detection("contra"), _report([_fired("contra", _C), _fired("drug", _C)]), "failed"),
    ],
    ids=[
        "detection-fired",  # the v1.1 inversion: a fired expected flag is a pass
        "detection-silent",
        "detection-errored",  # L43: v1.2 scored this green
        "detection-not-selected",  # L44
        "fidelity-silent",
        "fidelity-fired",
        "control-fired-warning",  # the verdict is CRITICAL-scoped
        "control-fired-critical",  # a false positive
        "detection-errored-warning",  # L43: an error never satisfies an expectation
        "control-errored-critical",  # L43: a crashed CRITICAL never passes a case
        "control-errored-warning",  # a judge outage doesn't fail a case
        "detection-fired-downgraded",  # an expected check fires at any severity
        "detection-one-of-two",
        "detection-plus-unexpected-critical",
    ],
)
def test_case_verdict(case: EvalCase, report: EvalReport, status: CaseStatus) -> None:
    assert case_verdict(report, case) == status


@pytest.mark.parametrize(
    "case", [_case(), _fidelity(), _detection("contra")], ids=lambda c: c.species
)
def test_a_report_that_ran_no_check_scores_no_case(case: EvalCase) -> None:
    # L117: a control or fidelity case would otherwise pass on nothing (invariant 12)
    assert case_verdict(_report([], ran=set()), case) == "not_applicable"


def test_not_applicable_comes_before_any_failure() -> None:
    # L44: an expected check that didn't run excludes the case, whatever else happened
    report = _report([_fired("drug", _C), _errored("dose", _C)], ran={"drug", "dose"})
    assert case_verdict(report, _detection("judge")) == "not_applicable"


# --- a corpus run's rows (L224, L228) --------------------------------------------

DRAFT = SOAPNoteDraft.model_validate(
    {"claims": [{"text": "claim 0", "section": "S", "source_quote": "quote 0"}]}
)
USAGE = TokenUsage(input_tokens=11, output_tokens=7)


def _summarized() -> SummarizationResult:
    metadata = RunMetadata(
        model="model-id-1", prompt_version="prompt-hash-1", usage=USAGE, validation_attempts=2
    )
    return SummarizationResult(draft=DRAFT, metadata=metadata)


def test_case_result_keeps_the_verdict_the_cost_the_draft_and_the_wall_time() -> None:
    case = _detection("contra", "drug", "audit")
    results = [
        _fired("contra", _C),
        _clean_result("drug", _C),
        _clean_result("audit", _W),
        _fired("quote", _W),
        _fired("note", _W),
        _errored("judge", _W),
        _errored("crash", _W),
    ]
    report = _report(results)
    row = case_result(case, 2, report, _summarized(), summarize_wall_s=3.25)
    assert (row.case_id, row.repeat, row.species) == ("trap-1", 2, "detection")
    assert row.status == case_verdict(report, case) == "failed"
    assert row.fired_checks == ["contra", "note", "quote"]
    assert row.fired_critical == ["contra"]
    assert row.missing_expected == ["audit", "drug"]
    assert row.unexpected_fired == ["note", "quote"]
    assert row.errored_checks == ["crash", "judge"]
    assert (row.usage, row.validation_attempts) == (USAGE, 2)
    assert (row.draft, row.summarize_wall_s, row.error) == (DRAFT, 3.25, None)


@pytest.mark.parametrize(
    ("report", "status"),
    [
        (_report([_fired("contra", _C)]), "passed"),
        (_report([_clean_result("contra", _C)]), "failed"),
        (_report([], ran=set()), "not_applicable"),
    ],
    ids=["passed", "failed", "not-applicable"],
)
def test_case_result_takes_its_status_from_case_verdict(
    report: EvalReport, status: CaseStatus
) -> None:
    case = _detection("contra")
    assert case_result(case, 0, report, _summarized(), summarize_wall_s=1.0).status == status


def test_a_lowered_finding_fires_but_not_at_critical() -> None:
    # L224: diagnosis_in_quote's downgrade is a CRITICAL check's WARNING finding
    report = _report([_fired("diagnosis", _W)])
    row = case_result(_fidelity(), 0, report, _summarized(), summarize_wall_s=1.0)
    assert (row.fired_checks, row.fired_critical) == (["diagnosis"], [])


@pytest.mark.parametrize(
    ("usage", "attempts", "draft"),
    [(None, None, None), (USAGE, 3, None), (USAGE, 2, DRAFT)],
    ids=["crash-in-summarize", "orchestrator-error", "crash-after-summarize"],
)
def test_errored_case_is_failed_with_its_code_and_every_expected_flag_missing(
    usage: TokenUsage | None, attempts: int | None, draft: SOAPNoteDraft | None
) -> None:
    case = _detection("drug", "contra")
    row = errored_case(
        case,
        1,
        "code-1",
        usage=usage,
        validation_attempts=attempts,
        draft=draft,
        summarize_wall_s=0.5,
    )
    assert (row.case_id, row.repeat, row.species) == ("trap-1", 1, "detection")
    assert (row.status, row.error) == ("failed", "code-1")
    assert row.missing_expected == ["contra", "drug"]
    assert row.fired_checks == row.fired_critical == row.unexpected_fired == []
    assert row.errored_checks == []
    assert (row.usage, row.validation_attempts, row.draft) == (usage, attempts, draft)
    assert row.summarize_wall_s == 0.5


# --- a corpus run's metrics (L3, L205, L206, L224, L229, L230) ---------------------


def _row(
    case_id: str,
    species: Species,
    status: CaseStatus,
    *,
    repeat: int = 0,
    fired_critical: tuple[str, ...] = (),
    error: str | None = None,
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        repeat=repeat,
        species=species,
        status=status,
        fired_checks=list(fired_critical),
        fired_critical=list(fired_critical),
        missing_expected=[],
        unexpected_fired=[],
        usage=USAGE,
        validation_attempts=1,
        summarize_wall_s=1.0,
        draft=DRAFT,
        error=error,
    )


def test_each_rate_is_passed_over_applicable_repeats_by_species() -> None:
    rows = [
        _row("d-1", "detection", "passed"),
        _row("d-2", "detection", "passed"),
        _row("d-3", "detection", "failed"),
        _row("d-4", "detection", "not_applicable"),
        _row("c-1", "control", "passed"),
        _row("c-2", "control", "failed", error="APIError"),  # L205: a failure, applicable
        _row("f-1", "fidelity", "passed"),
        _row("f-2", "fidelity", "failed"),
        _row("f-3", "fidelity", "failed"),
        _row("f-4", "fidelity", "failed"),
    ]
    metrics = corpus_metrics(rows)
    assert metrics.detection_recall == pytest.approx(2 / 3)
    assert metrics.control_specificity == pytest.approx(1 / 2)
    assert metrics.model_fidelity == pytest.approx(1 / 4)
    assert metrics.pass_rate == pytest.approx(4 / 9)


def test_every_rate_is_none_when_no_repeat_is_applicable() -> None:
    # L205: a vacuous rate is not a perfect one
    rows = [_row(f"{s}-1", s, "not_applicable") for s in ("detection", "control", "fidelity")]
    metrics = corpus_metrics(rows)
    rates = (
        metrics.detection_recall,
        metrics.control_specificity,
        metrics.model_fidelity,
        metrics.fidelity_caught,
        metrics.pass_rate,
    )
    assert rates == (None, None, None, None, None)
    assert metrics.flaky_cases == []


@pytest.fixture
def live_and_reference(registry: dict[str, Check]) -> dict[str, Check]:
    register_check(name="live", severity=_C)(_clean)
    register_check(name="reference", severity=_C, requires_reference=True)(_clean)
    return registry


@pytest.mark.usefixtures("live_and_reference")
def test_fidelity_caught_counts_a_live_critical_among_failures_without_an_error() -> None:
    rows = [
        _row("f-1", "fidelity", "failed", fired_critical=("live",)),
        _row("f-2", "fidelity", "failed", fired_critical=("reference",)),
        _row("f-3", "fidelity", "failed", fired_critical=("live", "reference")),
        _row("f-4", "fidelity", "failed", error="APIError"),  # not in the denominator
        _row("f-5", "fidelity", "passed"),  # nor is a pass
        _row("c-1", "control", "failed", fired_critical=("live",)),  # nor another species
    ]
    assert corpus_metrics(rows).fidelity_caught == pytest.approx(2 / 3)


@pytest.mark.usefixtures("live_and_reference")
@pytest.mark.parametrize(
    "live",
    [_errored("live", _C), _fired("live", _W)],
    ids=["errored", "lowered"],
)
def test_an_errored_or_lowered_live_check_is_not_a_catch(live: EvalResult) -> None:
    # L224: production showed a lowered finding as a WARNING; L230: a crash is not a catch
    report = _report([_fired("reference", _C), live])
    row = case_result(_fidelity(), 0, report, _summarized(), summarize_wall_s=1.0)
    assert row.status == "failed"
    assert corpus_metrics([row]).fidelity_caught == 0.0


def test_a_case_is_flaky_when_its_applicable_repeats_disagree() -> None:
    # D11, L229: by case, over its applicable repeats, sorted by id
    outcomes: dict[str, list[CaseStatus]] = {
        "case-z": ["passed", "failed"],
        "case-b": ["passed", "passed"],
        "case-c": ["failed", "failed"],
        "case-d": ["passed", "not_applicable"],
        "case-e": ["not_applicable", "not_applicable"],
        "case-a": ["failed", "failed", "passed"],
    }
    rows = [
        _row(case_id, "control", status, repeat=repeat)
        for case_id, statuses in outcomes.items()
        for repeat, status in enumerate(statuses)
    ]
    assert corpus_metrics(rows).flaky_cases == ["case-a", "case-z"]
