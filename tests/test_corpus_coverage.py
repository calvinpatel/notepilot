"""§8.5's coverage rule, over the injected corpus (L42, L137, L138).

load_cases already holds two of §11's corpus checks: every case parses, and every
expected_flags entry names a registered check.
"""

from collections.abc import Callable

import pytest

from backend.evals.checks import named_drugs, span_text
from backend.evals.loader import CASES_DIR, load_cases
from backend.evals.registry import REGISTRY
from backend.grounding import ground
from backend.schemas import EvalCase, Severity, SOAPNote

CASES = load_cases(CASES_DIR)
INJECTED = [case for case in CASES if case.draft is not None]
CRITICAL = sorted(name for name, c in REGISTRY.items() if c.severity is Severity.CRITICAL)


def _note(case: EvalCase) -> SOAPNote:
    assert case.draft is not None
    return ground(case.draft, case.raw_text)


def _shares_a_drug(note: SOAPNote, raw_text: str) -> bool:
    for claim in note.claims:
        span = span_text(claim, raw_text)
        if span is not None and named_drugs(claim.text) & named_drugs(span):
            return True
    return False


def _names_a_drug(note: SOAPNote, raw_text: str) -> bool:
    return any(named_drugs(claim.text) for claim in note.claims)


# A control exercises a check when the check has something to compare on it (L138): for the
# claim-local family, a key its extractor finds in both a claim's text and that claim's span;
# for hallucinated_medication, a claim naming a drug, which grounding's flag then decides.
EXERCISES: dict[str, Callable[[SOAPNote, str], bool]] = {
    "drug_in_quote": _shares_a_drug,
    "hallucinated_medication": _names_a_drug,
    "med_status_consistency": _shares_a_drug,
}


def test_a_critical_check_is_registered() -> None:
    # a rule over no checks holds of nothing
    assert CRITICAL


def test_each_critical_check_has_an_exercise_predicate_and_no_other_name_does() -> None:
    assert sorted(EXERCISES) == CRITICAL


@pytest.mark.parametrize("name", CRITICAL)
def test_each_critical_check_has_an_injected_detection_trap(name: str) -> None:
    assert [c.id for c in INJECTED if c.species == "detection" and name in c.expected_flags]


@pytest.mark.parametrize("name", CRITICAL)
def test_each_critical_check_has_an_injected_control_that_exercises_it(name: str) -> None:
    exercises = EXERCISES[name]
    controls = [c for c in INJECTED if c.species == "control"]
    assert [c.id for c in controls if exercises(_note(c), c.raw_text)]


def test_the_corpus_holds_no_model_case_yet() -> None:
    # §8.5's model clause joins this file with the corpus's first model case (§14, L137)
    assert [case.id for case in CASES if case.draft is None] == []
