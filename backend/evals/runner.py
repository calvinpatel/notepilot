"""The check engine and the checks' lineage (spec §8.7).

run_checks runs the selected checks on one note. It fails closed per check (invariant 12): a
check that raises, returns a finding above its severity (L38), or names a claim the note
lacks (L115) becomes one errored result, logged in L69's form (L113), and the rest still run.

CHECKS_VERSION hashes the source that decides verdicts, so a corpus run records which checks
judged it (L45, L114).
"""

import hashlib
import inspect
import json
import logging
from pathlib import Path
from typing import Final, Literal

from backend.evals.judge import Judge
from backend.evals.registry import REGISTRY, stamp
from backend.schemas import EvalCase, EvalReport, EvalResult, SOAPNote, TokenUsage
from backend.tracebacks import format_frames

logger = logging.getLogger(__name__)


def checks_version(root: Path) -> str:
    """Twelve hex digits over root's checks source: evals/ and clinical/, and grounding.py.

    Source is the .py files (L114): case YAMLs have corpus_version, and runs/corpus_runs.jsonl
    changes on every run. Each file enters with its path relative to root, so a moved or
    renamed file moves the version; the paths are sorted, since listing order varies by
    filesystem.
    """
    files = [root / "grounding.py"]
    for package in ("evals", "clinical"):
        files.extend((root / package).rglob("*.py"))  # nothing, while a package doesn't exist
    payload = sorted(
        (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in files
    )
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:12]


# over backend/, computed at import (§8.7)
CHECKS_VERSION: Final = checks_version(Path(__file__).resolve().parents[1])


async def run_checks(
    note: SOAPNote,
    raw_text: str,
    case: EvalCase | None = None,
    *,
    mode: Literal["production", "ci"],
    judge: Judge | None = None,
) -> EvalReport:
    """Run the selected checks on one note (§8.7).

    Selected: every check in ci mode, the reference-free ones in production, and a judged
    check only when a judge is given (L49).
    """
    selected = [
        c
        for c in REGISTRY.values()
        if (mode == "ci" or not c.requires_reference) and (not c.needs_judge or judge is not None)
    ]
    claim_ids = {c.id for c in note.claims}
    results: list[EvalResult] = []
    for check in selected:
        try:
            out = (
                check.fn(note, raw_text, case, judge=judge)
                if check.needs_judge
                else check.fn(note, raw_text, case)
            )
            findings = await out if inspect.isawaitable(out) else out
            stamped = [stamp(check, f) for f in findings]  # a bad finding is a bad check
            if any(i not in claim_ids for r in stamped for i in r.claim_ids):  # L115
                raise ValueError(f"{check.name}: a finding names a claim the note lacks")
        except Exception as exc:
            # Not a passed check, and not a 500. Logged in L69's form: the message and
            # exc_info can carry note content (L53). CancelledError is a BaseException, so
            # it passes through.
            logger.error(
                "check_crashed code=check_errored check=%s exc_type=%s frames=%s",
                check.name,
                type(exc).__name__,
                format_frames(exc),
            )
            results.append(
                EvalResult(
                    check=check.name,
                    severity=check.severity,
                    passed=False,
                    errored=True,
                    detail="check errored",
                )
            )
            continue
        results.extend(
            stamped or [EvalResult(check=check.name, severity=check.severity, passed=True)]
        )
    return EvalReport(
        results=results,
        checks_run=frozenset(c.name for c in selected),
        checks_version=CHECKS_VERSION,
        judge_usage=judge.usage if judge is not None else TokenUsage(),
    )
