"""The injected corpus: each case with a draft, scored free on every commit (§8.5, §11; L42)."""

import pytest

from backend.evals.loader import CASES_DIR, load_cases
from backend.evals.runner import case_verdict, run_checks
from backend.grounding import ground
from backend.schemas import EvalCase, SafetyFlag

INJECTED = [case for case in load_cases(CASES_DIR) if case.draft is not None]
CONTROLS = [case for case in INJECTED if case.species == "control"]

# built to ground at Tier 3, so a cutoff change can't quietly make one a Tier 4 case (§8.5)
FUZZY = ["detect_paraphrase_drug_swap"]


@pytest.mark.anyio
@pytest.mark.parametrize("case", INJECTED, ids=[case.id for case in INJECTED])
async def test_an_injected_case_passes(case: EvalCase) -> None:
    assert case.draft is not None  # INJECTED holds only drafted cases; this narrows the type
    note = ground(case.draft, case.raw_text)
    report = await run_checks(note, case.raw_text, case, mode="ci")
    assert case_verdict(report, case) == "passed", report.results


@pytest.mark.anyio
@pytest.mark.parametrize("case", CONTROLS, ids=[case.id for case in CONTROLS])
async def test_an_injected_control_fires_no_check(case: EvalCase) -> None:
    # L162: an authored draft is deterministic, so a WARNING on a control is a false positive
    # too; the verdict stays CRITICAL-scoped (§8.7)
    assert case.draft is not None
    note = ground(case.draft, case.raw_text)
    report = await run_checks(note, case.raw_text, case, mode="ci")
    assert [r.check for r in report.results if not r.passed] == []


@pytest.mark.parametrize("case_id", FUZZY)
def test_a_fuzzy_tier_case_grounds_paraphrased(case_id: str) -> None:
    (case,) = [c for c in INJECTED if c.id == case_id]
    assert case.draft is not None
    note = ground(case.draft, case.raw_text)
    assert [SafetyFlag.PARAPHRASED in c.flags for c in note.claims] == [True]
