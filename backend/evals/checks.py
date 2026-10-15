"""The reference-free roster (spec §8.4), the helpers its checks share, and the reference
labels' readings.

A claim-local check runs one extractor over a claim's text and its source span and compares
the two (L35); allergy_preserved compares the raw text with the whole note. Registration is
this module's import side effect: runner.py imports it (§8.7), and so does loader.py, for
the label readers. Every check takes the config (L190); a check reads its knob from it,
never from settings (L187).

A reference label's text is read by its kind's extractor and states one reading (§8.4 point
4, L214): read_label reads it, label_problem says why a label can't be read, preserve_miss
compares a label with texts, and adds says whether a text adds one.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import NoReturn, get_args

from backend.clinical.extract import (
    ABSENCE_WORDS,
    NO_ALLERGY_STATEMENTS,
    Certainty,
    Dose,
    MedStatus,
    content_tokens,
    extract_allergies,
    extract_diagnoses,
    extract_doses,
    extract_drugs,
    extract_excluded_diagnoses,
    extract_findings,
    extract_med_status,
    new_prescriptions,
)
from backend.clinical.lexicons import CROSS_REACTIVITY, DOSE_MASS_UG, DRUG_CLASS, R1_GROUP
from backend.evals.registry import Finding, register_check
from backend.schemas import (
    ChecksConfig,
    ClinicalClaim,
    EvalCase,
    NotAddItem,
    PreserveItem,
    SafetyFlag,
    Severity,
    SOAPNote,
)


def span_text(claim: ClinicalClaim, raw_text: str) -> str | None:
    """The claim's source span in raw_text, or None for a claim that grounds nowhere (L35)."""
    return None if claim.source_span is None else raw_text[slice(*claim.source_span)]


def drug_mentions(note: SOAPNote) -> list[tuple[str, tuple[int, ...]]]:
    """Each active drug a claim names, with that claim's id: claims in order, drugs by name (§7).

    Every claim, whatever its section (invariant 5).
    """
    return [
        (drug, (claim.id,)) for claim in note.claims for drug in sorted(extract_drugs(claim.text))
    ]


def named_drugs(text: str) -> set[str]:
    """Every drug the text names, whatever status it asserts, negated included (L136).

    extract_med_status's keys, so presence and status read one key set (D13). A mention in
    allergy context asserts no status, so an allergen is never a named drug (L128).
    """
    return set(extract_med_status(text))


