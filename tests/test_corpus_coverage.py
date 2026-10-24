"""§8.5's coverage rule (L42, L137, L138, L146, L152, L222) and the model corpus's shape.

The model corpus holds its size, a model twin its injected case's raw text, each model
allergy trap both halves of its danger, and each fidelity trap a fact whose loss is CRITICAL
(L244, L245, L247, L248). No model case expects a judged check (L323).

load_cases already holds two of §11's corpus checks: every case parses, and every
expected_flags entry names a registered check.
"""

from collections.abc import Callable

import pytest

from backend.clinical.extract import (
    NO_ALLERGY_STATEMENTS,
    extract_allergies,
    extract_diagnoses,
    extract_excluded_diagnoses,
    extract_findings,
    extract_laterality,
    new_prescriptions,
)
from backend.clinical.lexicons import SITE_WORDS
from backend.evals.checks import drug_mentions, named_drugs, span_text
from backend.evals.loader import CASES_DIR, load_cases
from backend.evals.registry import REGISTRY
from backend.grounding import ground
from backend.schemas import EvalCase, Severity, SOAPNote
from tests.fakes import CHECKS_CONFIG

CASES = load_cases(CASES_DIR)
INJECTED = [case for case in CASES if case.draft is not None]
MODEL = [case for case in CASES if case.draft is None]
CRITICAL = sorted(name for name, c in REGISTRY.items() if c.severity is Severity.CRITICAL)
SOURCE = [name for name in CRITICAL if REGISTRY[name].origin == "source"]


def _note(case: EvalCase) -> SOAPNote:
    assert case.draft is not None
    return ground(case.draft, case.raw_text, config=CHECKS_CONFIG)


def _shares_a_drug(case: EvalCase, note: SOAPNote) -> bool:
    for claim in note.claims:
        span = span_text(claim, case.raw_text)
        if span is not None and named_drugs(claim.text) & named_drugs(span):
            return True
    return False


def _diagnoses(text: str) -> set[str]:
    return extract_diagnoses(text).keys() | extract_excluded_diagnoses(text)


def _shares_a_diagnosis(case: EvalCase, note: SOAPNote) -> bool:
    for claim in note.claims:
        span = span_text(claim, case.raw_text)
        if span is not None and _diagnoses(claim.text) & _diagnoses(span):
            return True
    return False


def _shares_a_finding(case: EvalCase, note: SOAPNote) -> bool:
    for claim in note.claims:
        span = span_text(claim, case.raw_text)
        if span is not None and extract_findings(claim.text).keys() & extract_findings(span).keys():
            return True
    return False


def _shares_a_site(case: EvalCase, note: SOAPNote) -> bool:
    for claim in note.claims:
        span = span_text(claim, case.raw_text)
        if span is None:
            continue
        for width in SITE_WORDS:
            if (
                extract_laterality(claim.text, width).keys()
                & extract_laterality(span, width).keys()
            ):
                return True
    return False


def _names_a_drug(case: EvalCase, note: SOAPNote) -> bool:
    return any(named_drugs(claim.text) for claim in note.claims)


def _keeps_an_allergy(case: EvalCase, note: SOAPNote) -> bool:
    raw = extract_allergies(case.raw_text)
    return any(extract_allergies(claim.text) & raw for claim in note.claims)


def _pairs_an_allergy_with_a_drug(case: EvalCase, note: SOAPNote) -> bool:
    texts = [case.raw_text, *(claim.text for claim in note.claims)]
    allergens = {a for text in texts for a in extract_allergies(text)} - NO_ALLERGY_STATEMENTS
    drugs = {drug for drug, _ in drug_mentions(note)} | new_prescriptions(case.raw_text)
    return bool(allergens and drugs)


def _carries_a_preserve_label(case: EvalCase, note: SOAPNote) -> bool:
    return bool(case.must_preserve)


def _carries_a_not_add_label(case: EvalCase, note: SOAPNote) -> bool:
    return bool(case.must_not_add)


