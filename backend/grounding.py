"""Grounding's string mechanics (spec §6).

Pure and deterministic: no LLM calls (invariant 2). Comparing in normalized space shifts
every index, so NormalizedText keeps, for each normalized character, the index of the
original character that produced it (§6.2).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

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
        may not exist, and when it does it can point past collapsed whitespace.
        """
        return self.index_map[n_start], self.index_map[n_end - 1] + 1
