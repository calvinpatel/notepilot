"""Clinical extraction: plain text to sets (spec §7).

Imports only lexicons.py (invariant 13): extraction takes plain strings and knows nothing of
the spine.

The scope engine is NegEx-shaped (L31), made exact by L121 and L122. Text is casefolded and
split into tokens: words, punctuation marks, and line breaks. Lexicon phrases are split the
same way and matched left to right, the longest first. Each cue carries its class as a label
(L124). A pre-cue governs the mentions that start within NEGATION_WINDOW words after it, and a
new pre-cue of any class replaces the open window. A post-cue governs the mention immediately
before it, across any mark but a comma or a terminator; a cue in both a pre and a post table
is a post-cue there and a pre-cue anywhere else. A terminator closes the window.

A finding sees one class of cue, negation. A drug sees four at once: negation, stop, start, and
allergy (L124, L125, L128). Allergy context reaches further than the others (L128): a header at
a line's start opens a section, and an allergy post-cue reaches back over a list. A diagnosis
sees negation and certainty, and a differential cue ("vs") governs both its sides (L135).

Doses are read by a grammar over the same tokens (L131, L133): a number and a unit after a
drug, in the drug's sentence, and the frequency charted after it.

Dose, MedStatus, and Certainty are extraction's result types. They live here and evals imports
them from here, since clinical/ may not import the spine (§13's third exception, L132).
"""

import re
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from typing import Literal, NamedTuple

from backend.clinical.lexicons import (
    ALLERGY_ALIASES,
    ALLERGY_CUES,
    ALLERGY_POST,
    BRAND_TO_GENERIC,
    CERTAINTY_CUES,
    CERTAINTY_POST,
    DIAGNOSES,
    DIAGNOSIS_ALIASES,
    DIFFERENTIAL_CUES,
    DOSE_FREQUENCIES,
    DOSE_UNITS,
    FINDING_NEG_POST,
    FINDING_NEG_PRE,
    FINDINGS,
    GENERIC_DRUGS,
    MED_START_CUES,
    MED_START_POST,
    MED_STOP_CUES,
    MED_STOP_POST,
    NEGATION_WINDOW,
    PSEUDO_NEGATIONS,
    TERMINATORS,
)


class Dose(NamedTuple):
    value: float  # parsed, so "500mg TID" == "500 mg tid" (L33)
    unit: str  # canonical: "mg", "μg" (folded), "ml" ...
    freq: str | None  # canonical: "tid", "bid", "daily" ...


MedStatus = Literal["active", "stopped"]
Certainty = Literal["definite", "probable", "possible", "rule_out"]  # strongest first

# A decimal number whole, so "38.5" ends no sentence; a word; a line break; one mark.
_TOKEN = re.compile(r"\d+(?:\.\d+)+|[^\W_]+|\n|[^\w\s]")

type _Phrase = tuple[str, ...]
type _Label = Literal[
    "negated", "stopped", "started", "allergy", "probable", "possible", "rule_out"
]
type _Cues = Mapping[_Phrase, _Label]


def _tokens(text: str) -> list[str]:
    """text, casefolded, as tokens.

    A carriage return, alone or before a line feed, reads as one line break (L128). An
    underscore, like whitespace, only separates words (L123).
    """
    return _TOKEN.findall(text.casefold().replace("\r\n", "\n").replace("\r", "\n"))


def _phrases(entries: Iterable[str]) -> dict[_Phrase, str]:
    """Each lexicon entry under its tokens, so it matches the text as the text is split."""
    return {tuple(_tokens(entry)): entry for entry in entries}


def _cues(label: _Label, entries: Iterable[str]) -> dict[_Phrase, _Label]:
    """Each cue under its tokens, labeled with its class (L124)."""
    return {phrase: label for phrase in _phrases(entries)}


_PSEUDO = _phrases(PSEUDO_NEGATIONS)
_TERMINATORS = _phrases(TERMINATORS)
_FINDINGS = _phrases(FINDINGS)
_NEG_PRE = _cues("negated", FINDING_NEG_PRE)
_NEG_POST = _cues("negated", FINDING_NEG_POST)
# every name a listed drug is charted by, under the generic it means (L126), and every
# allergen name under the class or statement it means (L129)
_DRUGS = _phrases(GENERIC_DRUGS) | {
    tuple(_tokens(name)): drug for name, drug in BRAND_TO_GENERIC.items()
}
_NAMES = _DRUGS | {tuple(_tokens(name)): key for name, key in ALLERGY_ALIASES.items()}
_DRUG_PRE = (
    _NEG_PRE
    | _cues("stopped", MED_STOP_CUES)
    | _cues("started", MED_START_CUES)
    | _cues("allergy", ALLERGY_CUES)
)
_DRUG_POST = (
    _NEG_POST
    | _cues("stopped", MED_STOP_POST)
    | _cues("started", MED_START_POST)
    | _cues("allergy", ALLERGY_POST)
)
# the statements of D10, allergy information that needs no allergy cue
_NO_ALLERGY = frozenset({"nkda", "nka"})
# what joins a list an allergy post-cue reaches back over (L128)
_JOINS = frozenset({(",",), ("and",), ("or",)})
# the label each certainty a lexicon names becomes; a value it lacks fails at import (L135)
_CERTAINTY: Mapping[str, _Label] = {
    "probable": "probable",
    "possible": "possible",
    "rule_out": "rule_out",
}


