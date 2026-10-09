"""The reference-free roster (spec §8.4), and the helpers its checks share.

A claim-local check runs one extractor over a claim's text and its source span and compares
the two (L35); allergy_preserved compares the raw text with the whole note. Registration is
this module's import side effect: runner.py imports it (§8.7).
"""

from collections.abc import Callable, Iterable, Mapping
from decimal import Decimal
from typing import get_args

from backend.clinical.extract import (
    NO_ALLERGY_STATEMENTS,
    Certainty,
    Dose,
    MedStatus,
    extract_allergies,
    extract_diagnoses,
    extract_doses,
    extract_excluded_diagnoses,
    extract_findings,
    extract_med_status,
)
from backend.clinical.lexicons import DOSE_MASS_UG
from backend.evals.registry import Finding, register_check
from backend.schemas import ClinicalClaim, EvalCase, SafetyFlag, Severity, SOAPNote


def span_text(claim: ClinicalClaim, raw_text: str) -> str | None:
    """The claim's source span in raw_text, or None for a claim that grounds nowhere (L35)."""
    return None if claim.source_span is None else raw_text[slice(*claim.source_span)]


def named_drugs(text: str) -> set[str]:
    """Every drug the text names, whatever status it asserts, negated included (L136).

    extract_med_status's keys, so presence and status read one key set (D13). A mention in
    allergy context asserts no status, so an allergen is never a named drug (L128).
    """
    return set(extract_med_status(text))


@register_check(name="drug_in_quote", severity=Severity.CRITICAL)
def check_drug_in_quote(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None
) -> list[Finding]:
    """One finding per drug a claim names that its source span doesn't (§8.4, L35, L136).

    A status the span contradicts is D13's other half, not presence. A claim with no span
    is skipped (§8.4).

    Omission (D17): an omitted claim leaves nothing to compare, so the check passes; §8.4's
    omission table assigns that omission elsewhere.
    """
    findings: list[Finding] = []
    for claim in note.claims:
        span = span_text(claim, raw_text)
        if span is None:
            continue
        for drug in sorted(named_drugs(claim.text) - named_drugs(span)):
            findings.append(
                Finding(detail=f"{drug}: in the claim, not its source span", claim_ids=(claim.id,))
            )
    return findings


@register_check(name="hallucinated_medication", severity=Severity.CRITICAL)
def check_hallucinated_medication(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None
) -> list[Finding]:
    """One finding per drug in a claim grounding flagged UNSUPPORTED (§8.4, L136).

    Reads grounding's flag and never re-derives it (D6). A grounded claim is drug_in_quote's,
    so the two presence checks split a note between them.

    Omission (D17): an omitted claim leaves nothing to read, so the check passes; §8.4's
    omission table assigns that omission elsewhere.
    """
    findings: list[Finding] = []
    for claim in note.claims:
        if SafetyFlag.UNSUPPORTED not in claim.flags:
            continue
        for drug in sorted(named_drugs(claim.text)):
            findings.append(
                Finding(detail=f"{drug}: in a claim that grounds nowhere", claim_ids=(claim.id,))
            )
    return findings


def _compare_per_key[V](
    note: SOAPNote,
    raw_text: str,
    extract: Callable[[str], dict[str, set[V]]],
    describe: Callable[[set[V]], str],
) -> list[Finding]:
    """values(text) ⊆ values(span), per key a claim and its span both name (§8.4).

    One finding per key whose values in the claim aren't all in the span's, in key order. A
    key only one side names isn't compared, and a claim with no span is skipped.
    """
    findings: list[Finding] = []
    for claim in note.claims:
        span = span_text(claim, raw_text)
        if span is None:
            continue
        in_text, in_span = extract(claim.text), extract(span)
        for key in sorted(in_text.keys() & in_span.keys()):
            if not in_text[key] <= in_span[key]:
                findings.append(
                    Finding(
                        detail=f"{key}: {describe(in_text[key])} in the claim, "
                        f"{describe(in_span[key])} in its source span",
                        claim_ids=(claim.id,),
                    )
                )
    return findings


def _statuses(statuses: set[MedStatus]) -> str:
    """'active', 'stopped', or 'active and stopped', for a finding's detail."""
    return " and ".join(sorted(statuses))


