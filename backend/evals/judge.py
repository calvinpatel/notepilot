"""The Judge protocol: what evals/ needs from an entailment judge (spec §8.2; L17, L111).

A domain interface: evals/ declares it, so evals/ imports no vendor client (invariant 1).
"""

from collections.abc import Sequence
from typing import Protocol

from backend.schemas import TokenUsage


class Judge(Protocol):
    usage: TokenUsage  # what this judge's calls have cost (L7)

    async def entailment(self, pairs: Sequence[tuple[str, str]]) -> list[bool]:
        """One verdict per (text, span) pair, in order: is the text entailed by the span?"""
        ...