def _certainty_cues(table: Mapping[str, str]) -> dict[_Phrase, _Label]:
    """Each certainty cue under its tokens, labeled with the certainty it asserts (L135)."""
    return {tuple(_tokens(cue)): _CERTAINTY[certainty] for cue, certainty in table.items()}


_DIAGNOSES = _phrases(DIAGNOSES) | {
    tuple(_tokens(name)): diagnosis for name, diagnosis in DIAGNOSIS_ALIASES.items()
}
_DX_PRE = _NEG_PRE | _certainty_cues(CERTAINTY_CUES)
_DX_POST = _NEG_POST | _certainty_cues(CERTAINTY_POST)
_DIFFERENTIAL = _certainty_cues(DIFFERENTIAL_CUES)
_NO_CUES: _Cues = {}
_UNITS = {tuple(_tokens(name)): unit for name, unit in DOSE_UNITS.items()}
_FREQUENCIES = {tuple(_tokens(name)): freq for name, freq in DOSE_FREQUENCIES.items()}
# a number, and any letters fused to it ("500mg"); a decimal is one token already (L121)
_NUMBER = re.compile(r"(\d+(?:\.\d+)?)([^\W\d_]*)")


def _is_word(token: str) -> bool:
    return token[0].isalnum()


def _split(
    tokens: Sequence[str], tables: Sequence[Collection[_Phrase]]
) -> Iterator[tuple[int, _Phrase]]:
    """tokens as phrases, left to right, each with its first token's index: the longest
    phrase a table holds, else one token."""
    most = max(len(phrase) for table in tables for phrase in table)
    i = 0
    while i < len(tokens):
        phrase: _Phrase = (tokens[i],)
        for n in range(most, 1, -1):
            if any(tuple(tokens[i : i + n]) in table for table in tables):
                phrase = tuple(tokens[i : i + n])
                break
        yield i, phrase
        i += len(phrase)


def _sections(
    tokens: Sequence[str],
    phrases: Sequence[tuple[int, _Phrase]],
    entities: Collection[_Phrase],
    pre: _Cues,
) -> set[int]:
    """The token indices inside an allergy section (L128).

    An allergy cue ending in a colon, at a line's start, opens a section. It runs to a blank
    line, or to the next header (up to three words and a colon, the first naming no entity)
    at a line's start or after a period.
    """
    starts = {
        i
        for i, phrase in phrases
        if pre.get(phrase) == "allergy" and phrase[-1] == ":" and (i == 0 or tokens[i - 1] == "\n")
    }
    if not starts:
        return set()
    at = dict(phrases)

    def header(j: int) -> bool:
        k = j
        while k < len(tokens) and k - j < 3 and _is_word(tokens[k]):
            k += 1
        return j < k < len(tokens) and tokens[k] == ":" and at.get(j) not in entities

    inside: set[int] = set()
    open_ = False
    for i, token in enumerate(tokens):
        if i in starts:
            open_ = True
        elif open_ and token == "\n" and tokens[i + 1 : i + 2] == ["\n"]:
            open_ = False
        elif open_ and token in ("\n", ".") and i + 1 not in starts and header(i + 1):
            open_ = False
        if open_:
            inside.add(i)
    return inside


