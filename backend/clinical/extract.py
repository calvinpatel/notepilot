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

A finding sees one class of cue, negation. A drug sees three at once: negation, stop, and
start (L124, L125).
"""

import re
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from typing import Literal

from backend.clinical.lexicons import (
    BRAND_TO_GENERIC,
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

MedStatus = Literal["active", "stopped"]

# A decimal number whole, so "38.5" ends no sentence; a word; a line break; one mark.
_TOKEN = re.compile(r"\d+(?:\.\d+)+|[^\W_]+|\n|[^\w\s]")

type _Phrase = tuple[str, ...]
type _Label = Literal["negated", "stopped", "started"]
type _Cues = Mapping[_Phrase, _Label]


def _tokens(text: str) -> list[str]:
    """text, casefolded, as tokens.

    A carriage return reads as a line break. An underscore, like whitespace, only separates
    words (L123).
    """
    return _TOKEN.findall(text.casefold().replace("\r", "\n"))


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
# every name a listed drug is charted by, under the generic it means (L126)
_DRUGS = _phrases(GENERIC_DRUGS) | {
    tuple(_tokens(name)): drug for name, drug in BRAND_TO_GENERIC.items()
}
_DRUG_PRE = _NEG_PRE | _cues("stopped", MED_STOP_CUES) | _cues("started", MED_START_CUES)
_DRUG_POST = _NEG_POST | _cues("stopped", MED_STOP_POST) | _cues("started", MED_START_POST)


def _is_word(token: str) -> bool:
    return token[0].isalnum()


def _split(tokens: Sequence[str], tables: Sequence[Collection[_Phrase]]) -> Iterator[_Phrase]:
    """tokens as phrases, left to right: the longest phrase a table holds, else one token."""
    most = max(len(phrase) for table in tables for phrase in table)
    i = 0
    while i < len(tokens):
        phrase: _Phrase = (tokens[i],)
        for n in range(most, 1, -1):
            if any(tuple(tokens[i : i + n]) in table for table in tables):
                phrase = tuple(tokens[i : i + n])
                break
        yield phrase
        i += len(phrase)


def _scope(
    text: str, entities: Mapping[_Phrase, str], pre: _Cues, post: _Cues
) -> list[tuple[str, _Label | None]]:
    """Each entity mention in text, in order, with the label of the cue that governs it, or
    None if none does (L31, L121, L122, L124)."""
    mentions: list[tuple[str, _Label | None]] = []
    window = 0  # the words the open pre-cue still governs
    label: _Label | None = None  # the open pre-cue's class
    before: int | None = None  # the mention immediately before, past any mark but a comma
    for phrase in _split(_tokens(text), (_PSEUDO, _TERMINATORS, entities, pre, post)):
        words = sum(map(_is_word, phrase))
        in_window = window > 0
        window = max(window - words, 0)
        if phrase in _TERMINATORS:
            window = 0
        elif phrase in post and before is not None:  # tested ahead of pre, per L121
            mentions[before] = (mentions[before][0], post[phrase])
        elif phrase in pre:
            window, label = NEGATION_WINDOW, pre[phrase]
        elif phrase in entities:
            mentions.append((entities[phrase], label if in_window else None))
        # adjacency: a mention opens it; a word, a terminator, or a comma ends it (L122)
        if phrase in entities:
            before = len(mentions) - 1
        elif words or phrase in _TERMINATORS or phrase == (",",):
            before = None
    return mentions


# what each label asserts: a started drug is active, and a negated one isn't taken (L124)
_STATUS: Mapping[_Label | None, MedStatus] = {
    None: "active",
    "started": "active",
    "stopped": "stopped",
    "negated": "stopped",
}


def extract_drugs(text: str) -> set[str]:
    """Generic names mentioned as active, brand->generic (L126): each drug with an active
    mention. Negated and stopped mentions are not active ones."""
    return {drug for drug, statuses in extract_med_status(text).items() if "active" in statuses}


def extract_med_status(text: str) -> dict[str, set[MedStatus]]:
    """drug -> the statuses asserted for it (D13).

    "continue apixaban" -> {"active"}; "discontinue apixaban" -> {"stopped"}. A negated
    mention is stopped: "not on apixaban" asserts the drug isn't taken (L124).
    """
    statuses: dict[str, set[MedStatus]] = {}
    for drug, label in _scope(text, _DRUGS, _DRUG_PRE, _DRUG_POST):
        statuses.setdefault(drug, set()).add(_STATUS[label])
    return statuses


def new_prescriptions(text: str) -> set[str]:
    """Drugs started at this visit: the mentions a start cue governs, before or after the drug
    (L41, L125). "mom takes metformin" and "tried ibuprofen last year" name no start."""
    mentions = _scope(text, _DRUGS, _DRUG_PRE, _DRUG_POST)
    return {drug for drug, label in mentions if label == "started"}


def extract_findings(text: str) -> dict[str, set[bool]]:
    """finding -> polarities asserted. "denies chest pain" -> {"chest pain": {False}}.

    Scoped negation (L31, L121, L122). A set, so a mixed statement keeps both (L33).
    """
    polarities: dict[str, set[bool]] = {}
    for finding, label in _scope(text, _FINDINGS, _NEG_PRE, _NEG_POST):
        polarities.setdefault(finding, set()).add(label is None)
    return polarities
