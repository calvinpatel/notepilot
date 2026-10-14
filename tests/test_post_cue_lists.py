"""A post-cue over a list, through grounding and the checks (§7, §8.4; L193).

Measured at d55153d, before L193's code: on "ROS: fever, chills, and nausea denied", every
faithful summary fired two false CRITICALs, however the claims were grouped, and a flipped
claim citing the same span fired nothing. The plan line guards the other side: a list after
a word keeps adjacent-only reach, so a continued drug before a held one stays active.
"""

import pytest

from backend.evals.runner import run_checks
from backend.grounding import ground
from backend.schemas import SOAPNoteDraft
from tests.fakes import CHECKS_CONFIG

_ROS = "ROS: fever, chills, and nausea denied. Exam normal."
_ROS_SPAN = "fever, chills, and nausea denied"


async def _fired(raw: str, claims: list[tuple[str, str, str]]) -> list[tuple[str, str]]:
    """The checks that fire on a note of (text, section, quote) claims, grounded in raw."""
    draft = SOAPNoteDraft.model_validate(
        {"claims": [{"text": t, "section": s, "source_quote": q} for t, s, q in claims]}
    )
    note = ground(draft, raw, config=CHECKS_CONFIG)
    report = await run_checks(note, raw, mode="production", config=CHECKS_CONFIG)
    return [(r.check, r.severity.value) for r in report.results if not r.passed]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "claims",
    [
        [
            ("Denies fever", "S", _ROS_SPAN),
            ("Denies chills", "S", _ROS_SPAN),
            ("Denies nausea", "S", _ROS_SPAN),
        ],
        [("Denies fever, chills, and nausea", "S", _ROS_SPAN)],
    ],
    ids=["split", "merged"],
)
async def test_a_faithful_summary_of_a_bare_ros_list_fires_nothing(
    claims: list[tuple[str, str, str]],
) -> None:
    assert await _fired(_ROS, claims) == []


@pytest.mark.anyio
async def test_a_flipped_claim_on_a_bare_ros_list_is_caught() -> None:
    assert await _fired(_ROS, [("Reports fever", "S", _ROS_SPAN)]) == [
        ("negation_consistency", "critical")
    ]


@pytest.mark.anyio
async def test_a_continued_drug_cited_with_a_held_one_stays_active() -> None:
    raw = "Plan: continue lisinopril, metformin held for AKI."
    claims = [
        ("Continue lisinopril", "P", "continue lisinopril, metformin held"),
        ("Metformin held", "P", "metformin held"),
    ]
    assert await _fired(raw, claims) == []