def _scope(
    text: str,
    entities: Mapping[_Phrase, str],
    pre: _Cues,
    post: _Cues,
    differential: _Cues = _NO_CUES,
) -> list[tuple[str, _Label | None]]:
    """Each entity mention in text, in order, with the label of the cue that governs it, or
    None if none does (L31, L121, L122, L124, L128, L135)."""
    tokens = _tokens(text)
    phrases = list(_split(tokens, (_PSEUDO, _TERMINATORS, entities, pre, post, differential)))
    sections = _sections(tokens, phrases, entities, pre)
    mentions: list[tuple[str, _Label | None]] = []
    window = 0  # the words the open pre-cue still governs
    label: _Label | None = None  # the open pre-cue's class
    before: int | None = None  # the mention immediately before, past any mark but a comma
    run: list[int] = []  # the mentions a list joins, ending at `before` (L128)
    for i, phrase in phrases:
        words = sum(map(_is_word, phrase))
        in_window = window > 0
        window = max(window - words, 0)
        if phrase in _TERMINATORS:
            window = 0
        elif phrase in differential:  # both sides: the mention before, unless governed, and after
            if before is not None and mentions[before][1] is None:
                mentions[before] = (mentions[before][0], differential[phrase])
            window, label = NEGATION_WINDOW, differential[phrase]
        elif phrase in post and before is not None:  # tested ahead of pre, per L121
            reach = run if post[phrase] == "allergy" else [before]
            for m in reach:  # a list's earlier mentions only where no other cue governs
                if m == before or mentions[m][1] is None:
                    mentions[m] = (mentions[m][0], post[phrase])
        elif phrase in pre:
            window, label = NEGATION_WINDOW, pre[phrase]
        elif phrase in entities:
            governing = label if in_window else "allergy" if i in sections else None
            mentions.append((entities[phrase], governing))
        # adjacency: a mention opens it; a word, a terminator, or a comma ends it (L122). A
        # list's run survives a join and a mark, and ends where adjacency ends otherwise.
        if phrase in entities:
            before = len(mentions) - 1
            run.append(before)
        elif words or phrase in _TERMINATORS or phrase == (",",):
            before = None
            if phrase not in _JOINS:
                run = []
    return mentions


def _drug_mentions(text: str) -> list[tuple[str, _Label | None]]:
    """Each drug and allergen mention in text, with the label of the cue that governs it."""
    return _scope(text, _NAMES, _DRUG_PRE, _DRUG_POST)


# what each label asserts: a started drug is active and a negated one isn't taken (L124); an
# allergen asserts no status at all (L128), so "allergy" has no entry
_STATUS: Mapping[_Label | None, MedStatus] = {
    None: "active",
    "started": "active",
    "stopped": "stopped",
    "negated": "stopped",
}


def extract_drugs(text: str) -> set[str]:
    """Generic names mentioned as active, brand->generic (L126): each drug with an active
    mention. Negated and stopped mentions are not active ones, and an allergen is no
    medication (L128)."""
    return {drug for drug, statuses in extract_med_status(text).items() if "active" in statuses}


def extract_med_status(text: str) -> dict[str, set[MedStatus]]:
    """drug -> the statuses asserted for it (D13).

    "continue apixaban" -> {"active"}; "discontinue apixaban" -> {"stopped"}. A negated
    mention is stopped: "not on apixaban" asserts the drug isn't taken (L124). A mention in
    allergy context asserts no status (L128).
    """
    statuses: dict[str, set[MedStatus]] = {}
    for drug, label in _drug_mentions(text):
        if drug in GENERIC_DRUGS and label in _STATUS:
            statuses.setdefault(drug, set()).add(_STATUS[label])
    return statuses


def new_prescriptions(text: str) -> set[str]:
    """Drugs started at this visit: the mentions a start cue governs, before or after the drug
    (L41, L125). "mom takes metformin" and "tried ibuprofen last year" name no start."""
    mentions = _drug_mentions(text)
    return {drug for drug, label in mentions if label == "started" and drug in GENERIC_DRUGS}


def extract_allergies(text: str) -> set[str]:
    """Allergens, normalized: brand->generic, aliases resolved ("PCN" -> "penicillin") (L30).

    A key is a generic drug ("amoxicillin"), a class ("penicillin", "sulfa", "nsaid"),
    "nkda", or "nka" (D10). A mention is an allergen where allergy context governs it
    (L128); "nkda" and "nka" are allergy statements wherever they aren't negated (L129).
    """
    return {
        name
        for name, label in _drug_mentions(text)
        if label == "allergy" or (name in _NO_ALLERGY and label != "negated")
    }


def _number_at(phrases: Sequence[_Phrase], i: int) -> tuple[str, str | None, int] | None:
    """The number that starts at phrases[i]: its digits, the unit fused to it or written after
    it (None if neither), and how many phrases it spans; None if no number starts there. A
    thousands comma joins, with or without a unit fused to the last group ("1,000mg")."""
    number = _NUMBER.fullmatch(phrases[i][0]) if len(phrases[i]) == 1 else None
    if number is None:
        return None
    digits, fused = number.groups()
    width = 1
    while not fused and (group := _thousands(phrases[i + width : i + width + 2])) is not None:
        digits += group.group(1)
        fused = group.group(2)
        width += 2
    if fused:
        return digits, _UNITS.get((fused,)), width
    unit = _UNITS.get(phrases[i + width]) if i + width < len(phrases) else None
    return digits, unit, width if unit is None else width + 1


