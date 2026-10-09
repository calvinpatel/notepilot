"""The reference-free roster (spec §8.4), and the helpers its checks share.

A claim-local check runs one extractor over a claim's text and its source span and compares
the two (L35). Registration is this module's import side effect: runner.py imports it (§8.7).
"""

from collections.abc import Callable

from backend.clinical.extract import MedStatus, extract_findings, extract_med_status
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