# A control exercises a check when the check has something to compare on it (L138, L146,
# L152, L222): for the claim-local family, a key its extractor finds in both a claim's text and
# that claim's span, a site at any SITE_WORDS width for laterality_consistency; for
# hallucinated_medication, a claim naming a drug, which grounding's flag
# then decides; for allergy_preserved, an allergy the raw text and a claim both state; for
# allergy_contraindication, an allergy and a drug for the ladder to pair; for must_preserve
# and must_not_add, a label of their list, since each compares its labels with the note.
EXERCISES: dict[str, Callable[[EvalCase, SOAPNote], bool]] = {
    "allergy_contraindication": _pairs_an_allergy_with_a_drug,
    "allergy_preserved": _keeps_an_allergy,
    "diagnosis_in_quote": _shares_a_diagnosis,
    "drug_in_quote": _shares_a_drug,
    "hallucinated_medication": _names_a_drug,
    "laterality_consistency": _shares_a_site,
    "med_status_consistency": _shares_a_drug,
    "must_not_add": _carries_a_not_add_label,
    "must_preserve": _carries_a_preserve_label,
    "negation_consistency": _shares_a_finding,
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
    assert [c.id for c in controls if exercises(c, _note(c))]


def test_a_source_check_is_registered() -> None:
    # the model clause over no checks holds of nothing
    assert SOURCE


@pytest.mark.parametrize("name", SOURCE)
def test_each_source_check_has_a_model_detection_trap(name: str) -> None:
    # §8.5's model clause (L137): does a real model keep the danger visible?
    assert [c.id for c in MODEL if c.species == "detection" and name in c.expected_flags]


@pytest.mark.parametrize("species", ["detection", "fidelity", "control"])
def test_the_model_corpus_holds_at_least_six_of_each_species(species: str) -> None:
    # §8.5's size, with ≥ 24 in all below (L248)
    assert len([c for c in MODEL if c.species == species]) >= 6


def test_the_model_corpus_holds_at_least_twenty_four_cases() -> None:
    assert len(MODEL) >= 24


def test_no_model_case_expects_a_judged_check() -> None:
    # L323: a run without the judge, and every replay, would read the expectation as
    # not_applicable (L44), so a model case's verdict never waits on the judge
    judged = {name for name, check in REGISTRY.items() if check.needs_judge}
    assert judged, "no judged check is registered"
    assert [c.id for c in MODEL if judged & set(c.expected_flags)] == []


TWINS = [c for c in MODEL if c.id.endswith("_model")]
ALLERGY_TRAPS = [c for c in MODEL if "allergy_contraindication" in c.expected_flags]
FIDELITY = [c for c in MODEL if c.species == "fidelity"]


@pytest.mark.parametrize("twin", TWINS, ids=[c.id for c in TWINS])
def test_a_model_twin_keeps_its_injected_case_s_raw_text(twin: EvalCase) -> None:
    # L247: an id is its file name, so a model twin takes its injected case's id plus _model
    base = twin.id.removesuffix("_model")
    assert [c.raw_text for c in INJECTED if c.id == base] == [twin.raw_text]


def _labels(case: EvalCase, kind: str) -> list[str]:
    return [item.text for item in case.must_preserve if item.kind == kind]


@pytest.mark.parametrize("case", ALLERGY_TRAPS, ids=[c.id for c in ALLERGY_TRAPS])
def test_a_model_allergy_trap_labels_both_halves_of_its_danger(case: EvalCase) -> None:
    # L244: the check reads the source, so it fires on any note; the labels make a note that
    # hides the allergy or the order fail the trap
    assert _labels(case, "allergy") and _labels(case, "medication")


@pytest.mark.parametrize("case", FIDELITY, ids=[c.id for c in FIDELITY])
def test_a_fidelity_trap_keeps_a_fact_whose_loss_is_critical(case: EvalCase) -> None:
    # L245: a trap passes when nothing CRITICAL fires, so a trap whose labels can only lose at
    # WARNING (a dose, NKDA, or NKA, L217) can never fail
    allergies = [
        t for t in _labels(case, "allergy") if extract_allergies(t) - NO_ALLERGY_STATEMENTS
    ]
    kept = allergies + [
        i.text for i in case.must_preserve if i.kind in ("medication", "finding", "diagnosis")
    ]
    assert kept
