"""Pins the case loader (spec §8.5; L103, L118, L119)."""

from collections.abc import Mapping
from pathlib import Path

import pytest

from backend.evals.loader import CaseLoadError, load_cases
from backend.evals.registry import Check, Finding, register_check
from backend.schemas import EvalCase, Severity, SOAPNote

RAW_SENTINEL = "sentinel-raw-3e9b"

DETECTION = """
id: detect-1
species: detection
raw_text: |
  Pt with acute sinusitis. Will start antibiotics, f/u 1 wk.
trap: claim text names a drug its source span does not
draft:
  claims:
    - text: Start amoxicillin
      section: P
      source_quote: Will start antibiotics
expected_flags: [drug_in_quote]
"""

CONTROL = """
id: control-1
species: control
raw_text: |
  Pt well. No changes to medications.
trap: null
"""


FIDELITY_NO = """
id: fidelity-1
species: fidelity
raw_text: Pt well.
trap: no
"""

UNTERMINATED = f"""
id: control-1
species: control
raw_text: "{RAW_SENTINEL}
trap: null
"""

DUPLICATE_RAW_TEXT = (
    CONTROL
    + f"""raw_text: {RAW_SENTINEL}
"""
)

DUPLICATE_FLAGS = (
    DETECTION
    + """expected_flags: [dose_consistency]
"""
)

A_LIST = """
- x
- y
"""


def _clean(note: SOAPNote, raw_text: str, case: EvalCase | None = None) -> list[Finding]:
    return []


@pytest.fixture
def drug_in_quote(registry: dict[str, Check]) -> None:
    """The check DETECTION's answer key names, registered for the test."""
    register_check(name="drug_in_quote", severity=Severity.CRITICAL)(_clean)


