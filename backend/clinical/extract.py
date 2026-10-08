"""Clinical extraction: plain text to sets (spec §7).

Imports only lexicons.py (invariant 13): extraction takes plain strings and knows nothing of
the spine.

The scope engine is NegEx-shaped (L31), made exact by L121. Text is casefolded and split into
tokens: words, punctuation marks, and line breaks. Lexicon phrases are split the same way and
matched left to right, the longest first. A pre-negation cue governs the findings that start
within NEGATION_WINDOW words after it. A post-negation cue governs the finding immediately
before it, across punctuation that isn't a terminator; a cue in both classes is a post-cue
there and a pre-cue anywhere else. A terminator closes the window.
"""

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence

from backend.clinical.lexicons import (
    FINDING_NEG_POST,
    FINDING_NEG_PRE,
    FINDINGS,
    NEGATION_WINDOW,
    PSEUDO_NEGATIONS,
    TERMINATORS,
)

# A decimal number whole, so "38.5" ends no sentence; a word; a line break; one mark.
_TOKEN = re.compile(r"\d+(?:\.\d+)+|[^\W_]+|\n|[^\w\s]")

type _Phrases = Mapping[tuple[str, ...], str]


def _tokens(text: str) -> list[str]:
    """text, casefolded, as tokens. A carriage return reads as a line break."""
    return _TOKEN.findall(text.casefold().replace("\r", "\n"))


def _phrases(entries: Iterable[str]) -> dict[tuple[str, ...], str]:
    """Each lexicon entry under its tokens, so it matches the text as the text is split."""
    return {tuple(_tokens(entry)): entry for entry in entries}


_PSEUDO = _phrases(PSEUDO_NEGATIONS)
_TERMINATORS = _phrases(TERMINATORS)
_FINDINGS = _phrases(FINDINGS)
_NEG_PRE = _phrases(FINDING_NEG_PRE)
_NEG_POST = _phrases(FINDING_NEG_POST)


def _is_word(token: str) -> bool:
    return token[0].isalnum()


def _split(tokens: Sequence[str], tables: Sequence[_Phrases]) -> Iterator[tuple[str, ...]]:
    """tokens as phrases, left to right: the longest phrase a table holds, else one token."""
    most = max(len(phrase) for table in tables for phrase in table)
    i = 0
    while i < len(tokens):
        phrase: tuple[str, ...] = (tokens[i],)
        for n in range(most, 1, -1):
            if any(tuple(tokens[i : i + n]) in table for table in tables):
                phrase = tuple(tokens[i : i + n])
                break
        yield phrase
        i += len(phrase)


def _scope(text: str, entities: _Phrases, pre: _Phrases, post: _Phrases) -> list[tuple[str, bool]]:
    """Each entity mention in text, in order, and whether a cue governs it (L31, L121)."""
    mentions: list[tuple[str, bool]] = []
    window = 0  # the words an open pre-cue still governs
    before: int | None = None  # the mention immediately before, past punctuation marks
    for phrase in _split(_tokens(text), (_PSEUDO, _TERMINATORS, entities, pre, post)):
        words = sum(map(_is_word, phrase))
        in_window = window > 0
        window = max(window - words, 0)
        if phrase in _TERMINATORS:
            window = 0
        elif phrase in post and before is not None:  # tested ahead of pre, per L121
            mentions[before] = (mentions[before][0], True)
        elif phrase in pre:
            window = NEGATION_WINDOW
        elif phrase in entities:
            mentions.append((entities[phrase], in_window))
        # adjacency: a mention opens it, and a word or a terminator ends it
        if phrase in entities:
            before = len(mentions) - 1
        elif words or phrase in _TERMINATORS:
            before = None
    return mentions


def extract_findings(text: str) -> dict[str, set[bool]]:
    """finding -> polarities asserted. "denies chest pain" -> {"chest pain": {False}}.

    Scoped negation (L31, L121). A set, so a mixed statement keeps both (L33).
    """
    polarities: dict[str, set[bool]] = {}
    for finding, negated in _scope(text, _FINDINGS, _NEG_PRE, _NEG_POST):
        polarities.setdefault(finding, set()).add(not negated)
    return polarities
