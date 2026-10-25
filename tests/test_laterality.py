"""extract_laterality: a side and the site after it (L285, L304, L305).

The fills L304 and L305 make, and the costs §8.8 states (L306, L338), are pinned here; the
check that reads these sides lands in its own commit (L286).
"""

import pytest

from backend.clinical.extract import Side, extract_laterality
from backend.clinical.lexicons import NOT_SIDES, SIDE_CUES, SIDE_LETTERS, SIDE_SITES

type _Sides = dict[str, set[Side]]


@pytest.mark.parametrize(
    ("text", "two", "one"),
    [
        # L285: a site is the words after a side, read two words wide and one
        ("Left knee pain after a fall", {"knee pain": {"left"}}, {"knee": {"left"}}),
        ("Bilateral knee pain", {"knee pain": {"bilateral"}}, {"knee": {"bilateral"}}),
        ("Right-sided chest pain", {"chest pain": {"right"}}, {"chest": {"right"}}),
        (
            "Left-side weakness and right facial droop",
            {"facial droop": {"right"}},
            {"weakness": {"left"}, "facial": {"right"}},
        ),
        # a SIDE_SITES token's site is spelled out, so it meets the charting that spells it
        ("RLQ tenderness", {"lower quadrant": {"right"}}, {"lower": {"right"}}),
        ("Right lower quadrant tenderness", {"lower quadrant": {"right"}}, {"lower": {"right"}}),
        ("LLE edema", {"lower extremity": {"left"}}, {"lower": {"left"}}),
        # a bare letter before a word and not after a number
        ("L knee pain", {"knee pain": {"left"}}, {"knee": {"left"}}),
        ("2 L NC", {}, {}),
        ("R/O PE", {}, {}),
        # L305: the two-letter forms take their period; a lone letter's is an initial's
        (
            "Rt. hip pain, lt. knee pain",
            {"hip pain": {"right"}, "knee pain": {"left"}},
            {"hip": {"right"}, "knee": {"left"}},
        ),
        ("Dr. R. Smith saw the patient", {}, {}),
        # sides joined by "and", "or", or a comma share the site after the last
        ("Left and right knee pain", {"knee pain": {"left", "right"}}, {"knee": {"left", "right"}}),
        ("Left, right knee pain", {"knee pain": {"left", "right"}}, {"knee": {"left", "right"}}),
        ("L and R knee pain", {"knee pain": {"left", "right"}}, {"knee": {"left", "right"}}),
        ("Left and right. Right hip pain", {"hip pain": {"right"}}, {"hip": {"right"}}),
        # a join holds a side only for a side after it, so a refused letter holds none
        ("Reflexes 2+ L and R. Right knee pain", {"knee pain": {"right"}}, {"knee": {"right"}}),
        # a NOT_SIDES phrase, a token kept whole, and a side with no site name none
        ("Pt left AMA with right knee pain", {"knee pain": {"right"}}, {"knee": {"right"}}),
        ("Right handed", {}, {}),
        ("L4 radiculopathy, LAD stenosis, RA flare", {}, {}),
        ("Acute otitis media, left ear", {}, {"ear": {"left"}}),
        ("Left knee: pain", {}, {"knee": {"left"}}),
        # L304: a site holds no function word
        ("R knee and L ankle", {}, {"knee": {"right"}, "ankle": {"left"}}),
        ("Tender left of the sternum", {}, {}),
        # §8.8's costs (L306): "&" and "/" join no sides, a bare letter before a comma is none,
        # and a side after its site names none
        ("Left & right knee pain", {"knee pain": {"right"}}, {"knee": {"right"}}),
        ("L, R knee pain", {"knee pain": {"right"}}, {"knee": {"right"}}),
        ("Chest pain on the left", {}, {}),
        # §8.8's costs (L338): a corrected side reads both sides at its site, and a finding
        # shared by "also" stays at the first side's two-word site
        (
            "Right knee swelling, I mean left knee swelling",
            {"knee swelling": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Left knee swollen, right knee also",
            {"knee swollen": {"left"}, "knee also": {"right"}},
            {"knee": {"left", "right"}},
        ),
        # §8.8 (L285): no table lists these
        ("Edema L>R, both knees swollen, OD pain", {}, {}),
    ],
)
def test_a_side_names_the_site_after_it(text: str, two: _Sides, one: _Sides) -> None:
    assert extract_laterality(text, 2) == two
    assert extract_laterality(text, 1) == one


@pytest.mark.parametrize(("cue", "side"), sorted(SIDE_CUES.items()))
def test_every_side_cue_names_the_site_after_it(cue: str, side: str) -> None:
    assert extract_laterality(f"{cue} knee pain", 2) == {"knee pain": {side}}


@pytest.mark.parametrize(("letter", "side"), sorted(SIDE_LETTERS.items()))
def test_every_side_letter_names_the_site_after_it(letter: str, side: str) -> None:
    assert extract_laterality(f"{letter} knee pain", 2) == {"knee pain": {side}}


@pytest.mark.parametrize(("token", "side_site"), sorted(SIDE_SITES.items()))
def test_every_side_site_names_its_side_at_its_site(token: str, side_site: tuple[str, str]) -> None:
    side, site = side_site
    assert extract_laterality(f"{token} pain", 2) == {site: {side}}


@pytest.mark.parametrize("phrase", sorted(NOT_SIDES))
def test_every_not_side_phrase_names_no_side(phrase: str) -> None:
    assert extract_laterality(f"{phrase} knee pain", 2) == {}
