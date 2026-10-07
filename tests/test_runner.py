"""Pins the check engine, the per-case verdict, and the checks' lineage (spec §8.7; L38,
L43–L45, L49, L113–L115).
"""

import asyncio
import logging
from pathlib import Path
from typing import Literal

import pytest

from backend.evals.judge import Judge
from backend.evals.registry import Check, Finding, register_check
from backend.evals.runner import CHECKS_VERSION, case_verdict, checks_version, run_checks
from backend.schemas import (
    CaseStatus,
    ClinicalClaim,
    EvalCase,
    EvalReport,
    EvalResult,
    Severity,
    SOAPNote,
    TokenUsage,
)
from tests.fakes import FakeJudge

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


def _clean(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
    return []


def _judged_clean(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, judge: Judge
) -> list[Finding]:
    return []


class _Crash(Exception):
    """A local type: a hard-coded exc_type literal can't match a builtin's name."""


def _crashing(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
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
    report = await run_checks(_note(), RAW, mode=mode, judge=FakeJudge() if with_judge else None)
    assert report.checks_run == selected  # L44: what ran, so "didn't run" isn't "didn't fire"
    assert {r.check for r in report.results} == selected


@pytest.mark.anyio
async def test_run_checks_passes_each_check_its_arguments(registry: dict[str, Check]) -> None:
    seen: dict[str, tuple[object, ...]] = {}

    @register_check(name="plain", severity=_W)
    def plain(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
        seen["plain"] = (note, raw_text, case)
        return []

    @register_check(name="judged", severity=_W, needs_judge=True)
    async def judged(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, judge: Judge
    ) -> list[Finding]:
        seen["judged"] = (note, raw_text, case, judge)
        return []

    note, case, judge = _note(1), _case(), FakeJudge()
    await run_checks(note, RAW, case, mode="ci", judge=judge)
    assert [a is b for a, b in zip(seen["plain"], (note, RAW, case), strict=True)] == [True] * 3
    expected = (note, RAW, case, judge)
    assert [a is b for a, b in zip(seen["judged"], expected, strict=True)] == [True] * 4


@pytest.mark.anyio
async def test_run_checks_turns_findings_into_results_and_a_clean_check_into_a_pass(
    registry: dict[str, Check],
) -> None:
    register_check(name="clean", severity=_C)(_clean)

    @register_check(name="findings", severity=_C)
    async def findings(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None
    ) -> list[Finding]:
        return [Finding(detail="detail-1", claim_ids=(2,)), Finding(detail="detail-2", severity=_W)]

    report = await run_checks(_note(1, 2), RAW, mode="production")
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
    judged = await run_checks(_note(), RAW, mode="production", judge=FakeJudge(usage=usage))
    unjudged = await run_checks(_note(), RAW, mode="production")
    assert (judged.judge_usage, unjudged.judge_usage) == (usage, TokenUsage())  # L7
    assert judged.checks_version == CHECKS_VERSION  # L45


# --- fail-closed (invariant 12) -----------------------------------------------


@pytest.mark.anyio
async def test_a_check_that_raises_becomes_one_errored_result_and_the_rest_run(
    registry: dict[str, Check],
) -> None:
    register_check(name="crash", severity=_C)(_crashing)
    register_check(name="after", severity=_W)(_clean)
    report = await run_checks(_note(), RAW, mode="production")
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
    await run_checks(_note(), RAW, mode="production")
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
    def upgrade(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
        return [Finding(detail="detail-1", severity=_C)]

    report = await run_checks(_note(), RAW, mode="production")
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
    def stray(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
        return [Finding(detail="detail-1", claim_ids=claim_ids)]

    report = await run_checks(_note(1, 2), RAW, mode="production")
    assert report.results == [_errored("stray", _C)]


@pytest.mark.anyio
async def test_cancellation_passes_through(registry: dict[str, Check]) -> None:
    # CancelledError is a BaseException: the per-check except must not absorb it
    @register_check(name="cancelled", severity=_C)
    async def cancelled(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None
    ) -> list[Finding]:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await run_checks(_note(), RAW, mode="production")


# --- CHECKS_VERSION (L45, L114) ---------------------------------------------


_BASE = {"grounding.py": "g", "evals/runner.py": "r", "clinical/extract.py": "e"}


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
    "rel", ["grounding.py", "evals/runner.py", "clinical/extract.py", "evals/cases/new.py"]
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
