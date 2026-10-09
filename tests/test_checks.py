"""Pins the reference-free roster and its helpers (spec §8.4; D6, D10, D12, D13, L35, L136-L144)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.clinical.lexicons import (
    ALLERGY_ALIASES,
    DIAGNOSES,
    DOSE_MASS_UG,
    DOSE_UNITS,
    FINDINGS,
    GENERIC_DRUGS,
)
from backend.evals.checks import (
    check_allergy_preserved,
    check_diagnosis_in_quote,
    check_dose_consistency,
    check_drug_in_quote,
    check_hallucinated_medication,
    check_med_status_consistency,
    check_negation_consistency,
    named_drugs,
    span_text,
)
from backend.evals.registry import REGISTRY, Finding
from backend.schemas import ClinicalClaim, SafetyFlag, Section, Severity, SOAPNote

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _note(*claims: tuple[str, str | None]) -> tuple[SOAPNote, str]:
    """A note of (text, span) claims, ids from 0, and a raw text holding every span.

    A claim whose span is None grounds nowhere, as Tier 4 leaves it (§6.3).
    """
    raw = " ".join(span for _, span in claims if span is not None)
    built: list[ClinicalClaim] = []
    for i, (text, span) in enumerate(claims):
        if span is None:
            built.append(
                ClinicalClaim(
                    id=i,
                    text=text,
                    section="P",
                    source_quote=text,
                    flags=(SafetyFlag.UNSUPPORTED,),
                )
            )
        else:
            start = raw.index(span)
            built.append(
                ClinicalClaim(
                    id=i,
                    text=text,
                    section="P",
                    source_quote=span,
                    source_span=(start, start + len(span)),
                )
            )
    return SOAPNote(claims=tuple(built)), raw


def _named(findings: list[Finding]) -> list[str]:
    """The drug each finding names, in order: a detail opens with its drug."""
    return [f.detail.partition(":")[0] for f in findings]


# --- span_text and named_drugs ------------------------------------------------------------


def test_span_text_is_the_claims_slice_of_the_raw_text() -> None:
    note, raw = _note(("Continue lisinopril", "continue lisinopril 10 mg daily"))
    assert span_text(note.claims[0], raw) == "continue lisinopril 10 mg daily"


def test_span_text_is_none_for_a_claim_that_grounds_nowhere() -> None:
    note, raw = _note(("Start amoxicillin", None))
    assert span_text(note.claims[0], raw) is None


@pytest.mark.parametrize(
    "text",
    [
        "continue apixaban",
        "discontinue apixaban",
        "apixaban held",
        "not on apixaban",
        "start Eliquis",
    ],
)
def test_named_drugs_reads_every_status_and_brand(text: str) -> None:
    # active, stopped either side of the drug, negated (L124), and a brand (L126): one key
    assert named_drugs(text) == {"apixaban"}


def test_named_drugs_never_reads_an_allergen() -> None:
    assert named_drugs("allergic to amoxicillin") == set()


# --- drug_in_quote (§8.4, L35, L136) ------------------------------------------------------


def test_drug_in_quote_is_a_reference_free_critical_check() -> None:
    check = REGISTRY["drug_in_quote"]
    assert (check.severity, check.requires_reference, check.needs_judge, check.origin) == (
        Severity.CRITICAL,
        False,
        False,
        "model",
    )


def test_drug_in_quote_fires_on_a_drug_its_span_doesnt_name() -> None:
    note, raw = _note(("Start amoxicillin", "Will start antibiotics"))
    findings = check_drug_in_quote(note, raw)
    assert _named(findings) == ["amoxicillin"]
    assert findings[0].claim_ids == (0,)


def test_drug_in_quote_passes_a_drug_its_span_names_by_brand() -> None:
    note, raw = _note(("Continue lisinopril 10 mg daily", "Zestril 10 mg daily, continue"))
    assert check_drug_in_quote(note, raw) == []


def test_drug_in_quote_leaves_a_status_difference_to_status() -> None:
    # D13: "not on apixaban" names apixaban; the flip to active is status, not presence
    note, raw = _note(("Continue apixaban", "pt not on apixaban"))
    assert check_drug_in_quote(note, raw) == []


def test_drug_in_quote_fires_on_a_swapped_stop_order() -> None:
    # L136: as active drugs alone, both sides read empty and this passed
    note, raw = _note(("Discontinue metformin", "discontinue lisinopril"))
    assert _named(check_drug_in_quote(note, raw)) == ["metformin"]


def test_drug_in_quote_fires_on_an_allergen_written_as_an_order() -> None:
    note, raw = _note(("Start amoxicillin", "allergic to amoxicillin"))
    assert _named(check_drug_in_quote(note, raw)) == ["amoxicillin"]


def test_drug_in_quote_reads_the_span_never_the_quote() -> None:
    # invariant 14: at Tier 3 the quote is the model's claim about the source (L35)
    raw = "will start azithromycin 500 mg daily"
    claim = ClinicalClaim(
        id=0,
        text="Start amoxicillin 500 mg daily",
        section="P",
        source_quote="will start amoxicillin 500 mg daily",
        source_span=(0, len(raw)),
        flags=(SafetyFlag.PARAPHRASED,),
    )
    assert _named(check_drug_in_quote(SOAPNote(claims=(claim,)), raw)) == ["amoxicillin"]


def test_drug_in_quote_reads_the_claims_own_span_not_the_raw_text() -> None:
    note, raw = _note(
        ("Continue amoxicillin", "continue amoxicillin"),
        ("Start amoxicillin", "Will start antibiotics"),
    )
    assert [f.claim_ids for f in check_drug_in_quote(note, raw)] == [(1,)]


def test_drug_in_quote_skips_a_claim_that_grounds_nowhere() -> None:
    # §8.4: an ungrounded claim is grounding's red badge, not a span comparison
    note, raw = _note(("Start amoxicillin", None))
    assert check_drug_in_quote(note, raw) == []


def test_drug_in_quote_finds_each_drug_once_in_name_order() -> None:
    # the whole vocabulary, in reverse: name order has to come from the check's sort
    text = "Start " + ", ".join(sorted(GENERIC_DRUGS, reverse=True))
    note, raw = _note((text, "Start antibiotics"))
    findings = check_drug_in_quote(note, raw)
    assert _named(findings) == sorted(GENERIC_DRUGS)
    assert {f.claim_ids for f in findings} == {(0,)}


# --- hallucinated_medication (§8.4, D6, L136) ---------------------------------------------


def test_hallucinated_medication_is_a_reference_free_critical_check() -> None:
    check = REGISTRY["hallucinated_medication"]
    assert (check.severity, check.requires_reference, check.needs_judge, check.origin) == (
        Severity.CRITICAL,
        False,
        False,
        "model",
    )


def test_hallucinated_medication_fires_on_a_drug_in_a_claim_that_grounds_nowhere() -> None:
    note, raw = _note(("Continue lisinopril", "continue lisinopril"), ("Start amoxicillin", None))
    findings = check_hallucinated_medication(note, raw)
    assert _named(findings) == ["amoxicillin"]
    assert findings[0].claim_ids == (1,)


@pytest.mark.parametrize("text", ["Discontinue apixaban", "Hold apixaban", "Not on apixaban"])
def test_hallucinated_medication_fires_on_a_drug_named_at_any_status(text: str) -> None:
    # L136: as active drugs alone, an ungrounded stop or denial named nothing
    note, raw = _note((text, None))
    assert _named(check_hallucinated_medication(note, raw)) == ["apixaban"]


def test_hallucinated_medication_passes_a_claim_that_grounds_nowhere_and_names_no_drug() -> None:
    note, raw = _note(("Follow up in one week", None))
    assert check_hallucinated_medication(note, raw) == []


def test_hallucinated_medication_passes_a_paraphrased_claim() -> None:
    raw = "will start azithromycin 500 mg daily"
    claim = ClinicalClaim(
        id=0,
        text="Start amoxicillin 500 mg daily",
        section="P",
        source_quote="will start amoxicillin 500 mg daily",
        source_span=(0, len(raw)),
        flags=(SafetyFlag.PARAPHRASED,),
    )
    assert check_hallucinated_medication(SOAPNote(claims=(claim,)), raw) == []


def test_hallucinated_medication_reads_groundings_flag_never_the_span() -> None:
    # D6: evals consume grounding's flags; ground() never pairs UNSUPPORTED with a span, so
    # only a hand-built claim tells reading the flag from re-deriving it
    raw = "continue lisinopril"
    claim = ClinicalClaim(
        id=0,
        text="Start amoxicillin",
        section="P",
        source_quote=raw,
        source_span=(0, len(raw)),
        flags=(SafetyFlag.UNSUPPORTED,),
    )
    assert _named(check_hallucinated_medication(SOAPNote(claims=(claim,)), raw)) == ["amoxicillin"]


def test_hallucinated_medication_finds_each_drug_once_in_name_order() -> None:
    # the whole vocabulary, in reverse: name order has to come from the check's sort
    text = "Start " + ", ".join(sorted(GENERIC_DRUGS, reverse=True))
    note, raw = _note((text, None))
    findings = check_hallucinated_medication(note, raw)
    assert _named(findings) == sorted(GENERIC_DRUGS)
    assert {f.claim_ids for f in findings} == {(0,)}


def test_the_presence_checks_split_a_note_by_whether_each_claim_grounds() -> None:
    # a grounded claim is drug_in_quote's, an ungrounded one hallucinated_medication's
    note, raw = _note(("Start amoxicillin", "Will start antibiotics"), ("Start azithromycin", None))
    assert [f.claim_ids for f in check_drug_in_quote(note, raw)] == [(0,)]
    assert [f.claim_ids for f in check_hallucinated_medication(note, raw)] == [(1,)]


# --- med_status_consistency (§8.4, D13, L124) ---------------------------------------------


def test_med_status_consistency_is_a_reference_free_critical_check() -> None:
    check = REGISTRY["med_status_consistency"]
    assert (check.severity, check.requires_reference, check.needs_judge, check.origin) == (
        Severity.CRITICAL,
        False,
        False,
        "model",
    )


def test_med_status_consistency_fires_on_a_continued_drug_written_as_stopped() -> None:
    # D13's dangerous direction
    note, raw = _note(("Discontinue apixaban", "continue apixaban"))
    findings = check_med_status_consistency(note, raw)
    assert [f.detail for f in findings] == [
        "apixaban: stopped in the claim, active in its source span"
    ]
    assert findings[0].claim_ids == (0,)


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("Continue lisinopril", "lisinopril discontinued due to cough"),
        ("Continue apixaban", "pt not on apixaban"),
    ],
    ids=["stopped-after-the-drug", "negated"],
)
def test_med_status_consistency_fires_on_a_stopped_drug_written_as_active(
    text: str, span: str
) -> None:
    # a post-cue stop (L125) and a negation, which status reads as stopped (L124)
    note, raw = _note((text, span))
    assert len(check_med_status_consistency(note, raw)) == 1


def test_med_status_consistency_passes_a_status_both_sides_assert() -> None:
    note, raw = _note(("Hold metformin", "metformin held"))
    assert check_med_status_consistency(note, raw) == []


def test_med_status_consistency_passes_one_of_the_spans_statuses() -> None:
    # status(text) ⊆ status(span): a claim may report part of what its span says
    note, raw = _note(
        ("Restart metformin in 48 hours", "metformin held, restart metformin in 48 hours")
    )
    assert check_med_status_consistency(note, raw) == []


def test_med_status_consistency_fires_on_a_status_the_span_lacks_beside_one_it_has() -> None:
    note, raw = _note(("Hold metformin, restart metformin in 48 hours", "restart metformin"))
    findings = check_med_status_consistency(note, raw)
    assert [f.detail for f in findings] == [
        "metformin: active and stopped in the claim, active in its source span"
    ]


def test_med_status_consistency_reads_the_claims_own_span_not_the_raw_text() -> None:
    note, raw = _note(
        ("Continue apixaban", "continue apixaban"), ("Continue apixaban", "apixaban held")
    )
    assert [f.claim_ids for f in check_med_status_consistency(note, raw)] == [(1,)]


def test_med_status_consistency_reads_the_span_never_the_quote() -> None:
    # invariant 14: the quote agrees with the claim; the span it grounded to doesn't (L35)
    raw = "discontinue apixaban 5 mg bid"
    claim = ClinicalClaim(
        id=0,
        text="Continue apixaban 5 mg bid",
        section="P",
        source_quote="continue apixaban 5 mg bid",
        source_span=(0, len(raw)),
        flags=(SafetyFlag.PARAPHRASED,),
    )
    assert _named(check_med_status_consistency(SOAPNote(claims=(claim,)), raw)) == ["apixaban"]


def test_med_status_consistency_skips_a_claim_that_grounds_nowhere() -> None:
    note, raw = _note(("Discontinue apixaban", None))
    assert check_med_status_consistency(note, raw) == []


def test_med_status_consistency_finds_each_drug_once_in_name_order() -> None:
    # the whole vocabulary, in reverse: name order has to come from the check's sort
    drugs = sorted(GENERIC_DRUGS, reverse=True)
    text = ", ".join(f"stop {d}" for d in drugs)
    span = ", ".join(f"continue {d}" for d in drugs)
    note, raw = _note((text, span))
    findings = check_med_status_consistency(note, raw)
    assert _named(findings) == sorted(GENERIC_DRUGS)
    assert {f.claim_ids for f in findings} == {(0,)}


@pytest.mark.parametrize(
    ("text", "span", "presence", "status"),
    [
        ("Discontinue metformin", "discontinue lisinopril", ["metformin"], []),
        ("Continue apixaban", "pt not on apixaban", [], ["apixaban"]),
    ],
    ids=["a-drug-the-span-lacks", "a-status-the-span-lacks"],
)
def test_presence_and_status_split_one_error_into_one_finding(
    text: str, span: str, presence: list[str], status: list[str]
) -> None:
    # D13: a drug only one side names is presence's; a status on a drug both name is status's
    note, raw = _note((text, span))
    assert _named(check_drug_in_quote(note, raw)) == presence
    assert _named(check_med_status_consistency(note, raw)) == status


# --- negation_consistency (§8.4, L33, L139) -----------------------------------------------


def test_negation_consistency_is_a_reference_free_critical_check() -> None:
    check = REGISTRY["negation_consistency"]
    assert (check.severity, check.requires_reference, check.needs_judge, check.origin) == (
        Severity.CRITICAL,
        False,
        False,
        "model",
    )


def test_negation_consistency_fires_on_a_denied_finding_written_as_reported() -> None:
    note, raw = _note(("Reports chest pain", "denies chest pain"))
    findings = check_negation_consistency(note, raw)
    assert [f.detail for f in findings] == [
        "chest pain: present in the claim, absent in its source span"
    ]
    assert findings[0].claim_ids == (0,)


def test_negation_consistency_fires_on_a_reported_finding_written_as_denied() -> None:
    note, raw = _note(("Denies fever", "reports fever and chills"))
    assert _named(check_negation_consistency(note, raw)) == ["fever"]


def test_negation_consistency_passes_a_polarity_both_sides_assert() -> None:
    note, raw = _note(("Denies chest pain", "denies chest pain or shortness of breath"))
    assert check_negation_consistency(note, raw) == []


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("Reports chest pain", "denies fever"),
        ("No fever", "Temp 37.0, afebrile"),
        ("Reports chest pain", "denies CP"),
    ],
    ids=["invented", "afebrile", "unlisted-name"],
)
def test_negation_consistency_leaves_a_finding_the_span_doesnt_name(text: str, span: str) -> None:
    # L139: compared per finding, for findings both sides name; §8.8 states the recall cost
    note, raw = _note((text, span))
    assert check_negation_consistency(note, raw) == []


@pytest.mark.parametrize(
    "text", ["Reports chest pain on exertion", "Denies chest pain"], ids=["kept", "selective"]
)
def test_negation_consistency_passes_one_of_the_spans_polarities(text: str) -> None:
    # polarity(text) ⊆ polarity(span): with qualifiers unread, a claim keeping either half of
    # a mixed span passes, the faithful half and the selective one alike (§8.8, L139)
    note, raw = _note((text, "denies chest pain at rest, reports chest pain on exertion"))
    assert check_negation_consistency(note, raw) == []


def test_negation_consistency_fires_on_a_polarity_the_span_lacks_beside_one_it_has() -> None:
    note, raw = _note(
        (
            "Denies chest pain at rest, reports chest pain on exertion",
            "reports chest pain on exertion",
        )
    )
    findings = check_negation_consistency(note, raw)
    assert [f.detail for f in findings] == [
        "chest pain: absent and present in the claim, present in its source span"
    ]


def test_negation_consistency_reads_the_claims_own_span_not_the_raw_text() -> None:
    note, raw = _note(("Denies fever", "denies fever"), ("Denies fever", "reports fever"))
    assert [f.claim_ids for f in check_negation_consistency(note, raw)] == [(1,)]


def test_negation_consistency_reads_the_span_never_the_quote() -> None:
    # invariant 14: the quote agrees with the claim; the span it grounded to doesn't (L35)
    raw = "reports chest pain at rest"
    claim = ClinicalClaim(
        id=0,
        text="Denies chest pain at rest",
        section="S",
        source_quote="denies chest pain at rest",
        source_span=(0, len(raw)),
        flags=(SafetyFlag.PARAPHRASED,),
    )
    assert _named(check_negation_consistency(SOAPNote(claims=(claim,)), raw)) == ["chest pain"]


def test_negation_consistency_skips_a_claim_that_grounds_nowhere() -> None:
    note, raw = _note(("Reports chest pain", None))
    assert check_negation_consistency(note, raw) == []


def test_negation_consistency_finds_each_finding_once_in_name_order() -> None:
    # every listed finding, in reverse: name order has to come from the check's sort
    names = sorted(FINDINGS, reverse=True)
    text = ", ".join(f"denies {n}" for n in names)
    span = ", ".join(f"reports {n}" for n in names)
    note, raw = _note((text, span))
    findings = check_negation_consistency(note, raw)
    assert _named(findings) == sorted(FINDINGS)
    assert {f.claim_ids for f in findings} == {(0,)}


# --- diagnosis_in_quote (§8.4, D7, D12, L140) ---------------------------------------------


def test_diagnosis_in_quote_is_a_reference_free_critical_check() -> None:
    check = REGISTRY["diagnosis_in_quote"]
    assert (check.severity, check.requires_reference, check.needs_judge, check.origin) == (
        Severity.CRITICAL,
        False,
        False,
        "model",
    )


def test_diagnosis_in_quote_fires_on_an_invented_diagnosis() -> None:
    # D7 and D12's trap: a vital sign written as a diagnosis
    note, raw = _note(("Hypertensive urgency", "BP 190/110 on arrival"))
    findings = check_diagnosis_in_quote(note, raw)
    assert [(f.detail, f.severity) for f in findings] == [
        (
            "hypertensive urgency: definite in the claim, not named in its source span",
            Severity.CRITICAL,
        )
    ]
    assert findings[0].claim_ids == (0,)


def test_diagnosis_in_quote_fires_on_an_upgrade() -> None:
    note, raw = _note(("Pulmonary embolism", "r/o PE, CTA ordered"))
    assert [(f.detail, f.severity) for f in check_diagnosis_in_quote(note, raw)] == [
        (
            "pulmonary embolism: definite in the claim, rule-out in its source span",
            Severity.CRITICAL,
        )
    ]


def test_diagnosis_in_quote_lowers_a_downgrade_to_a_warning() -> None:
    note, raw = _note(("Possible pneumonia", "pneumonia"))
    assert [(f.detail, f.severity) for f in check_diagnosis_in_quote(note, raw)] == [
        ("pneumonia: possible in the claim, definite in its source span", Severity.WARNING)
    ]


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("Likely pneumonia", "likely pneumonia"),
        ("Pneumonia", "PNA"),
        ("r/o PE", "PE possible, r/o PE"),
        ("Likely PE", "r/o PE; PE likely given D-dimer"),
        ("PE ruled out", "CTA negative, PE ruled out"),
        ("PE ruled out", "r/o PE; CTA negative, PE ruled out"),
    ],
    ids=[
        "same",
        "alias",
        "one-of-the-spans",
        "strongest-matches",
        "exclusion",
        "workup-and-result",
    ],
)
def test_diagnosis_in_quote_passes_a_reading_the_span_supports(text: str, span: str) -> None:
    note, raw = _note((text, span))
    assert check_diagnosis_in_quote(note, raw) == []


@pytest.mark.parametrize(
    ("text", "span", "severity"),
    [
        ("PE ruled out", "r/o PE", Severity.CRITICAL),
        ("No pneumonia", "pneumonia", Severity.CRITICAL),
        ("PE ruled out", "CTA negative", Severity.CRITICAL),
        ("PE", "PE ruled out", Severity.CRITICAL),
        ("Likely PE", "PE ruled out", Severity.CRITICAL),
        ("Possible PE", "PE ruled out", Severity.WARNING),
        ("r/o PE", "PE ruled out", Severity.WARNING),
    ],
    ids=[
        "premature-closure",
        "flip",
        "inferred-exclusion",
        "definite-against-an-exclusion",
        "probable-against-an-exclusion",
        "possible-reopens",
        "rule-out-reopens",
    ],
)
def test_diagnosis_in_quote_reads_exclusions(text: str, span: str, severity: Severity) -> None:
    # L140: an exclusion the span doesn't make is CRITICAL; asserting what the span excludes is
    # CRITICAL as definite or probable, and a WARNING as possible or rule-out, which reopen it
    note, raw = _note((text, span))
    assert [f.severity for f in check_diagnosis_in_quote(note, raw)] == [severity]


def test_diagnosis_in_quote_describes_an_exclusion() -> None:
    note, raw = _note(("PE ruled out", "r/o PE"))
    assert [f.detail for f in check_diagnosis_in_quote(note, raw)] == [
        "pulmonary embolism: excluded in the claim, rule-out in its source span"
    ]


def test_diagnosis_in_quote_reads_the_claims_own_span_not_the_raw_text() -> None:
    note, raw = _note(
        ("Likely pneumonia", "likely pneumonia"), ("Likely pneumonia", "r/o pneumonia")
    )
    assert [f.claim_ids for f in check_diagnosis_in_quote(note, raw)] == [(1,)]


def test_diagnosis_in_quote_reads_the_span_never_the_quote() -> None:
    # invariant 14: the quote agrees with the claim; the span it grounded to doesn't (L35)
    raw = "r/o pulmonary embolism, CTA ordered"
    claim = ClinicalClaim(
        id=0,
        text="Pulmonary embolism",
        section="A",
        source_quote="pulmonary embolism, CTA ordered",
        source_span=(0, len(raw)),
        flags=(SafetyFlag.PARAPHRASED,),
    )
    assert _named(check_diagnosis_in_quote(SOAPNote(claims=(claim,)), raw)) == [
        "pulmonary embolism"
    ]


def test_diagnosis_in_quote_skips_a_claim_that_grounds_nowhere() -> None:
    note, raw = _note(("Hypertensive urgency", None))
    assert check_diagnosis_in_quote(note, raw) == []


def test_diagnosis_in_quote_finds_each_diagnosis_once_in_name_order() -> None:
    # every listed diagnosis, in reverse: name order has to come from the check's sort
    note, raw = _note((", ".join(sorted(DIAGNOSES, reverse=True)), "Assessment deferred"))
    findings = check_diagnosis_in_quote(note, raw)
    assert _named(findings) == sorted(DIAGNOSES)
    assert {f.claim_ids for f in findings} == {(0,)}


# --- dose_consistency (§8.4, D1, L141) ----------------------------------------------------


def test_dose_consistency_is_a_reference_free_warning() -> None:
    check = REGISTRY["dose_consistency"]
    assert (check.severity, check.requires_reference, check.needs_judge, check.origin) == (
        Severity.WARNING,
        False,
        False,
        "model",
    )


def test_dose_consistency_fires_on_a_tenfold_dose() -> None:
    note, raw = _note(("Continue lisinopril 100 mg daily", "lisinopril 10 mg daily"))
    findings = check_dose_consistency(note, raw)
    assert [f.detail for f in findings] == [
        "lisinopril: 100 mg daily in the claim, 10 mg daily in its source span"
    ]
    assert (findings[0].claim_ids, findings[0].severity) == ((0,), None)


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("Continue lisinopril 10 mg daily", "lisinopril 10 mg daily"),
        ("Acetaminophen 1 g q6h", "acetaminophen 1000 mg q6h"),
        ("Acetaminophen 1.005 g", "acetaminophen 1005 mg"),
        ("Metformin 500 mg", "metformin 500 mg bid"),
        ("Metformin 1000 mg", "metformin 500 mg, then 1000 mg"),
    ],
    ids=["same", "grams-as-milligrams", "exact-arithmetic", "no-frequency", "one-of-a-titration"],
)
def test_dose_consistency_passes_a_dose_the_span_charts(text: str, span: str) -> None:
    # L141: mass compares in micrograms, exactly (in floats, 1.005 * 1000 is 1004.999...), and
    # a dose the claim charts without a frequency matches the span's at any
    note, raw = _note((text, span))
    assert check_dose_consistency(note, raw) == []


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("Amoxicillin 5 ml", "amoxicillin 5 mg"),
        ("Metformin 500 mg bid", "metformin 500 mg"),
        ("Metformin 500 mg tid", "metformin 500 mg bid"),
        ("Continue metformin 1000 mg bid", "continue metformin"),
        ("Metformin 500 mg, then 2000 mg", "metformin 500 mg"),
    ],
    ids=["volume-for-mass", "a-frequency-the-span-lacks", "another-frequency", "no-dose", "beside"],
)
def test_dose_consistency_fires_on_a_dose_the_span_doesnt_chart(text: str, span: str) -> None:
    note, raw = _note((text, span))
    assert len(check_dose_consistency(note, raw)) == 1


def test_dose_consistency_names_a_missing_dose() -> None:
    note, raw = _note(("Continue metformin 1000 mg bid", "continue metformin"))
    assert [f.detail for f in check_dose_consistency(note, raw)] == [
        "metformin: 1000 mg bid in the claim, no dose in its source span"
    ]


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("Acetaminophen 1 g", "acetaminophen 1000 mg"),
        ("Acetaminophen 1 mg", "acetaminophen 1000 μg"),
        ("Acetaminophen 1 g", "acetaminophen 1000000 μg"),
    ],
    ids=["g-as-mg", "mg-as-ug", "g-as-ug"],
)
def test_each_mass_unit_charts_the_same_dose_as_the_others(text: str, span: str) -> None:
    # facts, not the table read back: each pair pins two of DOSE_MASS_UG's three sizes
    note, raw = _note((text, span))
    assert check_dose_consistency(note, raw) == []


def test_only_ml_and_units_carry_no_mass() -> None:
    # a canonical unit outside DOSE_MASS_UG compares only to itself (L141)
    assert set(DOSE_UNITS.values()) - DOSE_MASS_UG.keys() == {"ml", "unit"}
    assert DOSE_MASS_UG.keys() <= set(DOSE_UNITS.values())


def test_dose_consistency_leaves_a_drug_the_span_doesnt_name_to_presence() -> None:
    note, raw = _note(("Start amoxicillin 500 mg", "Will start antibiotics"))
    assert _named(check_drug_in_quote(note, raw)) == ["amoxicillin"]
    assert check_dose_consistency(note, raw) == []


def test_dose_consistency_reads_the_claims_own_span_not_the_raw_text() -> None:
    note, raw = _note(
        ("Metformin 500 mg bid", "metformin 500 mg bid"),
        ("Metformin 500 mg bid", "metformin 850 mg bid"),
    )
    # the first claim's span charts 500 mg, so only a check reading the raw text passes both
    assert [f.claim_ids for f in check_dose_consistency(note, raw)] == [(1,)]


def test_dose_consistency_reads_the_span_never_the_quote() -> None:
    # invariant 14: the quote agrees with the claim; the span it grounded to doesn't (L35)
    raw = "lisinopril 10 mg daily"
    claim = ClinicalClaim(
        id=0,
        text="Lisinopril 100 mg daily",
        section="P",
        source_quote="lisinopril 100 mg daily",
        source_span=(0, len(raw)),
        flags=(SafetyFlag.PARAPHRASED,),
    )
    assert _named(check_dose_consistency(SOAPNote(claims=(claim,)), raw)) == ["lisinopril"]


def test_dose_consistency_skips_a_claim_that_grounds_nowhere() -> None:
    note, raw = _note(("Lisinopril 100 mg daily", None))
    assert check_dose_consistency(note, raw) == []


def test_dose_consistency_finds_each_drug_once_in_name_order() -> None:
    # the whole vocabulary, in reverse: name order has to come from the check's sort
    drugs = sorted(GENERIC_DRUGS, reverse=True)
    text = ", ".join(f"{d} 20 mg" for d in drugs)
    span = ", ".join(f"{d} 10 mg" for d in drugs)
    note, raw = _note((text, span))
    findings = check_dose_consistency(note, raw)
    assert _named(findings) == sorted(GENERIC_DRUGS)
    assert {f.claim_ids for f in findings} == {(0,)}


# --- allergy_preserved (§8.4, D10, D17, L144) ---------------------------------------------


def test_allergy_preserved_is_a_reference_free_critical_check() -> None:
    check = REGISTRY["allergy_preserved"]
    assert (check.severity, check.requires_reference, check.needs_judge, check.origin) == (
        Severity.CRITICAL,
        False,
        False,
        "model",
    )


def test_allergy_preserved_fires_on_an_allergy_no_claim_states() -> None:
    note, raw = _note(("Start azithromycin", "start azithromycin"))
    findings = check_allergy_preserved(note, raw + " PCN allergy.")
    assert [(f.detail, f.claim_ids, f.severity) for f in findings] == [
        ("penicillin: in the source, not the note", (), None)
    ]


def test_allergy_preserved_passes_an_allergy_a_claim_states_in_other_words() -> None:
    note, raw = _note(("PCN allergy", "allergic to penicillin"))
    assert check_allergy_preserved(note, raw) == []


@pytest.mark.parametrize("section", ["S", "O", "A", "P"])
def test_allergy_preserved_reads_a_claim_in_any_section(section: Section) -> None:
    # invariant 5: the section is the model's judgment call, display-only
    raw = "Allergic to sulfa."
    claim = ClinicalClaim(
        id=0, text="Sulfa allergy", section=section, source_quote=raw, source_span=(0, len(raw))
    )
    assert check_allergy_preserved(SOAPNote(claims=(claim,)), raw) == []


def test_allergy_preserved_reads_a_claim_that_grounds_nowhere() -> None:
    # the allergy is in the note; whether its claim grounds is the red badge's question
    note, raw = _note(("Allergic to amoxicillin", None))
    assert check_allergy_preserved(note, raw + "Allergic to amoxicillin.") == []


def test_allergy_preserved_leaves_an_allergy_only_the_note_states() -> None:
    note, raw = _note(("Sulfa allergy", None))
    assert check_allergy_preserved(note, raw + "Start azithromycin.") == []


@pytest.mark.parametrize(
    ("raw", "statement"),
    [("NKDA.", "nkda"), ("No known allergies.", "nka"), ("Allergies: none", "nka")],
)
def test_allergy_preserved_lowers_a_dropped_statement_to_a_warning(
    raw: str, statement: str
) -> None:
    # D10, L144: an undocumented allergy status prompts a re-ask
    findings = check_allergy_preserved(SOAPNote(claims=()), raw)
    assert [(f.detail, f.severity) for f in findings] == [
        (f"{statement}: in the source, not the note", Severity.WARNING)
    ]


def test_allergy_preserved_keeps_nkda_and_nka_apart() -> None:
    # D10: NKA says more than NKDA, so a note writing one for the other drops the source's
    note, raw = _note(("No known allergies", None))
    findings = check_allergy_preserved(note, raw + "NKDA.")
    assert [f.detail for f in findings] == ["nkda: in the source, not the note"]


def test_allergy_preserved_finds_each_allergy_once_in_name_order() -> None:
    # every allergen the lexicon names, in reverse: name order has to come from the check's sort
    allergens = (set(ALLERGY_ALIASES.values()) | GENERIC_DRUGS) - {"nkda", "nka"}
    raw = "Allergies: " + ", ".join(sorted(allergens, reverse=True))
    findings = check_allergy_preserved(SOAPNote(claims=()), raw)
    assert [f.detail.partition(":")[0] for f in findings] == sorted(allergens)


# --- registration -------------------------------------------------------------------------


def test_importing_the_runner_registers_the_roster() -> None:
    """runner.py imports checks.py for its side effect (§8.7).

    In-process, this file's own import of checks.py registers the roster first, so only a
    fresh interpreter shows what the runner's import does by itself.
    """
    script = (
        "import backend.evals.runner; "
        "from backend.evals.registry import REGISTRY; "
        "print(*sorted(REGISTRY))"
    )
    # the repo root on PYTHONPATH, as test_api's logging test sets it
    existing = os.environ.get("PYTHONPATH")
    env = {
        **os.environ,
        "PYTHONPATH": str(_REPO_ROOT) + (os.pathsep + existing if existing else ""),
    }
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.split() == sorted(REGISTRY)
