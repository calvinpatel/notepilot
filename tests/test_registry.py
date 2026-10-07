"""Pins the check registry and stamp (spec §8.7; L38, L42, L111)."""

import inspect
from dataclasses import FrozenInstanceError

import pytest

from backend.evals.judge import Judge
from backend.evals.registry import Check, Finding, register_check, stamp
from backend.schemas import EvalCase, EvalResult, Severity, SOAPNote

_C, _W, _I = Severity.CRITICAL, Severity.WARNING, Severity.INFO


def _clean(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
    return []


def _other(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
    return []


def _judged(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, judge: Judge
) -> list[Finding]:
    return []


def _check(severity: Severity) -> Check:
    return Check(
        name="check-1",
        severity=severity,
        fn=_clean,
        requires_reference=False,
        needs_judge=False,
        origin="model",
    )


# --- register_check -----------------------------------------------------------


def test_register_check_records_the_check_and_returns_the_function(
    registry: dict[str, Check],
) -> None:
    fn = register_check(name="check-1", severity=_C)(_clean)
    assert fn is _clean
    assert registry == {"check-1": _check(_C)}


def test_register_check_records_each_option_on_its_own_field(
    registry: dict[str, Check],
) -> None:
    register_check(name="reference", severity=_W, requires_reference=True)(_clean)
    register_check(name="judged", severity=_W, needs_judge=True)(_judged)
    register_check(name="source", severity=_W, origin="source")(_clean)
    options = {n: (c.requires_reference, c.needs_judge, c.origin) for n, c in registry.items()}
    assert options == {
        "reference": (True, False, "model"),
        "judged": (False, True, "model"),
        "source": (False, False, "source"),
    }


def test_register_check_rejects_a_duplicate_name_and_keeps_the_first(
    registry: dict[str, Check],
) -> None:
    register_check(name="check-1", severity=_C)(_clean)
    with pytest.raises(RuntimeError, match="^duplicate check name: check-1$"):
        register_check(name="check-1", severity=_W)(_other)
    assert registry == {"check-1": _check(_C)}


def test_register_check_types_a_checks_signature(registry: dict[str, Check]) -> None:
    # The bound is (note, raw_text, case) -> list[Finding], or an awaitable of one. mypy
    # holds this half: strict mode fails on an ignore it doesn't need, so the gates break
    # if the bound stops rejecting the swapped signature or starts rejecting the others.
    @register_check(name="sync", severity=_W)
    def sync_check(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
        return []

    @register_check(name="async", severity=_W)
    async def async_check(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None
    ) -> list[Finding]:
        return []

    @register_check(name="swapped", severity=_W)  # type: ignore[type-var]
    def swapped_check(raw_text: str, note: SOAPNote, case: EvalCase | None = None) -> list[Finding]:
        return []

    # nothing checks a signature at runtime: all three register
    assert set(registry) == {"sync", "async", "swapped"}
    assert inspect.iscoroutinefunction(registry["async"].fn)


def test_register_check_ties_needs_judge_to_the_signature(registry: dict[str, Check]) -> None:
    # needs_judge=True takes a check with a required keyword judge, and the default takes one
    # without. Each ignore below is mypy's assertion, as in the test above.
    @register_check(name="judged", severity=_W, needs_judge=True)
    async def judged_check(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, judge: Judge
    ) -> list[Finding]:
        return []

    @register_check(name="flag-only", severity=_W, needs_judge=True)  # type: ignore[type-var]
    def flag_only(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
        return []

    @register_check(name="judge-only", severity=_W)  # type: ignore[type-var]
    async def judge_only(
        note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, judge: Judge
    ) -> list[Finding]:
        return []

    # at runtime the flag is recorded as given, whatever the signature
    needs_judge = {n: c.needs_judge for n, c in registry.items()}
    assert needs_judge == {"judged": True, "flag-only": True, "judge-only": False}


def test_a_finding_rejects_attribute_assignment() -> None:
    finding = Finding(detail="detail-1")
    with pytest.raises(FrozenInstanceError):
        finding.severity = _C  # type: ignore[misc]


def test_a_check_rejects_attribute_assignment() -> None:
    check = _check(_W)
    with pytest.raises(FrozenInstanceError):
        check.severity = _C  # type: ignore[misc]


# --- stamp (L38) --------------------------------------------------------------


def test_stamp_builds_a_failed_result_from_the_finding() -> None:
    result = stamp(_check(_C), Finding(detail="detail-1", claim_ids=(2, 0)))
    assert result == EvalResult(
        check="check-1",
        severity=_C,
        passed=False,
        errored=False,
        detail="detail-1",
        claim_ids=(2, 0),
    )


def test_a_bare_finding_stamps_a_note_level_result_at_the_checks_severity() -> None:
    # claim_ids=() is note-level (§9.7). On a WARNING check a wrong severity default shows
    # either way: CRITICAL raises, INFO stamps lower.
    result = stamp(_check(_W), Finding(detail="detail-1"))
    assert result == EvalResult(check="check-1", severity=_W, passed=False, detail="detail-1")


@pytest.mark.parametrize(
    ("check_severity", "finding_severity", "stamped"),
    [
        (_C, None, _C),
        (_W, None, _W),
        (_I, None, _I),
        (_C, _C, _C),
        (_C, _W, _W),
        (_C, _I, _I),
        (_W, _W, _W),
        (_W, _I, _I),
        (_I, _I, _I),
    ],
    ids=[
        "critical-none",
        "warning-none",
        "info-none",
        "critical-critical",
        "critical-warning",
        "critical-info",
        "warning-warning",
        "warning-info",
        "info-info",
    ],
)
def test_stamp_keeps_the_checks_severity_or_lowers_it(
    check_severity: Severity, finding_severity: Severity | None, stamped: Severity
) -> None:
    result = stamp(_check(check_severity), Finding(detail="detail-1", severity=finding_severity))
    assert result.severity is stamped


@pytest.mark.parametrize(
    ("check_severity", "finding_severity"),
    [(_W, _C), (_I, _W), (_I, _C)],
    ids=["warning-critical", "info-warning", "info-critical"],
)
def test_stamp_rejects_a_finding_above_its_checks_severity(
    check_severity: Severity, finding_severity: Severity
) -> None:
    # L38: a downgrade is the finding's to make; an upgrade is a bug in the check
    with pytest.raises(ValueError, match="^check-1: finding severity exceeds the check's$"):
        stamp(_check(check_severity), Finding(detail="detail-1", severity=finding_severity))
