"""The model corpus's answer keys, checked free before a run pays for them (§8.5, §11; L246).

A model case has no draft: the model writes its note on a paid run. A free test can still
check its answer key. A faithful note, each sentence of the raw text a claim quoting
itself, reaches the verdict the case asks for, so a case no faithful note can pass is caught
here rather than on every paid run, where the scorecard would blame the model.
"""

import re

import pytest

from backend.evals.loader import CASES_DIR, load_cases
from backend.evals.runner import case_verdict, run_checks
from backend.grounding import ground
from backend.schemas import EvalCase, SOAPNoteDraft
from tests.fakes import CHECKS_CONFIG

MODEL = [case for case in load_cases(CASES_DIR) if case.draft is None]


def _faithful(raw_text: str) -> SOAPNoteDraft:
    """Each sentence of each line, its final period dropped, as a claim quoting itself.

    A sentence ends at a period followed by a space, or at its line's end (L143). Every claim
    is S, so the test guesses no sections (L246).
    """
    sentences = [
        s.removesuffix(".") for line in raw_text.splitlines() for s in re.split(r"(?<=\.) ", line)
    ]
    claims = [{"text": s, "section": "S", "source_quote": s} for s in sentences if s]
    return SOAPNoteDraft.model_validate({"claims": claims})


@pytest.mark.anyio
@pytest.mark.parametrize("case", MODEL, ids=[case.id for case in MODEL])
async def test_a_faithful_note_passes_a_model_case(case: EvalCase) -> None:
    note = ground(_faithful(case.raw_text), case.raw_text, config=CHECKS_CONFIG)
    report = await run_checks(note, case.raw_text, case, mode="ci", config=CHECKS_CONFIG)
    assert case_verdict(report, case) == "passed", report.results