def _thousands(pair: Sequence[_Phrase]) -> re.Match[str] | None:
    """After a thousands comma, its three digits and any letters fused to them; else None."""
    if len(pair) != 2 or pair[0] != (",",) or len(pair[1]) != 1:
        return None
    group = _NUMBER.fullmatch(pair[1][0])
    return (
        group
        if group is not None and len(group.group(1)) == 3 and group.group(1).isdecimal()
        else None
    )


def _dose_at(phrases: Sequence[_Phrase], i: int) -> tuple[float, str, int] | None:
    """The dose that starts at phrases[i] (L133): its value, its unit, and how many phrases it
    spans; None if none starts there. Neither number of a range is a dose: a hyphen joins one
    whether or not its numbers carry units ("5-10 mg", "5mg-10mg"), and "to" joins one only
    after a number without a unit ("5 to 10 mg"), since "from 500 mg to 1000 mg" is a
    titration."""
    number = _number_at(phrases, i)
    if number is None:
        return None
    digits, unit, width = number
    if unit is None:
        return None
    first = _number_at(phrases, i - 2) if i >= 2 else None
    ends = i >= 2 and (
        (phrases[i - 1] == ("-",) and (first is not None or phrases[i - 2] in _UNITS))
        or (phrases[i - 1] == ("to",) and first is not None and first[1] is None)
    )
    second = _number_at(phrases, i + width + 1) if i + width + 1 < len(phrases) else None
    starts = (
        phrases[i + width : i + width + 1] == [("-",)]
        and second is not None
        and second[1] is not None
    )
    if ends or starts:
        return None
    return float(digits), unit, width


def extract_doses(text: str) -> dict[str, set[Dose]]:
    """drug -> parsed doses. A set, so a titration keeps both (D1, L33).

    A dose belongs to the most recent drug before it in the same sentence, whatever that
    mention's status, and takes the first frequency charted after its unit before the next
    dose, drug, or terminator; a prn yields to an interval in that reach (L133).
    """
    phrases = [p for _, p in _split(_tokens(text), (_TERMINATORS, _NAMES, _UNITS, _FREQUENCIES))]
    doses: dict[str, set[Dose]] = {}
    drug: str | None = None  # the most recent drug in this sentence
    pending: tuple[str, float, str] | None = None  # a dose still reaching for its frequency
    prn = False  # a prn charted in the pending dose's reach

    def settle(freq: str | None) -> None:
        nonlocal pending, prn
        if pending is not None:
            name, value, unit = pending
            doses.setdefault(name, set()).add(Dose(value, unit, freq or ("prn" if prn else None)))
        pending, prn = None, False

    i = 0
    while i < len(phrases):
        phrase = phrases[i]
        if phrase in _FREQUENCIES and pending is not None:
            if _FREQUENCIES[phrase] == "prn":
                prn = True
            else:
                settle(_FREQUENCIES[phrase])
        elif phrase in _TERMINATORS:
            settle(None)
            drug = None
        elif _NAMES.get(phrase) in GENERIC_DRUGS:
            settle(None)
            drug = _NAMES[phrase]
        elif (dose := _dose_at(phrases, i)) is not None:
            settle(None)
            value, unit, width = dose
            pending = None if drug is None else (drug, value, unit)
            i += width
            continue
        i += 1
    settle(None)
    return doses


# what each label asserts of a diagnosis: no cue is a definite one, and a negated one isn't
# asserted at all, so "negated" has no entry (L135)
_ASSERTED: Mapping[_Label | None, Certainty] = {
    None: "definite",
    "probable": "probable",
    "possible": "possible",
    "rule_out": "rule_out",
}


def extract_diagnoses(text: str) -> dict[str, set[Certainty]]:
    """diagnosis -> certainties asserted (D12). "r/o PE" -> {"pulmonary embolism": {"rule_out"}}.

    Names resolve to their canonical diagnosis (L134). A diagnosis no cue governs is definite,
    and a negated one ("PE ruled out") isn't asserted (L135).
    """
    certainties: dict[str, set[Certainty]] = {}
    for diagnosis, label in _scope(text, _DIAGNOSES, _DX_PRE, _DX_POST, _DIFFERENTIAL):
        if label in _ASSERTED:
            certainties.setdefault(diagnosis, set()).add(_ASSERTED[label])
    return certainties


def extract_findings(text: str) -> dict[str, set[bool]]:
    """finding -> polarities asserted. "denies chest pain" -> {"chest pain": {False}}.

    Scoped negation (L31, L121, L122). A set, so a mixed statement keeps both (L33).
    """
    polarities: dict[str, set[bool]] = {}
    for finding, label in _scope(text, _FINDINGS, _NEG_PRE, _NEG_POST):
        polarities.setdefault(finding, set()).add(label is None)
    return polarities