@register_check(name="drug_in_quote", severity=Severity.CRITICAL)
def check_drug_in_quote(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
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
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
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
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
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
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
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
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
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
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
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
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
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


# a class name is its own class (D9)
_CLASSES: frozenset[str] = frozenset(DRUG_CLASS.values())

# CROSS_REACTIVITY's severities as the spine's; a value Severity lacks fails at import
_CROSS_REACTIVITY: Mapping[tuple[str, str], Severity] = {
    pair: Severity(call) for pair, call in CROSS_REACTIVITY.items()
}


def _drug_class(name: str) -> str | None:
    """A drug's class, a class name's own, or None."""
    return name if name in _CLASSES else DRUG_CLASS.get(name)


def contraindication(allergen: str, drug: str) -> tuple[Severity, str] | None:
    """D9's ladder for one allergen and one drug: the first rung that matches, or None.

    1. the same drug, CRITICAL; 2. the same class, CRITICAL; 3. an identical R1 side chain
    across classes, CRITICAL; 4. CROSS_REACTIVITY's call for the two classes. The second value
    says why, for a finding's detail. An allergy to a class names no side chain, so rung 4
    asks for the specific drug (D14).
    """
    if allergen == drug:
        return Severity.CRITICAL, "the allergen itself"
    allergen_class, drug_class = _drug_class(allergen), _drug_class(drug)
    if allergen_class is not None and allergen_class == drug_class:
        return Severity.CRITICAL, f"in the allergen's class ({drug_class})"
    side_chain = R1_GROUP.get(allergen)
    if side_chain is not None and side_chain == R1_GROUP.get(drug):
        return Severity.CRITICAL, f"shares the allergen's R1 side chain ({side_chain})"
    if allergen_class is None or drug_class is None:
        return None
    call = _CROSS_REACTIVITY.get((allergen_class, drug_class))
    if call is None:
        return None
    refine = (
        f"specify the {allergen} to refine the risk"
        if allergen in _CLASSES
        else "R1 side chain not shared"
    )
    return call, f"cross-reactive with {allergen_class} ({drug_class}); {refine}"


@register_check(name="allergy_contraindication", severity=Severity.CRITICAL, origin="source")
def check_allergy_contraindication(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
) -> list[Finding]:
    """One finding per allergy and active drug that D9's ladder pairs (§8.4; D9, D14).

    Allergies come from the raw text and every claim; drugs from every claim, then each new
    prescription the raw text starts that no claim names (L51). A finding names the drug's
    claim and the allergy's (L37), at the rung's severity; a drug no claim names has no claim
    to hang on, so its finding names none and goes to the banner (§9.7).

    Omission (D17):
    - an omitted allergy is still read from the raw text, so the check fires.
    - an omitted new drug is still read through new_prescriptions(raw_text), so the check
      fires, at the banner.
    - an omitted continued home medication is not seen live: a CI-only gap, which
      must_preserve covers.
    """
    allergy_claim = {a: claim.id for claim in note.claims for a in extract_allergies(claim.text)}
    allergens = (extract_allergies(raw_text) | allergy_claim.keys()) - NO_ALLERGY_STATEMENTS
    drugs = drug_mentions(note)
    in_note = {drug for drug, _ in drugs}
    drugs += [(drug, ()) for drug in sorted(new_prescriptions(raw_text) - in_note)]
    findings: list[Finding] = []
    for drug, drug_ids in drugs:
        for allergen in sorted(allergens):
            hit = contraindication(allergen, drug)
            if hit is None:
                continue
            severity, why = hit
            allergy_ids = (
                (allergy_claim[allergen],) if allergen in allergy_claim and drug_ids else ()
            )
            findings.append(
                Finding(
                    detail=f"{allergen} allergy on record; {drug}: {why}",
                    claim_ids=drug_ids + allergy_ids,
                    severity=severity,
                )
            )
    return findings


@register_check(name="new_prescription_preserved", severity=Severity.WARNING)
def check_new_prescription_preserved(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
) -> list[Finding]:
    """One finding per drug the raw text starts and no claim names (§8.4, L41).

    new_prescriptions(raw) − named(note), over every claim, grounded or not, whatever its
    section (invariant 5). A claim naming the drug at another status keeps it: the status is
    med_status_consistency's (D13, L156). The finding names no claim, since the drug is in
    none, so it goes to the banner (§9.7).
    """
    named = {drug for claim in note.claims for drug in named_drugs(claim.text)}
    return [
        Finding(detail=f"{drug}: started in the source, not the note", claim_ids=())
        for drug in sorted(new_prescriptions(raw_text) - named)
    ]


@register_check(name="quote_informativeness", severity=Severity.WARNING)
def check_quote_informativeness(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
) -> list[Finding]:
    """One finding per claim whose source span says too little to ground it (§8.4, D15).

    A span is informative with config.min_quote_content_tokens content tokens (L161), or
    when it states NKDA or NKA, a statement in one word (L158), or when each of its content
    tokens is a word stating its finding absent ("afebrile", L174). A bare lexicon name is
    not: "pain" grounds wherever a source mentions pain (§6.5). The check reads the span,
    what the claim cites, not the model's quote (L159); a claim with no span is skipped
    (§8.4).
    """
    minimum = config.min_quote_content_tokens
    findings: list[Finding] = []
    for claim in note.claims:
        span = span_text(claim, raw_text)
        if span is None or extract_allergies(span) & NO_ALLERGY_STATEMENTS:
            continue
        tokens = content_tokens(span)
        if tokens and set(tokens) <= ABSENCE_WORDS:
            continue
        count = len(tokens)
        if count < minimum:
            findings.append(
                Finding(
                    detail=f"content tokens in its span: {count}, fewer than {minimum}",
                    claim_ids=(claim.id,),
                )
            )
    return findings


@register_check(name="empty_note_on_clinical_input", severity=Severity.WARNING)
def check_empty_note_on_clinical_input(
    note: SOAPNote, raw_text: str, case: EvalCase | None = None, *, config: ChecksConfig
) -> list[Finding]:
    """One finding when the note holds no claim and the raw text names an entity (§8.4, L55).

    An entity is what five extractors read from the raw text (L164): a drug it names at any
    status, an allergy or D10's statements, a finding of either polarity, and a diagnosis
    asserted or excluded. The finding names them in name order and no claim, so it goes to
    the banner (§9.7). A raw text naming nothing the lexicons list reads as non-clinical
    (§8.8, L165).
    """
    if note.claims:
        return []
    entities = {
        *named_drugs(raw_text),
        *extract_allergies(raw_text),
        *extract_findings(raw_text),
        *extract_diagnoses(raw_text),
        *extract_excluded_diagnoses(raw_text),
    }
    if not entities:
        return []
    names = ", ".join(sorted(entities))
    return [Finding(detail=f"no claims; the source names: {names}", claim_ids=())]


# --- reference labels (§8.4 point 4; L214-L219) ---------------------------------------------

# What a label reads as, by kind: an allergen nothing more, a drug its status, a dose the
# dose, a finding its polarity, a diagnosis its certainty or its exclusion (L214)
type LabelValue = MedStatus | Dose | bool | _Reading | None


def _one[T](readings: Mapping[str, set[T]]) -> tuple[str, T] | None:
    """The one key and its one value, or None for any other count of either."""
    if len(readings) != 1:
        return None
    ((key, values),) = readings.items()
    return (key, next(iter(values))) if len(values) == 1 else None


def _allergen(text: str) -> str | None:
    allergens = extract_allergies(text)
    return next(iter(allergens)) if len(allergens) == 1 else None


def _diagnosis(text: str) -> tuple[str, _Reading] | None:
    """One diagnosis at one certainty, or one excluded: never both, never two."""
    readings = _diagnosis_readings(text)
    if len(readings) != 1:
        return None
    ((name, (certainties, excluded)),) = readings.items()
    return (name, (certainties, excluded)) if len(certainties) + excluded == 1 else None


def read_label(item: PreserveItem | NotAddItem) -> tuple[str, LabelValue] | None:
    """The one entity a label's text names and the one reading it states, else None (L214)."""
    match item.kind:
        case "allergy":
            allergen = _allergen(item.text)
            return None if allergen is None else (allergen, None)
        case "medication":
            return _one(extract_med_status(item.text))
        case "dose":
            return _one(extract_doses(item.text))
        case "finding":
            return _one(extract_findings(item.text))
        case "diagnosis":
            return _diagnosis(item.text)


def label_problem(item: PreserveItem | NotAddItem) -> str | None:
    """Why no check can read this label, or None (L219). Never quotes the label's text."""
    if isinstance(item, PreserveItem) and item.kind != "finding" and not item.present:
        return "present applies to findings"
    reading = read_label(item)
    if reading is None:
        return f"doesn't read as one {item.kind} with one reading"
    _, value = reading
    if isinstance(item, PreserveItem):
        if item.kind == "finding" and value is not item.present:
            said = "present" if item.present else "absent"
            return f"labeled {said}, but its text doesn't read it {said}"
        return None
    match item.kind:  # a must_not_add label names what a note would add (L36)
        case "medication":
            positive = value == "active"
        case "finding":
            positive = value is True
        case "diagnosis":
            positive = isinstance(value, tuple) and not value[1]
    return None if positive else "doesn't read as a positive mention"


def _unreadable(item: PreserveItem | NotAddItem) -> NoReturn:
    raise ValueError(f"unreadable {item.kind} label: {label_problem(item)}")


def _diagnosis_miss(label: _Reading, note: _Reading) -> Severity | None:
    """How far a whole note's reading of a diagnosis departs from its label's (L216).

    Strongest certainty against strongest, since a note records a course; an exclusion
    label is kept by the exclusion, and a rule-out ending in it keeps it.
    """
    (wanted, excluded), (said, note_excludes) = label, note
    if excluded:
        if said & _CONTRADICTS_AN_EXCLUSION or not (said or note_excludes):
            return Severity.CRITICAL  # asserted against the exclusion, or never named
        return None if note_excludes else Severity.WARNING  # reopened
    if note_excludes or not said:
        return Severity.CRITICAL  # an exclusion the source doesn't make (L140), or dropped
    if _strongest(said) < _strongest(wanted):
        return Severity.CRITICAL  # upgrade
    if _strongest(said) > _strongest(wanted):
        return Severity.WARNING  # downgrade
    return None


def preserve_miss(item: PreserveItem, texts: Sequence[str]) -> Severity | None:
    """None when the texts keep the label's reading, else how badly they miss it (L215-L217).

    Each text is read whole and the readings are pooled, so a course across claims keeps
    every reading in it. ValueError for a label no check can read (L219).
    """
    if label_problem(item) is not None:
        _unreadable(item)
    match item.kind:
        case "allergy":
            allergen = _allergen(item.text) or _unreadable(item)
            if any(allergen in extract_allergies(t) for t in texts):
                return None
            return Severity.WARNING if allergen in NO_ALLERGY_STATEMENTS else Severity.CRITICAL
        case "medication":
            drug, status = _one(extract_med_status(item.text)) or _unreadable(item)
            kept = any(status in extract_med_status(t).get(drug, set()) for t in texts)
            return None if kept else Severity.CRITICAL
        case "dose":
            drug, dose = _one(extract_doses(item.text)) or _unreadable(item)
            kept = any(_matches(d, dose) for t in texts for d in extract_doses(t).get(drug, set()))
            return None if kept else Severity.WARNING
        case "finding":
            finding, polarity = _one(extract_findings(item.text)) or _unreadable(item)
            kept = any(polarity in extract_findings(t).get(finding, set()) for t in texts)
            return None if kept else Severity.CRITICAL
        case "diagnosis":
            name, wanted = _diagnosis(item.text) or _unreadable(item)
            readings = [_diagnosis_readings(t).get(name, (set(), False)) for t in texts]
            said: set[Certainty] = set().union(*(certainties for certainties, _ in readings))
            return _diagnosis_miss(wanted, (said, any(excluded for _, excluded in readings)))


def adds(item: NotAddItem, text: str) -> bool:
    """Whether text reads the label's entity as a positive mention: a drug active, a finding
    present, a diagnosis at any certainty (L36, L214). ValueError for an unreadable label."""
    if label_problem(item) is not None:
        _unreadable(item)
    name, _ = read_label(item) or _unreadable(item)
    match item.kind:
        case "medication":
            return name in extract_drugs(text)
        case "finding":
            return True in extract_findings(text).get(name, set())
        case "diagnosis":
            return name in extract_diagnoses(text)
