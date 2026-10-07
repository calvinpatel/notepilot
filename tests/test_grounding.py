"""Pins NormalizedText, its index map, and rapidfuzz's alignment coordinates.

Spec §6.2, §6.3, §6.5, §11; L26, L27, L62.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from rapidfuzz import fuzz

from backend.grounding import PUNCT_MAP, NormalizedText

# Non-ASCII on purpose (L26): U+0130, whose lower() returns two characters, the PUNCT_MAP
# keys, and several kinds of whitespace, drawn by name beside arbitrary characters. Texts are
# joined from lists because text() merges its alphabet into one character set, where a
# handful of named characters are rarely drawn.
_NAMED = ["\u0130", *PUNCT_MAP, " ", "\t", "\n", "\u00a0", "\u2028", "\u3000", "\x1c"]
_CHAR = st.one_of(st.sampled_from(_NAMED), st.characters())


def _texts(*, min_size: int = 0) -> st.SearchStrategy[str]:
    return st.lists(_CHAR, min_size=min_size).map("".join)


def _normalizes_to(text: str, i: int) -> str:
    """What original character i contributes to the normalized text (§6.2, L62)."""
    ch = text[i]
    if ch.isspace():
        return "" if i > 0 and text[i - 1].isspace() else " "
    return PUNCT_MAP.get(ch, ch).lower()


# --- the worked examples (§6.2, §6.5) -------------------------------------------


def test_whitespace_runs_collapse_and_the_map_skips_them() -> None:
    norm = NormalizedText.of("Pt  denies\tCP")
    assert norm.text == "pt denies cp"
    assert norm.index_map == [0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12]


def test_to_original_ends_after_the_last_matched_character() -> None:
    raw = "Pt  denies\tCP"
    norm = NormalizedText.of(raw)
    start, end = norm.to_original(3, 12)  # "denies cp", to the end of the normalized text
    assert (start, end) == (4, 13)
    assert raw[start:end] == "denies\tCP"


def test_punctuation_variants_and_the_micro_sign_fold() -> None:
    raw = "\u201cA\u201d \u2018b\u2019 \u2013 \u2014 5 \u00b5g"
    assert NormalizedText.of(raw).text == "\"a\" 'b' - - 5 \u03bcg"


def test_a_two_character_lowercase_maps_both_characters_to_its_original() -> None:
    norm = NormalizedText.of("\u0130V")
    assert norm.text == "i\u0307v"
    assert norm.index_map == [0, 0, 1]


def test_a_match_ending_inside_an_expansion_spans_the_whole_original_character() -> None:
    # "i" is the first of the two characters U+0130 lowercases to
    assert NormalizedText.of("\u0130V").to_original(0, 1) == (0, 1)


# --- the properties (§11; L26, L62) --------------------------------------------


def test_hypothesis_profile_is_deterministic() -> None:
    # conftest's profile: the free tier is deterministic (invariant 20)
    assert settings().derandomize is True
    assert settings().deadline is None


@given(_texts())
def test_each_original_character_maps_to_what_it_normalizes_to(text: str) -> None:
    # L62: stated per original character, so a lower() that returns two can't break it
    norm = NormalizedText.of(text)
    assert len(norm.index_map) == len(norm.text)
    assert norm.index_map == sorted(norm.index_map)  # normalized order is original order
    contributed = [""] * len(text)
    for c, i in zip(norm.text, norm.index_map, strict=True):
        contributed[i] += c
    assert contributed == [_normalizes_to(text, i) for i in range(len(text))]


@given(st.data())
def test_to_original_covers_exactly_the_slice(data: st.DataObject) -> None:
    text = data.draw(_texts(min_size=1), label="text")
    norm = NormalizedText.of(text)
    a = data.draw(st.integers(0, len(norm.text) - 1), label="n_start")
    b = data.draw(st.integers(a + 1, len(norm.text)), label="n_end")
    start, end = norm.to_original(a, b)
    behind = set(norm.index_map[a:b])
    # the span runs from the first original character behind the slice to the last, and
    # anything between them not behind it is whitespace the normalization collapsed away
    assert start == min(behind)
    assert end - 1 == max(behind)
    for i in range(start, end):
        assert i in behind or (text[i].isspace() and text[i - 1].isspace())
    # normalizing the span reproduces the normalized characters behind it
    assert NormalizedText.of(text[start:end]).text == "".join(
        c for c, i in zip(norm.text, norm.index_map, strict=True) if start <= i < end
    )


# --- the rapidfuzz coordinate pin (§6.3; L27) -----------------------------------


@pytest.mark.parametrize(
    ("first", "second"),
    [("pt denies cp or sob today", "denies cp"), ("denies cp", "pt denies cp or sob today")],
    ids=["first-longer", "second-longer"],
)
def test_alignment_src_indexes_the_first_argument(first: str, second: str) -> None:
    # L27: §6.3 aligns with partial_ratio_alignment(norm.text, nq) and maps src_start and
    # src_end through to_original, so they must index the first argument, whichever is longer
    align = fuzz.partial_ratio_alignment(first, second)
    assert align is not None
    assert first[align.src_start : align.src_end] == "denies cp"
    assert second[align.dest_start : align.dest_end] == "denies cp"