@register_check(name="med_status_consistency", severity=Severity.CRITICAL)
def check_med_status_consistency(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None
) -> list[Finding]:
    """One finding per drug a claim and its span both name, at a status the span lacks (D13).

    status(text) ⊆ status(span), per drug (§8.4): the claim may report part of what the span
    says, and a negated mention reads as stopped (L124). A drug only one side names is
    drug_in_quote's, so an error has one finding. A claim with no span is skipped (§8.4).

    Omission (D17): an omitted claim leaves no drug in both to compare, so the check passes;
    §8.4's omission table assigns that omission elsewhere.
    """
    return _compare_per_key(note, raw_text, extract_med_status, _statuses)


def _polarities(polarities: set[bool]) -> str:
    """'present', 'absent', or 'absent and present', for a finding's detail."""
    return " and ".join(sorted("present" if p else "absent" for p in polarities))


@register_check(name="negation_consistency", severity=Severity.CRITICAL)
def check_negation_consistency(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None
) -> list[Finding]:
    """One finding per finding a claim and its span both name, at a polarity the span lacks.

    polarity(text) ⊆ polarity(span), per finding (§8.4, L33). Only findings both sides name
    are compared (L139): a finding the span doesn't name, or names in words the lexicon
    doesn't list, isn't this check's (§8.8). A claim with no span is skipped (§8.4).

    Omission (D17): an omitted claim leaves no finding in both to compare, so the check
    passes; §8.4's omission table assigns that omission elsewhere.
    """
    return _compare_per_key(note, raw_text, extract_findings, _polarities)


# A diagnosis' reading in one string: the certainties asserted for it, and whether it is excluded
type _Reading = tuple[set[Certainty], bool]

_STRONGEST_FIRST: tuple[Certainty, ...] = get_args(Certainty)

# Against a span's exclusion, a claim asserting the diagnosis this strongly contradicts it,
# CRITICAL; possible or rule-out reopen the question, a WARNING (L140).
_CONTRADICTS_AN_EXCLUSION: frozenset[Certainty] = frozenset({"definite", "probable"})

_SAID: Mapping[Certainty, str] = {
    "definite": "definite",
    "probable": "probable",
    "possible": "possible",
    "rule_out": "rule-out",
}


def _diagnosis_readings(text: str) -> dict[str, _Reading]:
    """Each diagnosis text names: asserted ones in mention order, then the rest in name order."""
    asserted, excluded = extract_diagnoses(text), extract_excluded_diagnoses(text)
    return {
        diagnosis: (asserted.get(diagnosis, set()), diagnosis in excluded)
        for diagnosis in [*asserted, *sorted(excluded - asserted.keys())]
    }


def _strongest(certainties: set[Certainty]) -> int:
    """The strongest certainty's rank, 0 for definite (§7)."""
    return min(_STRONGEST_FIRST.index(c) for c in certainties)


def _diagnosis_severity(claim: _Reading, span: _Reading) -> Severity | None:
    """How far a claim's reading of a diagnosis departs from its span's, or None (D12, L140)."""
    (claimed, claim_excludes), (spanned, span_excludes) = claim, span
    if claim_excludes and not span_excludes:
        return Severity.CRITICAL  # an exclusion the span doesn't make
    if not claimed:
        return None
    if not spanned:
        if not span_excludes:
            return Severity.CRITICAL  # invented
        if claimed & _CONTRADICTS_AN_EXCLUSION:
            return Severity.CRITICAL  # asserts what the span excludes
        return Severity.WARNING  # reopens what the span excludes
    if _strongest(claimed) < _strongest(spanned):
        return Severity.CRITICAL  # upgrade
    if not claimed <= spanned:
        return Severity.WARNING  # downgrade
    return None


def _describe(reading: _Reading) -> str:
    """'definite', 'rule-out and excluded', 'not named', ..., for a finding's detail."""
    certainties, excluded = reading
    said = [_SAID[c] for c in _STRONGEST_FIRST if c in certainties]
    return " and ".join([*said, "excluded"] if excluded else said) or "not named"