def _write(directory: Path, files: Mapping[str, str | bytes]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        if isinstance(content, bytes):
            (directory / name).write_bytes(content)
        else:
            (directory / name).write_text(content, encoding="utf-8")
    return directory


def _problems(directory: Path) -> tuple[str, ...]:
    with pytest.raises(CaseLoadError) as caught:
        load_cases(directory)
    return caught.value.problems


# --- what loads ---------------------------------------------------------------


@pytest.mark.usefixtures("drug_in_quote")
def test_load_cases_returns_every_case_sorted_by_id(tmp_path: Path) -> None:
    # written out of order: the result follows the ids, not the writes
    cases = load_cases(_write(tmp_path, {"detect-1.yaml": DETECTION, "control-1.yaml": CONTROL}))
    assert [c.id for c in cases] == ["control-1", "detect-1"]
    control, detection = cases
    assert (control.species, control.trap, control.draft) == ("control", None, None)
    assert detection.expected_flags == ["drug_in_quote"]
    assert detection.draft is not None
    assert detection.draft.claims[0].source_quote == "Will start antibiotics"


def test_an_empty_directory_loads_no_cases(tmp_path: Path) -> None:
    assert load_cases(tmp_path) == []


def test_yaml_is_read_as_1_2(tmp_path: Path) -> None:
    # YAML 1.1 reads `no` as False, and EvalCase would then reject trap as not a string
    (case,) = load_cases(_write(tmp_path, {"fidelity-1.yaml": FIDELITY_NO}))
    assert case.trap == "no"


def test_dotfiles_are_skipped(tmp_path: Path) -> None:
    # .DS_Store and editor droppings aren't cases; .gitignore keeps them out of the repo
    assert load_cases(_write(tmp_path, {".DS_Store": bytes([0, 1, 2]), ".notes.swp": "x"})) == []


# --- what doesn't (§8.5) ------------------------------------------------------


@pytest.mark.usefixtures("registry")  # empty on purpose, whatever registers at import
def test_an_unregistered_expected_flag_is_a_load_error(tmp_path: Path) -> None:
    problems = _problems(_write(tmp_path, {"detect-1.yaml": DETECTION}))
    assert problems == ("detect-1.yaml: expected_flags names unregistered checks: drug_in_quote",)


@pytest.mark.usefixtures("drug_in_quote")
def test_an_id_that_isnt_the_file_name_is_a_load_error(tmp_path: Path) -> None:
    problems = _problems(_write(tmp_path, {"control-2.yaml": CONTROL}))
    assert problems == ("control-2.yaml: id 'control-1' doesn't match the file name",)


@pytest.mark.usefixtures("drug_in_quote")
def test_a_duplicate_key_is_a_load_error(tmp_path: Path) -> None:
    # L118: a second answer key would otherwise replace the first, silently
    assert _problems(_write(tmp_path, {"detect-1.yaml": DUPLICATE_FLAGS})) == (
        "detect-1.yaml: line 13: duplicate key",
    )


def test_a_duplicate_key_names_its_line_never_its_values(tmp_path: Path) -> None:
    # ruamel's own message quotes both values: here, the planted raw_text
    with pytest.raises(CaseLoadError) as caught:
        load_cases(_write(tmp_path, {"control-1.yaml": DUPLICATE_RAW_TEXT}))
    assert caught.value.problems == ("control-1.yaml: line 7: duplicate key",)
    assert RAW_SENTINEL not in str(caught.value)


@pytest.mark.usefixtures("drug_in_quote")
def test_a_misspelled_key_is_a_load_error(tmp_path: Path) -> None:
    # L103: a typo'd draft can't turn an injected case into a paid model case
    misspelled = DETECTION.replace("draft:", "drafts:")
    problems = _problems(_write(tmp_path, {"detect-1.yaml": misspelled}))
    assert problems == ("detect-1.yaml: drafts: Extra inputs are not permitted",)


def test_every_file_must_be_an_id_yaml(tmp_path: Path) -> None:
    # L119: a file the loader skipped would be a case that never runs
    _write(tmp_path, {"control-1.yml": CONTROL, "notes.txt": "x"})
    (tmp_path / "more").mkdir()
    (tmp_path / "nested.yaml").mkdir()
    assert _problems(tmp_path) == (
        "control-1.yml: not a case file; each case is <id>.yaml",
        "more: not a case file; each case is <id>.yaml",
        "nested.yaml: not a case file; each case is <id>.yaml",
        "notes.txt: not a case file; each case is <id>.yaml",
    )


# --- how problems read --------------------------------------------------------


@pytest.mark.usefixtures("drug_in_quote")
def test_every_files_problems_are_reported_together(tmp_path: Path) -> None:
    files = {"control-2.yaml": CONTROL, "detect-1.yaml": DETECTION.replace("draft:", "drafts:")}
    assert _problems(_write(tmp_path, files)) == (
        "control-2.yaml: id 'control-1' doesn't match the file name",
        "detect-1.yaml: drafts: Extra inputs are not permitted",
    )


def test_a_validation_problem_names_its_field_never_the_input(tmp_path: Path) -> None:
    # a model-level error's input is the whole case, raw_text and all
    no_key = DETECTION.replace("expected_flags: [drug_in_quote]", "")
    no_key = no_key.replace("Pt with acute sinusitis.", f"Pt with acute sinusitis. {RAW_SENTINEL}")
    with pytest.raises(CaseLoadError) as caught:
        load_cases(_write(tmp_path, {"detect-1.yaml": no_key}))
    assert caught.value.problems == (
        "detect-1.yaml: (case): Value error, detection traps, and only they, carry expected_flags",
    )
    assert RAW_SENTINEL not in str(caught.value)


def test_a_syntax_problem_names_its_line_never_the_text(tmp_path: Path) -> None:
    with pytest.raises(CaseLoadError) as caught:
        load_cases(_write(tmp_path, {"control-1.yaml": UNTERMINATED}))
    (problem,) = caught.value.problems
    # the quote opened on line 4 runs to the end of the stream, line 6
    assert problem == "control-1.yaml: line 6: found unexpected end of stream"
    assert RAW_SENTINEL not in str(caught.value)


def test_a_file_that_isnt_a_mapping_is_a_load_error(tmp_path: Path) -> None:
    assert _problems(_write(tmp_path, {"a.yaml": A_LIST, "b.yaml": ""})) == (
        "a.yaml: (case): Input should be a valid dictionary or instance of EvalCase",
        "b.yaml: (case): Input should be a valid dictionary or instance of EvalCase",
    )


def test_a_file_that_isnt_utf8_is_a_load_error(tmp_path: Path) -> None:
    assert _problems(_write(tmp_path, {"control-1.yaml": bytes([0xFF, 0xFE, 0x00])})) == (
        "control-1.yaml: not UTF-8 text",
    )
