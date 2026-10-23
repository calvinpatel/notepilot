"""The injected corpus: each case with a draft, scored free on every commit (§8.5, §11; L42).

Each case is scored with no judge, with a fake judge that entails its claims but those
JUDGE_REJECTS names, and with one that times out (§11). A rejection scripted into the fake
tests the plumbing, not the judge (§8.8).
"""

from typing import Literal, assert_never

import pytest

from backend.evals.loader import CASES_DIR, load_cases
from backend.evals.runner import case_verdict, run_checks
from backend.grounding import ground
from backend.schemas import EvalCase, EvalReport, SafetyFlag, Severity
from tests.fakes import CHECKS_CONFIG, FakeJudge, entail_all_but, time_out

INJECTED = [case for case in load_cases(CASES_DIR) if case.draft is not None]
CONTROLS = [case for case in INJECTED if case.species == "control"]

# built to ground at Tier 3, so a cutoff change can't quietly make one a Tier 4 case (§8.5)
FUZZY = ["detect_paraphrase_drug_swap"]

# the claims the entailing fake rejects, by case
JUDGE_REJECTS = {"detect_invented_assessment": ("Hypertensive urgency",)}

# no claim with a span, so the judge is never called on them (L310)
UNJUDGED = ["detect_empty_note", "detect_hallucinated_medication"]

type Judging = Literal["no-judge", "entailing", "timing-out"]


def _judge(case: EvalCase, judging: Judging) -> FakeJudge | None:
    if judging == "no-judge":
        return None
    if judging == "entailing":
        return FakeJudge(script=entail_all_but(*JUDGE_REJECTS.get(case.id, ())))
    if judging == "timing-out":
        return FakeJudge(script=time_out)
    assert_never(judging)


@pytest.mark.anyio
@pytest.mark.parametrize("judging", ["no-judge", "entailing", "timing-out"])
@pytest.mark.parametrize("case", INJECTED, ids=[case.id for case in INJECTED])
async def test_an_injected_case_passes(case: EvalCase, judging: Judging) -> None:
    assert case.draft is not None  # INJECTED holds only drafted cases; this narrows the type
    note = ground(case.draft, case.raw_text, config=CHECKS_CONFIG)
    report = await run_checks(
        note, case.raw_text, case, mode="ci", config=CHECKS_CONFIG, judge=_judge(case, judging)
    )
    assert case_verdict(report, case) == "passed", report.results
    # an errored WARNING fails no case (§8.7), so the verdict alone can't see a crashed judge.
    # A judge that times out errors its own check and no other (invariant 7), on every case
    # it's called on.
    errored = {r.check for r in report.results if r.errored}
    timed_out = judging == "timing-out" and case.id not in UNJUDGED
    assert errored == ({"text_entailment_judge"} if timed_out else set())


@pytest.mark.anyio
@pytest.mark.parametrize("judging", ["no-judge", "entailing"])
@pytest.mark.parametrize("case", CONTROLS, ids=[case.id for case in CONTROLS])
async def test_an_injected_control_fires_no_check(case: EvalCase, judging: Judging) -> None:
    # L162: an authored draft is deterministic, so a WARNING on a control is a false positive
    # too; the verdict stays CRITICAL-scoped (§8.7). A judge that times out is the verdict
    # test's: its errored check is unpassed, though it fired nothing.
    assert case.draft is not None
    note = ground(case.draft, case.raw_text, config=CHECKS_CONFIG)
    report = await run_checks(
        note, case.raw_text, case, mode="ci", config=CHECKS_CONFIG, judge=_judge(case, judging)
    )
    assert [r.check for r in report.results if not r.passed] == []


def _fired(report: EvalReport) -> list[tuple[str, Severity, tuple[int, ...]]]:
    """Each fired result's check, severity, and claims, in the report's order."""
    return [
        (r.check, r.severity, r.claim_ids) for r in report.results if not r.passed and not r.errored
    ]


@pytest.mark.anyio
async def test_the_judge_adds_its_warning_beside_the_invented_assessment() -> None:
    # §14's 2c line: diagnosis_in_quote fires with the judge off, and the judge adds its
    # WARNING with it on; the verdict passes both ways (invariant 7)
    (case,) = [c for c in INJECTED if c.id == "detect_invented_assessment"]
    assert case.draft is not None
    note = ground(case.draft, case.raw_text, config=CHECKS_CONFIG)
    judge = FakeJudge(script=entail_all_but(*JUDGE_REJECTS[case.id]))
    off = await run_checks(note, case.raw_text, case, mode="ci", config=CHECKS_CONFIG)
    on = await run_checks(note, case.raw_text, case, mode="ci", config=CHECKS_CONFIG, judge=judge)
    assert _fired(off) == [("diagnosis_in_quote", Severity.CRITICAL, (0,))]
    assert _fired(on) == [
        ("diagnosis_in_quote", Severity.CRITICAL, (0,)),
        ("text_entailment_judge", Severity.WARNING, (0,)),
    ]
    assert (case_verdict(off, case), case_verdict(on, case)) == ("passed", "passed")
    assert judge.calls == [[("Hypertensive urgency", "BP 190/110 on arrival")]]


@pytest.mark.parametrize("case_id", FUZZY)
def test_a_fuzzy_tier_case_grounds_paraphrased(case_id: str) -> None:
    (case,) = [c for c in INJECTED if c.id == case_id]
    assert case.draft is not None
    note = ground(case.draft, case.raw_text, config=CHECKS_CONFIG)
    assert [SafetyFlag.PARAPHRASED in c.flags for c in note.claims] == [True]


@pytest.mark.parametrize("case_id", UNJUDGED)
def test_an_unjudged_case_has_no_claim_with_a_span(case_id: str) -> None:
    (case,) = [c for c in INJECTED if c.id == case_id]
    assert case.draft is not None
    note = ground(case.draft, case.raw_text, config=CHECKS_CONFIG)
    assert [c.id for c in note.claims if c.source_span is not None] == []
