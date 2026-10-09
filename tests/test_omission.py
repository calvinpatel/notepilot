"""The omission law: a test per row of §8.4's omission table (D17, invariant 17)."""

import inspect
from collections.abc import Callable

import pytest

from backend.evals.checks import (
    check_drug_in_quote,
    check_hallucinated_medication,
    check_med_status_consistency,
)
from backend.evals.registry import REGISTRY, Finding
from backend.schemas import ClinicalClaim, EvalCase, SafetyFlag, Severity, SOAPNote

type _CheckFn = Callable[[SOAPNote, str, EvalCase | None], list[Finding]]

# §8.4's row for the consistency family and hallucinated_medication: the model omits the claim
FAMILY: dict[str, _CheckFn] = {
    "drug_in_quote": check_drug_in_quote,
    "hallucinated_medication": check_hallucinated_medication,
    "med_status_consistency": check_med_status_consistency,
}

# every CRITICAL check a row below covers
COVERED = set(FAMILY)

CRITICAL = sorted(name for name, c in REGISTRY.items() if c.severity is Severity.CRITICAL)


@pytest.mark.parametrize("name", sorted(FAMILY))
def test_an_omitted_claim_leaves_the_family_nothing_to_contradict(name: str) -> None:
    # the source starts a drug; the note's claims are a grounded follow-up and an ungrounded
    # line naming no drug
    raw = "Will start amoxicillin 500 mg daily. Follow up in one week."
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


def test_every_critical_check_has_an_omission_row() -> None:
    assert [name for name in CRITICAL if name not in COVERED] == []


@pytest.mark.parametrize("name", CRITICAL)
def test_every_critical_check_documents_its_omission_row(name: str) -> None:
    assert "Omission (D17):" in (inspect.getdoc(REGISTRY[name].fn) or "")
