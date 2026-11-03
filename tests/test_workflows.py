"""Pins what the two workflows promise about the API key and the spend (spec §10, §11; L393).

Only GitHub runs a workflow, so these read the files. ci.yml names no secret. corpus.yml runs
on dispatch alone, its first step refuses a ref other than main, and spend and judge default
off. It reads the key once, in the step that runs the corpus, whose RUNS_PATH is in the
runner's temporary directory and is the path the upload takes. Its job holds the key, so each
action is pinned to a commit.
"""

import re
from pathlib import Path
from typing import Any, Final

from ruamel.yaml import YAML

_WORKFLOWS: Final = Path(__file__).resolve().parent.parent / ".github" / "workflows"
_KEY: Final = "${{ secrets.ANTHROPIC_API_KEY }}"
_RUNNER_TEMP: Final = "${{ runner.temp }}/"
_PINNED: Final = re.compile(r"[^@\s]+@[0-9a-f]{40}")


def _corpus() -> dict[str, Any]:
    """corpus.yml, parsed: ruamel's safe loader reads YAML 1.2, so the key "on" stays a string."""
    document = YAML(typ="safe", pure=True).load(_WORKFLOWS / "corpus.yml")
    assert isinstance(document, dict)
    return document


def _steps() -> list[dict[str, Any]]:
    steps = _corpus()["jobs"]["score"]["steps"]
    assert isinstance(steps, list)
    return steps


def _corpus_step() -> dict[str, Any]:
    """The one step that runs python -m backend.corpus."""
    (step,) = (s for s in _steps() if "python -m backend.corpus" in s.get("run", ""))
    return step


def _texts(node: object) -> list[str]:
    """Every key and every string value of a parsed document."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [t for key, value in node.items() for t in (*_texts(key), *_texts(value))]
    if isinstance(node, list):
        return [t for item in node for t in _texts(item)]
    return []


def test_ci_names_no_secret() -> None:
    # §10: no test reaches the network, so the push workflow needs no key
    assert "secrets" not in (_WORKFLOWS / "ci.yml").read_text(encoding="utf-8")


def test_the_corpus_runs_on_dispatch_alone() -> None:
    # §11: the model corpus is never in the push path; a dispatch is the go-ahead
    assert list(_corpus()["on"]) == ["workflow_dispatch"]


def test_spending_and_judging_are_off_by_default() -> None:
    # L210: spending is never a default, here as on the command line
    inputs = _corpus()["on"]["workflow_dispatch"]["inputs"]
    shapes = {name: (spec["type"], spec["default"]) for name, spec in inputs.items()}
    assert shapes == {"spend": ("boolean", False), "judge": ("boolean", False)}


def test_the_first_step_refuses_a_ref_other_than_main() -> None:
    first = _steps()[0]
    assert (first["if"], first["run"].splitlines()[-1]) == (
        "github.ref != 'refs/heads/main'",
        "exit 1",
    )


def test_the_key_is_read_once_in_the_step_that_runs_the_corpus() -> None:
    assert sum("secrets" in text for text in _texts(_corpus())) == 1
    assert _corpus_step().get("env", {}).get("ANTHROPIC_API_KEY") == _KEY


def test_the_record_lands_outside_the_checkout_and_is_uploaded() -> None:
    # outside the checkout, a dispatched run's record never joins the tracked file (D5)
    runs_path = _corpus_step()["env"]["RUNS_PATH"]
    (upload,) = (s for s in _steps() if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert runs_path.startswith(_RUNNER_TEMP)
    assert upload["with"]["path"] == runs_path


def test_each_action_is_pinned_to_a_commit() -> None:
    uses = [step["uses"] for step in _steps() if "uses" in step]
    assert uses  # a scan that read no step would pass
    assert [u for u in uses if not _PINNED.fullmatch(u)] == []