@register_check(name="diagnosis_in_quote", severity=Severity.CRITICAL)
def check_diagnosis_in_quote(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None
) -> list[Finding]:
    """One finding per diagnosis a claim names that its span doesn't support (D7, D12, L140).

    A diagnosis the span doesn't name is invented, CRITICAL. Certainty compares strongest to
    strongest: a claim's stronger than its span's is an upgrade, CRITICAL, and a certainty the
    span lacks, none stronger, is a downgrade, WARNING. An exclusion the span doesn't make is
    CRITICAL; asserting what the span excludes is CRITICAL as definite or probable and a
    WARNING as possible or rule-out (L140). A claim with no span is skipped (§8.4).

    Omission (D17): an omitted claim leaves no diagnosis to compare, so the check passes;
    §8.4's omission table assigns that omission elsewhere.
    """
    findings: list[Finding] = []
    for claim in note.claims:
        span = span_text(claim, raw_text)
        if span is None:
            continue
        in_text, in_span = _diagnosis_readings(claim.text), _diagnosis_readings(span)
        for diagnosis in sorted(in_text):
            span_reading = in_span.get(diagnosis, (set(), False))
            severity = _diagnosis_severity(in_text[diagnosis], span_reading)
            if severity is not None:
                findings.append(
                    Finding(
                        detail=f"{diagnosis}: {_describe(in_text[diagnosis])} in the claim, "
                        f"{_describe(span_reading)} in its source span",
                        claim_ids=(claim.id,),
                        severity=severity,
                    )
                )
    return findings


def _amount(dose: Dose) -> tuple[str, Decimal]:
    """A dose's unit and amount, a mass in micrograms (L141): "1 g" and "1000 mg" compare equal.

    Decimal from the value's shortest repr, so the arithmetic is exact: in floats, 1.005 g is
    1004999.9999999999 μg.
    """
    value = Decimal(str(dose.value))
    if dose.unit in DOSE_MASS_UG:
        return "μg", value * DOSE_MASS_UG[dose.unit]
    return dose.unit, value


def _matches(claim_dose: Dose, span_dose: Dose) -> bool:
    """The same amount, at the claim's frequency; a claim's dose without one matches any."""
    return _amount(claim_dose) == _amount(span_dose) and (
        claim_dose.freq is None or claim_dose.freq == span_dose.freq
    )


def _doses(doses: Iterable[Dose]) -> str:
    """'500 mg bid', '500 mg and 1000 mg', or 'no dose', for a finding's detail."""
    said = [
        f"{Decimal(str(d.value)).normalize():f} {d.unit}" + (f" {d.freq}" if d.freq else "")
        for d in sorted(doses, key=lambda d: (d.unit, d.value, d.freq or ""))
    ]
    return " and ".join(said) or "no dose"


@register_check(name="dose_consistency", severity=Severity.WARNING)
def check_dose_consistency(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None
) -> list[Finding]:
    """One finding per drug a claim and its span both name, at a dose the span doesn't chart.

    doses(text) ⊆ doses(span), parsed (§8.4, D1): a mass compares in micrograms, exactly, and a
    dose the claim charts without a frequency matches the span's at any (L141). A drug the span
    doesn't name is drug_in_quote's. A claim with no span is skipped (§8.4).
    """
    findings: list[Finding] = []
    for claim in note.claims:
        span = span_text(claim, raw_text)
        if span is None:
            continue
        in_text, in_span = extract_doses(claim.text), extract_doses(span)
        for drug in sorted(in_text.keys() & named_drugs(span)):
            spanned = in_span.get(drug, set())
            if not all(any(_matches(d, s) for s in spanned) for d in in_text[drug]):
                findings.append(
                    Finding(
                        detail=f"{drug}: {_doses(in_text[drug])} in the claim, "
                        f"{_doses(spanned)} in its source span",
                        claim_ids=(claim.id,),
                    )
                )
    return findings


@register_check(name="allergy_preserved", severity=Severity.CRITICAL)
def check_allergy_preserved(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None
) -> list[Finding]:
    """One finding per allergy the raw text states and no claim does (§8.4).

    allergies(raw) − allergies(note), over every claim, grounded or not, whatever its section
    (invariant 5). A dropped NKDA or NKA prompts a re-ask, not a missed allergy, so its
    finding is a WARNING (D10, L144). An allergy only the note states isn't this check's. The
    finding names no claim, since the allergy is in none.

    Omission (D17): an omitted allergy is this check's subject, so it fires.
    """
    in_note = {allergen for claim in note.claims for allergen in extract_allergies(claim.text)}
    return [
        Finding(
            detail=f"{allergen}: in the source, not the note",
            claim_ids=(),
            severity=Severity.WARNING if allergen in NO_ALLERGY_STATEMENTS else None,
        )
        for allergen in sorted(extract_allergies(raw_text) - in_note)
    ]
