"""The omission law: a test per row of §8.4's omission table (D17, invariant 17)."""

import inspect
from collections.abc import Callable

import pytest

from backend.evals.checks import (
    check_allergy_contraindication,
    check_allergy_preserved,
    check_diagnosis_in_quote,
    check_drug_in_quote,
    check_hallucinated_medication,
    check_med_status_consistency,
    check_negation_consistency,
)
from backend.evals.registry import REGISTRY, Finding
from backend.schemas import ClinicalClaim, EvalCase, SafetyFlag, Severity, SOAPNote

type _CheckFn = Callable[[SOAPNote, str, EvalCase | None], list[Finding]]

# §8.4's row for the consistency family and hallucinated_medication: the model omits the claim
FAMILY: dict[str, _CheckFn] = {
    "diagnosis_in_quote": check_diagnosis_in_quote,
    "drug_in_quote": check_drug_in_quote,
    "hallucinated_medication": check_hallucinated_medication,
    "med_status_consistency": check_med_status_consistency,
    "negation_consistency": check_negation_consistency,
}

# every CRITICAL check a row below covers
COVERED = set(FAMILY) | {"allergy_contraindication", "allergy_preserved"}

CRITICAL = sorted(name for name, c in REGISTRY.items() if c.severity is Severity.CRITICAL)


@pytest.mark.parametrize("name", sorted(FAMILY))
def test_an_omitted_claim_leaves_the_family_nothing_to_contradict(name: str) -> None:
    # the source starts a drug for a diagnosis; the note's claims are a grounded follow-up
    # and an ungrounded line naming neither
    raw = "Pneumonia, will start amoxicillin 500 mg daily. Follow up in one week."
    follow_up = "Follow up in one week."
    start = raw.index(follow_up)
    grounded = ClinicalClaim(
        id=0,
        text="Follow up in one week",
        section="P",
        source_quote=follow_up,
        source_span=(start, start + len(follow_up)),
    )
    ungrounded = ClinicalClaim(
        id=1,
        text="Counseled on diet",
        section="P",
        source_quote="counseled on diet",
        flags=(SafetyFlag.UNSUPPORTED,),
    )
    assert FAMILY[name](SOAPNote(claims=(grounded, ungrounded)), raw, None) == []


def test_an_omitted_allergy_is_allergy_preserveds_subject() -> None:
    # §8.4's row for allergy_preserved: the model omits the allergy, and the check fires
    raw = "PCN allergy. Will start azithromycin 500 mg daily."
    start_order = "start azithromycin 500 mg daily"
    start = raw.index(start_order)
    claim = ClinicalClaim(
        id=0,
        text="Start azithromycin 500 mg daily",
        section="P",
        source_quote=start_order,
        source_span=(start, start + len(start_order)),
    )
    findings = check_allergy_preserved(SOAPNote(claims=(claim,)), raw, None)
    assert [f.detail for f in findings] == ["penicillin: in the source, not the note"]


def _claim(raw: str, quote: str, claim_id: int = 0) -> ClinicalClaim:
    """A claim quoting quote, grounded to its first place in raw."""
    start = raw.index(quote)
    return ClinicalClaim(
        id=claim_id,
        text=quote,
        section="P",
        source_quote=quote,
        source_span=(start, start + len(quote)),
    )


def test_an_omitted_allergy_still_reaches_the_contraindication() -> None:
    # §8.4's row for allergy_contraindication: the allergy is read from the raw text
    raw = "Allergic to amoxicillin. Start amoxicillin 500 mg tid."
    note = SOAPNote(claims=(_claim(raw, "Start amoxicillin 500 mg tid"),))
    assert [f.claim_ids for f in check_allergy_contraindication(note, raw, None)] == [(0,)]


def test_an_omitted_new_drug_still_reaches_the_contraindication_at_the_banner() -> None:
    # §8.4's row: the drug is read through new_prescriptions(raw_text) (L51)
    raw = "PCN allergy. Start amoxicillin 500 mg tid."
    note = SOAPNote(claims=(_claim(raw, "PCN allergy"),))
    assert [f.claim_ids for f in check_allergy_contraindication(note, raw, None)] == [()]


def test_an_omitted_continued_home_medication_is_a_ci_only_gap() -> None:
    # §8.4's row: no live check sees it; must_preserve(kind="medication") covers it in CI
    raw = "NSAID allergy. Continue ibuprofen 400 mg prn."
    note = SOAPNote(claims=(_claim(raw, "NSAID allergy"),))
    assert check_allergy_contraindication(note, raw, None) == []


def test_every_critical_check_has_an_omission_row() -> None:
    assert [name for name in CRITICAL if name not in COVERED] == []


@pytest.mark.parametrize("name", CRITICAL)
def test_every_critical_check_documents_its_omission_row(name: str) -> None:
    assert "Omission (D17):" in (inspect.getdoc(REGISTRY[name].fn) or "")
