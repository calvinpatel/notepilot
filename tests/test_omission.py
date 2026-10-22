"""The omission law: a test per row of §8.4's omission table (D17, invariant 17)."""

import inspect

import pytest

from backend.evals.checks import (
    check_allergy_contraindication,
    check_allergy_preserved,
    check_diagnosis_in_quote,
    check_drug_in_quote,
    check_hallucinated_medication,
    check_laterality_consistency,
    check_med_status_consistency,
    check_must_not_add,
    check_must_preserve,
    check_negation_consistency,
)
from backend.evals.registry import REGISTRY, CheckFn
from backend.schemas import ClinicalClaim, EvalCase, SafetyFlag, Severity, SOAPNote
from tests.fakes import CHECKS_CONFIG

# §8.4's row for the consistency family and hallucinated_medication: the model omits the claim
FAMILY: dict[str, CheckFn] = {
    "diagnosis_in_quote": check_diagnosis_in_quote,
    "drug_in_quote": check_drug_in_quote,
    "hallucinated_medication": check_hallucinated_medication,
    "laterality_consistency": check_laterality_consistency,
    "med_status_consistency": check_med_status_consistency,
    "negation_consistency": check_negation_consistency,
}

# every CRITICAL check a row below covers
COVERED = set(FAMILY) | {
    "allergy_contraindication",
    "allergy_preserved",
    "must_preserve",
    "must_not_add",
}

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
    assert (
        FAMILY[name](SOAPNote(claims=(grounded, ungrounded)), raw, None, config=CHECKS_CONFIG) == []
    )


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
    findings = check_allergy_preserved(SOAPNote(claims=(claim,)), raw, None, config=CHECKS_CONFIG)
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
    assert [
        f.claim_ids for f in check_allergy_contraindication(note, raw, None, config=CHECKS_CONFIG)
    ] == [(0,)]


def test_an_omitted_new_drug_still_reaches_the_contraindication_at_the_banner() -> None:
    # §8.4's row: the drug is read through new_prescriptions(raw_text) (L51)
    raw = "PCN allergy. Start amoxicillin 500 mg tid."
    note = SOAPNote(claims=(_claim(raw, "PCN allergy"),))
    assert [
        f.claim_ids for f in check_allergy_contraindication(note, raw, None, config=CHECKS_CONFIG)
    ] == [()]


def test_an_omitted_continued_home_medication_is_a_ci_only_gap() -> None:
    # §8.4's row: no live check sees it; must_preserve(kind="medication") covers it in CI
    raw = "NSAID allergy. Continue ibuprofen 400 mg prn."
    note = SOAPNote(claims=(_claim(raw, "NSAID allergy"),))
    assert check_allergy_contraindication(note, raw, None, config=CHECKS_CONFIG) == []


def test_an_omitted_side_is_a_ci_only_gap_a_laterality_label_covers() -> None:
    # §8.4's row: a claim that drops the side names none, so laterality_consistency passes,
    # and must_preserve(kind="laterality") covers it in CI (L286)
    raw = "Right knee pain after a fall, left knee normal."
    quote = "Right knee pain after a fall"
    start = raw.index(quote)
    dropped = ClinicalClaim(
        id=0,
        text="Knee pain after a fall",
        section="S",
        source_quote=quote,
        source_span=(start, start + len(quote)),
    )
    note = SOAPNote(claims=(dropped,))
    assert check_laterality_consistency(note, raw, None, config=CHECKS_CONFIG) == []
    case = EvalCase.model_validate(
        {
            "id": "drops_a_side",
            "species": "fidelity",
            "raw_text": raw,
            "trap": "omission",
            "must_preserve": [{"text": "right knee", "kind": "laterality"}],
        }
    )
    # the detail names the label's entity, the site, as every kind's names its own
    assert [f.detail for f in check_must_preserve(note, raw, case, config=CHECKS_CONFIG)] == [
        "knee (laterality): in the answer key, not kept by the note"
    ]


def test_an_omitted_labeled_fact_is_must_preserves_subject() -> None:
    # §8.4's row for must_preserve: the model omits a labeled fact, and the check fires (CI)
    raw = "PCN allergy. Continue metformin. Will start azithromycin 500 mg daily."
    case = EvalCase.model_validate(
        {
            "id": "omits",
            "species": "fidelity",
            "raw_text": raw,
            "trap": "omission",
            "must_preserve": [{"text": "metformin", "kind": "medication"}],
        }
    )
    note = SOAPNote(claims=(_claim(raw, "PCN allergy"),))
    findings = check_must_preserve(note, raw, case, config=CHECKS_CONFIG)
    assert [f.detail for f in findings] == [
        "metformin (medication): in the answer key, not kept by the note"
    ]


def test_an_omitted_claim_leaves_must_not_add_nothing_to_fire_on() -> None:
    # §8.4's row for must_not_add: the claim that would add the label is gone, and an omitted
    # invention is the faithful note (L223). The source negates apixaban, so the label loads
    # (L219), and the adding claim cites a span that cuts off the negation (L157).
    raw = "Not on apixaban. Diet and exercise only."
    case = EvalCase.model_validate(
        {
            "id": "omits",
            "species": "fidelity",
            "raw_text": raw,
            "trap": "omission",
            "must_not_add": [{"text": "apixaban", "kind": "medication"}],
        }
    )
    start = raw.index("apixaban")
    adding = ClinicalClaim(
        id=0,
        text="Taking apixaban",
        section="S",
        source_quote="apixaban",
        source_span=(start, start + len("apixaban")),
    )
    faithful = _claim(raw, "Diet and exercise only", claim_id=1)
    added = SOAPNote(claims=(adding, faithful))
    omitted = SOAPNote(claims=(faithful,))
    assert [f.claim_ids for f in check_must_not_add(added, raw, case, config=CHECKS_CONFIG)] == [
        (0,)
    ]
    assert check_must_not_add(omitted, raw, case, config=CHECKS_CONFIG) == []


def test_every_critical_check_has_an_omission_row() -> None:
    assert [name for name in CRITICAL if name not in COVERED] == []


@pytest.mark.parametrize("name", CRITICAL)
def test_every_critical_check_documents_its_omission_row(name: str) -> None:
    assert "Omission (D17):" in (inspect.getdoc(REGISTRY[name].fn) or "")
