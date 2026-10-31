"""extract_laterality: a side and its site (L285, L304, L305, L367, L369, L370).

The fills L304 and L305 make, and the costs §8.8 states (L367, L370, L382, L383), are pinned
here; the check that reads these sides lands in its own commit (L286).
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
        # L367: "/" and "&" join sides too, and a bare letter is a side before a join another
        # side follows
        ("Left & right knee pain", {"knee pain": {"left", "right"}}, {"knee": {"left", "right"}}),
        ("Left/right knee pain", {"knee pain": {"left", "right"}}, {"knee": {"left", "right"}}),
        ("L, R knee pain", {"knee pain": {"left", "right"}}, {"knee": {"left", "right"}}),
        ("L & R knee pain", {"knee pain": {"left", "right"}}, {"knee": {"left", "right"}}),
        ("L/R knee pain", {"knee pain": {"left", "right"}}, {"knee": {"left", "right"}}),
        ("L/S spine tenderness", {}, {}),
        # L367: a side naming no site after it binds back to the nearest site, across a comma,
        # a hyphen, a colon, or "on the"
        ("Chest pain on the left", {"chest pain": {"left"}}, {"pain": {"left"}}),
        ("Decreased breath sounds on the left", {"breath sounds": {"left"}}, {"sounds": {"left"}}),
        ("Knee pain, right", {"knee pain": {"right"}}, {"pain": {"right"}}),
        ("Knee pain - right", {"knee pain": {"right"}}, {"pain": {"right"}}),
        ("Knee pain: right", {"knee pain": {"right"}}, {"pain": {"right"}}),
        (
            "Edema in the lower extremity, left",
            {"lower extremity": {"left"}},
            {"extremity": {"left"}},
        ),
        # and only where no width finds a site after it, to a site holding no side, and across
        # something
        (
            "Right knee swelling, left ankle",
            {"knee swelling": {"right"}},
            {"knee": {"right"}, "ankle": {"left"}},
        ),
        ("Left knee, right", {}, {"knee": {"left", "right"}}),
        ("R knee, left", {}, {"knee": {"left", "right"}}),
        (
            "RLQ tenderness, left",
            {"lower quadrant": {"right"}},
            {"lower": {"right"}, "tenderness": {"left"}},
        ),
        ("Patient left, knee pain resolved", {}, {}),
        # §8.8's costs (L367): a side directly after its site names none, and a trailing side
        # reaches the nearest site alone
        ("Edema bilaterally", {}, {}),
        ("Knee and hip pain, right", {"hip pain": {"right"}}, {"pain": {"right"}}),
        # §8.8's cost (L382): a parenthesis is neither a link nor the word or join a letter needs
        ("Knee pain (right)", {}, {}),
        ("Knee pain (R)", {}, {}),
        ("(R) knee pain", {}, {}),
        # L370: a correction cue that leads straight to a side, across marks and function words,
        # retires the side charted before it at that site, in its clause
        (
            "Right knee swelling, I mean left knee swelling",
            {"knee swelling": {"left"}},
            {"knee": {"left"}},
        ),
        ("Right knee pain, sorry, left knee pain", {"knee pain": {"left"}}, {"knee": {"left"}}),
        ("right knee, sorry, scratch that, it's the left knee", {}, {"knee": {"left"}}),
        ("Swelling of the right knee, correction: left knee", {}, {"knee": {"left"}}),
        ("Right knee, no, left knee, is swollen", {}, {"knee": {"left"}}),
        ("LLQ pain, I mean RLQ pain", {"lower quadrant": {"right"}}, {"lower": {"right"}}),
        (
            "Right knee swelling, I mean left knee swelling, also tender to touch",
            {"knee swelling": {"left"}},
            {"knee": {"left"}},
        ),
        # and retires nothing where words stand between, "also" or "too" follows the new side,
        # nothing comes before it, or the site differs
        (
            "Right knee pain, I mean worse than the left knee pain",
            {"knee pain": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Right knee pain, no swelling, left knee pain",
            {"knee pain": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Right knee swelling, sorry, left knee also swollen",
            {"knee swelling": {"right"}, "knee swollen": {"left"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Right knee pain, sorry, left knee pain too",
            {"knee pain": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Sorry, right knee pain, left knee pain",
            {"knee pain": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Right knee pain, correction: right hip pain",
            {"knee pain": {"right"}, "hip pain": {"right"}},
            {"knee": {"right"}, "hip": {"right"}},
        ),
        # §8.8's cost (L370): a correction past a sentence end retires nothing
        (
            "Right knee swelling. Sorry, I mean the left knee.",
            {"knee swelling": {"right"}},
            {"knee": {"left", "right"}},
        ),
        # L369: "also", "too", and "as well" are read past, and a site they leave short shares
        # the nearest earlier site in its clause that begins with the words read
        (
            "Left knee swollen, right knee also",
            {"knee swollen": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Left knee swollen, right knee too",
            {"knee swollen": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Left knee swollen, right knee as well",
            {"knee swollen": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Left knee swollen, right also",
            {"knee swollen": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        ("Right knee also swollen", {"knee swollen": {"right"}}, {"knee": {"right"}}),
        (
            "Left knee swollen, right knee also tender",
            {"knee swollen": {"left"}, "knee tender": {"right"}},
            {"knee": {"left", "right"}},
        ),
        (
            "Left knee swollen, left knee tender, right knee also",
            {"knee swollen": {"left"}, "knee tender": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        # and only a site that begins with the words read, in the same clause
        (
            "Left knee swollen, right hip too",
            {"knee swollen": {"left"}},
            {"knee": {"left"}, "hip": {"right"}},
        ),
        (
            "Left knee swollen. Right knee also",
            {"knee swollen": {"left"}},
            {"knee": {"left", "right"}},
        ),
        # §8.8's cost (L383): a bare side shares the nearest site a side charted, past a finding
        # no side names
        (
            "Left knee swollen, hip tender, right also",
            {"knee swollen": {"left", "right"}},
            {"knee": {"left", "right"}},
        ),
        # with no earlier site to share, a side binds back past them (L367)
        ("Knee pain, right too", {"knee pain": {"right"}}, {"pain": {"right"}}),
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
