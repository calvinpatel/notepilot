"""Pins the reference-free roster's helpers and checks (spec §8.4; D6, D13, L35, L136)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.clinical.lexicons import GENERIC_DRUGS
from backend.evals.checks import (
    check_drug_in_quote,
    check_hallucinated_medication,
    check_med_status_consistency,
    named_drugs,
    span_text,
)
from backend.evals.registry import REGISTRY, Finding
from backend.schemas import ClinicalClaim, SafetyFlag, Severity, SOAPNote

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
