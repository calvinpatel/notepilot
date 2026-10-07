"""Pins grounding: NormalizedText and its index map, rapidfuzz's coordinates, the ladder.

Spec §6.1-§6.5, §11; L8, L26, L27, L62, L66, L105, L107, L108, L109, L110.
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from rapidfuzz import fuzz

from backend import config, grounding
from backend.grounding import PUNCT_MAP, NormalizedText, _snap, ground, ground_claim
from backend.schemas import ClaimDraft, ClinicalClaim, SafetyFlag, SOAPNoteDraft

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


@pytest.mark.parametrize(
    ("n_start", "n_end"), [(0, 0), (3, 3), (5, 2)], ids=["empty-at-0", "empty", "reversed"]
)
def test_to_original_rejects_an_empty_slice(n_start: int, n_end: int) -> None:
    # L109: an empty slice has no last character, and at 0 the lookup would wrap to the end
    with pytest.raises(ValueError, match="empty normalized slice"):
        NormalizedText.of("Pt  denies\tCP").to_original(n_start, n_end)


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


# --- the ladder (§6.1, §6.3, §6.5; L8, L66, L105, L107, L108, L110) -------------

_NOTE = (
    "Pt  denies\tCP. Plan: Increase metformin to 1000 mg BID. Hypothyroidism, stable on "
    "levothyroxine 75 mcg daily. BP 148/92, HR 88. Rapid strep negative. Continue ibuprofen "
    "400 mg q6h prn. Pt denies SOB. No edema. Pt denies chest pain at rest; on exertion, pt "
    "denies chest pain."
)


def _ground(quote: str, raw: str = _NOTE) -> ClinicalClaim:
    draft = ClaimDraft(text="fact-1", section="S", source_quote=quote)
    return ground_claim(draft, raw, NormalizedText.of(raw), claim_id=0)


def _span_text(claim: ClinicalClaim, raw: str = _NOTE) -> str:
    assert claim.source_span is not None
    start, end = claim.source_span
    return raw[start:end]


def test_tier_1_an_exact_quote_grounds_clean() -> None:
    claim = _ground("Rapid strep negative")
    assert _span_text(claim) == "Rapid strep negative"
    assert claim.flags == ()
    assert claim.grounding_score is None


def test_tier_2_a_quote_differing_in_case_and_whitespace_grounds_clean() -> None:
    claim = _ground("pt denies cp")
    assert _span_text(claim) == "Pt  denies\tCP"
    assert claim.flags == ()
    assert claim.grounding_score is None


@pytest.mark.parametrize(
    ("quote", "span"),
    [
        ("Increase metformin to 1000mg BID", "Increase metformin to 1000 mg BID"),
        ("stable on levothyroxine 75mcg daily", "stable on levothyroxine 75 mcg daily"),
    ],
    ids=["BID", "daily"],
)
def test_tier_3_a_close_paraphrase_is_paraphrased_on_whole_words(quote: str, span: str) -> None:
    # L108: the alignment window is as long as the quote, so here it ends inside the
    # source's last word, at "BI" and "dail"; the span widens to whole words
    claim = _ground(quote)
    assert claim.flags == (SafetyFlag.PARAPHRASED,)
    assert _span_text(claim) == span
    assert claim.grounding_score is not None
    assert claim.grounding_score >= config.settings.fuzzy_score_cutoff


_SNAP_RAW = "Hypothyroidism, stable on levothyroxine 75 mcg daily."


@pytest.mark.parametrize(
    ("piece", "whole"),
    [
        ("table on levothyroxine", "stable on levothyroxine"),
        ("75 mcg dail", "75 mcg daily"),
        ("able on levothyroxine 75 mcg dai", "stable on levothyroxine 75 mcg daily"),
        ("75 mcg", "75 mcg"),
        (", stable", ", stable"),
    ],
    ids=["start", "end", "both", "whole-words", "punctuation"],
)
def test_snap_widens_a_span_to_whole_words(piece: str, whole: str) -> None:
    # L108, directly: which end a window cuts is a tie rapidfuzz breaks, so the ladder
    # tests above reach only one end
    start = _SNAP_RAW.index(piece)
    snapped_start, snapped_end = _snap(_SNAP_RAW, start, start + len(piece))
    assert _SNAP_RAW[snapped_start:snapped_end] == whole


def test_tier_4_a_near_miss_keeps_its_score() -> None:
    # L8: below the cutoff the quote grounds nowhere, and its score is tuning data
    claim = _ground("Rapid strep positive")
    assert claim.flags == (SafetyFlag.UNSUPPORTED,)
    assert claim.source_span is None
    assert claim.grounding_score is not None
    assert claim.grounding_score < config.settings.fuzzy_score_cutoff


@pytest.mark.parametrize(
    ("quote", "raw"),
    [
        ("Continue ibuprofen 600 mg q6h prn", _NOTE),
        ("Continue ibuprofen 400.0 mg q6h prn", _NOTE),
        ("BP 190/110", "Vitals: BP 130/110, HR 88."),
    ],
    ids=["changed-digit", "trailing-zero", "spec-example"],
)
def test_numeric_guard_demotes_a_number_the_span_lacks(quote: str, raw: str) -> None:
    # §6.3: fuzzy forgives letters, never digits; 400.0 for 400 errs red on purpose, and
    # §6.5's example clears the cutoff, so it is the guard that demotes it (L110)
    claim = _ground(quote, raw)
    assert claim.flags == (SafetyFlag.UNSUPPORTED,)
    assert claim.source_span is None
    assert claim.grounding_score is not None
    assert claim.grounding_score >= config.settings.fuzzy_score_cutoff  # the guard, not the cutoff


def test_detect_vital_drift() -> None:
    # L66: a drifted vital is a numeric invention, so it is grounding's guard that catches it
    claim = _ground("BP 184/92, HR 88")
    assert claim.flags == (SafetyFlag.UNSUPPORTED,)
    assert claim.grounding_score is not None
    assert claim.grounding_score >= config.settings.fuzzy_score_cutoff


def test_the_cutoff_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # L105: a cutoff just above this quote's score demotes it
    quote = "Increase metformin to 1000mg BID"
    score = _ground(quote).grounding_score
    assert score is not None
    raised = config.settings.model_copy(update={"fuzzy_score_cutoff": score + 0.01})
    monkeypatch.setattr(grounding, "settings", raised)
    claim = _ground(quote)
    assert claim.flags == (SafetyFlag.UNSUPPORTED,)
    assert claim.grounding_score == score


def test_the_cutoff_is_inclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    quote = "Increase metformin to 1000mg BID"
    score = _ground(quote).grounding_score
    assert score is not None
    exact = config.settings.model_copy(update={"fuzzy_score_cutoff": score})
    monkeypatch.setattr(grounding, "settings", exact)
    assert _ground(quote).flags == (SafetyFlag.PARAPHRASED,)


def test_an_empty_raw_text_grounds_nothing() -> None:
    # an alignment against nothing is empty, so there is no score to keep
    claim = _ground("Rapid strep negative", raw="")
    assert claim.flags == (SafetyFlag.UNSUPPORTED,)
    assert claim.source_span is None
    assert claim.grounding_score is None


@pytest.mark.parametrize(
    "quote", ["denies chest pain", "DENIES  CHEST PAIN"], ids=["exact", "respelled"]
)
def test_a_repeated_quote_grounds_at_its_first_occurrence(quote: str) -> None:
    # §6.5: first occurrence, chosen on purpose; choosing by locality is v2
    claim = _ground(quote)
    assert claim.source_span is not None
    assert claim.source_span[0] == _NOTE.index("denies chest pain")


def test_a_quote_merging_two_sentences_is_paraphrased() -> None:
    # §6.5: the model joined "Pt denies SOB. No edema." into one sentence
    claim = _ground("Pt denies SOB, no edema.")
    assert claim.flags == (SafetyFlag.PARAPHRASED,)
    assert _span_text(claim) == "Pt denies SOB. No edema."


def test_a_degenerate_quote_grounds_clean() -> None:
    # D15: "pain" is in the source, so grounding accepts it; quote_informativeness is evals'
    assert _ground("pain").flags == ()


def test_an_unvalidated_blank_draft_fails_loudly() -> None:
    # L107: a blank quote can't pass the boundary (L106); a draft built around it is a
    # programming error, and building its ClinicalClaim raises
    draft = ClaimDraft.model_construct(text="fact-1", section="S", source_quote="   ")
    with pytest.raises(ValidationError) as exc:
        ground_claim(draft, _NOTE, NormalizedText.of(_NOTE), claim_id=0)
    (err,) = exc.value.errors()
    assert err["type"] == "string_too_short"
    assert err["loc"] == ("source_quote",)


def test_ground_stamps_ids_in_draft_order() -> None:
    draft = SOAPNoteDraft(
        claims=[
            ClaimDraft(text="fact-1", section="O", source_quote="BP 148/92"),
            ClaimDraft(text="fact-2", section="P", source_quote="not in the note"),
        ]
    )
    note = ground(draft, _NOTE)
    assert [c.id for c in note.claims] == [0, 1]
    assert [c.text for c in note.claims] == ["fact-1", "fact-2"]
    assert note.claims[1].flags == (SafetyFlag.UNSUPPORTED,)


def test_ground_of_an_empty_draft_is_an_empty_note() -> None:
    assert ground(SOAPNoteDraft(claims=[]), _NOTE).claims == ()


# --- the ladder's properties (§11; L62) ------------------------------------------

_WS = [c for c in _NAMED if c.isspace()]


def _cut(data: st.DataObject) -> tuple[str, str]:
    raw = data.draw(_texts(min_size=1), label="raw")
    i = data.draw(st.integers(0, len(raw) - 1), label="i")
    j = data.draw(st.integers(i + 1, len(raw)), label="j")
    return raw, raw[i:j]


@given(st.data())
def test_a_quote_cut_from_the_text_grounds_to_itself(data: st.DataObject) -> None:
    # L62's first property, as written: the span is the stripped quote
    raw, q = _cut(data)
    assume(q.strip())
    claim = _ground(q, raw)
    assert claim.flags == ()
    assert _span_text(claim, raw) == q.strip()


@given(st.data())
def test_a_respelled_quote_grounds_clean_on_a_span_that_normalizes_back(
    data: st.DataObject,
) -> None:
    # Tier 2: case, whitespace runs, and PUNCT_MAP variants differ; the normalized text doesn't
    raw, q = _cut(data)
    respelled = []
    for ch in q:
        if ch.isspace():
            run = data.draw(st.lists(st.sampled_from(_WS), min_size=1, max_size=3))
            respelled.append("".join(run))
            continue
        same = sorted(
            c
            for c in {ch, ch.upper(), ch.lower(), *PUNCT_MAP, *PUNCT_MAP.values()}
            if NormalizedText.of(c).text == NormalizedText.of(ch).text
        )
        respelled.append(data.draw(st.sampled_from(same)))
    quote = "".join(respelled)
    assume(quote.strip())
    claim = _ground(quote, raw)
    assert claim.flags == ()
    nq = NormalizedText.of(quote.strip()).text
    got = NormalizedText.of(_span_text(claim, raw)).text
    assert nq in got
    assert len(got) <= len(nq) + 2  # widened only to whole characters, one at each edge
