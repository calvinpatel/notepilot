"""Grounding: proves each claim's quote is in the raw text (spec §6).

Pure and deterministic: no LLM calls (invariant 2). ground() runs every claim down the
ladder and stamps its id (§6.3). Tier 1 is an exact substring. Tier 2 is an exact match in
normalized space. Tier 3 is a fuzzy alignment in normalized space, kept at or above
fuzzy_score_cutoff when every number in the quote is in the span, and flags the claim
PARAPHRASED. Anything else is UNSUPPORTED (Tier 4), with its score kept when an alignment
ran (L8). An ungroundable claim is a result, not an exception (invariant 4).

Comparing in normalized space shifts every index, so NormalizedText keeps, for each
normalized character, the index of the original character that produced it (§6.2).
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

from rapidfuzz import fuzz

from backend.config import settings
from backend.schemas import ClaimDraft, ClinicalClaim, SafetyFlag, SOAPNote, SOAPNoteDraft

# Folded before comparison. The micro sign U+00B5 and Greek mu U+03BC look identical, and
# a dose unit may be written with either (L26).
PUNCT_MAP: Mapping[str, str] = {
    "\u201c": '"',  # curly double quotes
    "\u201d": '"',
    "\u2018": "'",  # curly single quotes
    "\u2019": "'",
    "\u2013": "-",  # en and em dashes
    "\u2014": "-",
    "\u00b5": "\u03bc",  # micro sign -> Greek mu
}


@dataclass(frozen=True)
class NormalizedText:
    text: str
    index_map: list[int]  # normalized index -> original index

    @classmethod
    def of(cls, text: str) -> Self:
        """Lowercase, collapse whitespace runs, and fold PUNCT_MAP, keeping the map."""
        out: list[str] = []
        index_map: list[int] = []
        prev_space = False
        for i, ch in enumerate(text):
            if ch.isspace():
                if not prev_space:
                    out.append(" ")
                    index_map.append(i)
                prev_space = True
                continue
            # L26: lower() can return more than one character (U+0130 returns two), so each
            # character it returns gets its own map entry
            for c in PUNCT_MAP.get(ch, ch).lower():
                out.append(c)
                index_map.append(i)
            prev_space = False
        return cls("".join(out), index_map)

    def to_original(self, n_start: int, n_end: int) -> tuple[int, int]:
        """Half-open normalized [n_start, n_end) -> half-open original span (§6.2).

        The end is the last matched character's original index plus one. index_map[n_end]
        may not exist, and when it does it can point past collapsed whitespace. An empty or
        reversed slice raises ValueError (L109): it has no last character, and at 0 the
        lookup would wrap to the end of the text.
        """
        if n_start >= n_end:
            raise ValueError(f"empty normalized slice [{n_start}, {n_end})")
        return self.index_map[n_start], self.index_map[n_end - 1] + 1


# --- the ladder (§6.1, §6.3) -----------------------------------------------------

_DIGITS = re.compile(r"\d+(?:[./]\d+)?")  # 120, 0.5, 190/110, 2.5


def _numbers_match(quote: str, span_text: str) -> bool:
    """Fuzzy may forgive letters, never digits: every number in the quote is in the span."""
    span_numbers = set(_DIGITS.findall(span_text))
    return all(n in span_numbers for n in _DIGITS.findall(quote))


def _snap(raw_text: str, start: int, end: int) -> tuple[int, int]:
    """Widen a span to whole words (L108): an alignment window can start or end mid-word."""
    while start > 0 and raw_text[start - 1].isalnum() and raw_text[start].isalnum():
        start -= 1
    while end < len(raw_text) and raw_text[end - 1].isalnum() and raw_text[end].isalnum():
        end += 1
    return start, end


def ground_claim(
    draft: ClaimDraft, raw_text: str, norm: NormalizedText, *, claim_id: int
) -> ClinicalClaim:
    """One claim down the ladder (§6.3). norm is NormalizedText.of(raw_text)."""
    quote = draft.source_quote  # stripped and non-blank at the boundary (L25, L106)
    base = draft.model_dump() | {"id": claim_id}

    idx = raw_text.find(quote)  # Tier 1
    if idx != -1:
        return ClinicalClaim(**base, source_span=(idx, idx + len(quote)))

    nq = NormalizedText.of(quote).text
    n_idx = norm.text.find(nq)  # Tier 2
    if n_idx != -1:
        return ClinicalClaim(**base, source_span=norm.to_original(n_idx, n_idx + len(nq)))

    # Tier 3, in normalized space (L27): src_start and src_end index norm.text
    align = fuzz.partial_ratio_alignment(norm.text, nq)
    if align is not None and align.src_end > align.src_start:
        start, end = _snap(raw_text, *norm.to_original(align.src_start, align.src_end))
        if align.score >= settings.fuzzy_score_cutoff and _numbers_match(
            quote, raw_text[start:end]
        ):
            return ClinicalClaim(
                **base,
                source_span=(start, end),
                grounding_score=align.score,
                flags=(SafetyFlag.PARAPHRASED,),
            )
        # Tier 4, score kept: near-misses and numeric demotions are the tuning data (L8)
        return ClinicalClaim(**base, grounding_score=align.score, flags=(SafetyFlag.UNSUPPORTED,))
    return ClinicalClaim(**base, flags=(SafetyFlag.UNSUPPORTED,))  # Tier 4: nothing aligned


def ground(draft: SOAPNoteDraft, raw_text: str) -> SOAPNote:
    """Ground every claim, stamping ids in draft order (§6.3)."""
    norm = NormalizedText.of(raw_text)  # once per note
    return SOAPNote(
        claims=tuple(
            ground_claim(c, raw_text, norm, claim_id=i) for i, c in enumerate(draft.claims)
        )
    )
