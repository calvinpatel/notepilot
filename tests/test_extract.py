"""Pins extraction's scope engine and its extractors (spec §7, §11; L31, L33, L120-L126)."""

import ast
import itertools
import re
import sys
from pathlib import Path

import pytest

from backend.clinical.extract import (
    _phrases,
    extract_drugs,
    extract_findings,
    extract_med_status,
    new_prescriptions,
)
from backend.clinical.lexicons import (
    BRAND_TO_GENERIC,
    FINDING_NEG_POST,
    FINDING_NEG_PRE,
    FINDINGS,
    GENERIC_DRUGS,
    MED_START_CUES,
    MED_START_POST,
    MED_STOP_CUES,
    MED_STOP_POST,
    NEGATION_WINDOW,
    PSEUDO_NEGATIONS,
    TERMINATORS,
)

_CLINICAL = Path(__file__).resolve().parents[1] / "backend" / "clinical"

# --- §7's four scope cases (L31), and a mixed finding (L33) ----------------------


def test_a_terminator_closes_the_window() -> None:
    assert extract_findings("no fever, but reports chest pain") == {
        "fever": {False},
        "chest pain": {True},
    }


def test_a_pseudo_negation_suppresses_its_cue() -> None:
    assert extract_findings("no increase in pain") == {"pain": {True}}


def test_a_post_cue_negates_the_finding_before_it_across_a_mark() -> None:
    assert extract_findings("chest pain: denied") == {"chest pain": {False}}


@pytest.mark.parametrize("text", ["runny nose and fever", "does she know about the fever"])
def test_a_cue_matches_whole_words_only(text: str) -> None:
    # "nose" and "know" contain "no"
    assert extract_findings(text) == {"fever": {True}}


def test_a_mixed_statement_keeps_both_polarities() -> None:
    text = "denies chest pain at rest, reports chest pain on exertion"
    assert extract_findings(text) == {"chest pain": {False, True}}


# --- the window (L121) -----------------------------------------------------------


def _fever_after(filler: int) -> str:
    """'denies', filler words, then 'fever': fever is word filler + 1 after the cue."""
    return " ".join(["denies", *["word"] * filler, "fever"])


def test_a_pre_cue_governs_a_finding_starting_at_its_windows_last_word() -> None:
    assert extract_findings(_fever_after(NEGATION_WINDOW - 1)) == {"fever": {False}}


def test_a_pre_cue_doesnt_reach_past_its_window() -> None:
    assert extract_findings(_fever_after(NEGATION_WINDOW)) == {"fever": {True}}


def test_punctuation_spends_none_of_the_window() -> None:
    text = "denies" + " word," * (NEGATION_WINDOW - 1) + " fever"
    assert extract_findings(text) == {"fever": {False}}


def test_the_window_rationales_list_is_negated_to_its_last_item() -> None:
    text = "denies fever, chills, nausea, vomiting, diarrhea, headache, or chest pain"
    negated = ["fever", "chills", "nausea", "vomiting", "chest pain"]
    assert extract_findings(text) == {finding: {False} for finding in negated}


# --- post-cues: adjacency, and the cue in both classes (L121, L122) ---------------


def test_a_post_cue_negates_one_finding_not_the_list_before_it() -> None:
    # §7: "the finding immediately before it"
    assert extract_findings("fever, chills, and nausea denied") == {
        "fever": {True},
        "chills": {True},
        "nausea": {False},
    }


def test_a_word_between_a_finding_and_a_post_cue_breaks_adjacency() -> None:
    assert extract_findings("chest pain today: absent") == {"chest pain": {True}}


def test_a_terminator_between_a_finding_and_a_post_cue_breaks_adjacency() -> None:
    assert extract_findings("chest pain; absent") == {"chest pain": {True}}


def test_a_comma_between_a_finding_and_a_post_cue_breaks_adjacency() -> None:
    # L122: past a comma, a post-cue belongs to the clause that follows it
    assert extract_findings("chest pain, absent") == {"chest pain": {True}}


def test_a_cue_in_both_classes_is_a_pre_cue_with_no_finding_before_it() -> None:
    assert extract_findings("pt denied chest pain") == {"chest pain": {False}}


def test_a_cue_in_both_classes_is_a_pre_cue_after_a_comma() -> None:
    assert extract_findings("endorses chest pain, denied fever") == {
        "chest pain": {True},
        "fever": {False},
    }


def test_a_cue_in_both_classes_is_only_a_post_cue_after_a_finding() -> None:
    assert extract_findings("chest pain denied, fever") == {
        "chest pain": {False},
        "fever": {True},
    }


def test_a_spent_post_cue_leaves_the_next_cue_free() -> None:
    assert extract_findings("fever absent, denied chest pain") == {
        "fever": {False},
        "chest pain": {False},
    }


# --- tokens (L121, L123) ---------------------------------------------------------


def test_matching_ignores_case() -> None:
    assert extract_findings("DENIES Fever") == {"fever": {False}}


def test_a_decimal_number_is_one_word() -> None:
    # so its point ends no sentence
    assert extract_findings("no fever for 2.5 days or chills") == {
        "fever": {False},
        "chills": {False},
    }


def test_a_slash_separates_two_words() -> None:
    assert extract_findings("denies fever/chills") == {"fever": {False}, "chills": {False}}


@pytest.mark.parametrize(
    ("text", "expected"),
    [("chest_pain", {"chest pain": {True}}), ("denies___fever", {"fever": {False}})],
    ids=["joined", "blank"],
)
def test_an_underscore_separates_words_as_whitespace_does(
    text: str, expected: dict[str, set[bool]]
) -> None:
    # L123: neither a word nor a mark, so it spends no window
    assert extract_findings(text) == expected


def test_the_longest_finding_matches() -> None:
    assert extract_findings("denies chest pain") == {"chest pain": {False}}


@pytest.mark.parametrize("text", ["", "feverish", "pt seen today"])
def test_text_naming_no_finding_extracts_nothing(text: str) -> None:
    assert extract_findings(text) == {}


@pytest.mark.parametrize("line_break", ["\n", "\r\n", "\r"], ids=["lf", "crlf", "cr"])
def test_a_line_break_of_each_kind_reads_as_one(line_break: str) -> None:
    text = f"denies fever{line_break}chills"
    assert extract_findings(text) == {"fever": {False}, "chills": {True}}


# --- drugs: status, active mentions, and starts (D13, L41, L124-L126) -------------


def test_a_drug_no_cue_governs_is_active() -> None:
    # §7's example: "continue" asserts the default
    assert extract_med_status("continue apixaban") == {"apixaban": {"active"}}


def test_a_stop_cue_before_a_drug_stops_it() -> None:
    assert extract_med_status("discontinue apixaban") == {"apixaban": {"stopped"}}


def test_a_stop_cue_after_a_drug_stops_it() -> None:
    # L125: the common charting puts the stop after the drug
    text = "Lisinopril discontinued due to cough"
    assert extract_med_status(text) == {"lisinopril": {"stopped"}}


def test_the_latest_pre_cue_governs() -> None:
    text = "stop metformin and start lisinopril"
    assert extract_med_status(text) == {"metformin": {"stopped"}, "lisinopril": {"active"}}
    assert new_prescriptions(text) == {"lisinopril"}


def test_each_order_in_a_list_governs_its_own_drug() -> None:
    text = "Continued lisinopril, held metformin, started apixaban"
    assert extract_med_status(text) == {
        "lisinopril": {"active"},
        "metformin": {"stopped"},
        "apixaban": {"active"},
    }
    assert new_prescriptions(text) == {"apixaban"}


def test_a_continued_order_closes_a_stop_window() -> None:
    assert extract_med_status("stop metformin, continue lisinopril") == {
        "metformin": {"stopped"},
        "lisinopril": {"active"},
    }


def test_a_refused_stop_leaves_the_drug_active() -> None:
    assert extract_med_status("do not stop apixaban") == {"apixaban": {"active"}}


def test_a_refused_start_leaves_the_drug_stopped_and_not_started() -> None:
    assert extract_med_status("do not start metformin") == {"metformin": {"stopped"}}
    assert new_prescriptions("do not start metformin") == set()


def test_a_negated_drug_is_stopped_and_not_active() -> None:
    # L124: "not on apixaban" asserts the drug isn't taken
    assert extract_med_status("pt not on apixaban") == {"apixaban": {"stopped"}}
    assert extract_drugs("pt not on apixaban") == set()


def test_a_drug_with_any_active_mention_is_active() -> None:
    text = "stop lisinopril. lisinopril 10 mg daily"
    assert extract_med_status(text) == {"lisinopril": {"stopped", "active"}}
    assert extract_drugs(text) == {"lisinopril"}


def test_a_brand_reads_as_its_generic() -> None:
    assert new_prescriptions("start Augmentin 875 mg bid") == {"amoxicillin-clavulanate"}


def test_the_longest_drug_name_matches() -> None:
    assert extract_drugs("amoxicillin-clavulanate 875 mg") == {"amoxicillin-clavulanate"}


@pytest.mark.parametrize("text", ["mom takes metformin", "tried ibuprofen last year"])
def test_a_mention_no_start_cue_governs_is_no_new_prescription(text: str) -> None:
    # §7's examples: the drug reads active, but nothing started it
    assert new_prescriptions(text) == set()
    assert extract_drugs(text) != set()


def test_a_narrative_start_counts_however_old_it_is() -> None:
    # L125's accepted cost, which lands on a WARNING
    assert new_prescriptions("metformin was started in 2019") == {"metformin"}


# --- every lexicon entry, in its role --------------------------------------------


@pytest.mark.parametrize("finding", sorted(FINDINGS))
def test_every_finding_extracts_as_itself(finding: str) -> None:
    assert extract_findings(finding) == {finding: {True}}


@pytest.mark.parametrize("cue", sorted(FINDING_NEG_PRE))
def test_every_pre_cue_negates_the_finding_after_it(cue: str) -> None:
    assert extract_findings(f"{cue} fever") == {"fever": {False}}


@pytest.mark.parametrize("cue", sorted(FINDING_NEG_POST))
def test_every_post_cue_negates_the_finding_before_it(cue: str) -> None:
    assert extract_findings(f"fever {cue}") == {"fever": {False}}


@pytest.mark.parametrize("pseudo", sorted(PSEUDO_NEGATIONS))
def test_every_pseudo_negation_suppresses_its_cue(pseudo: str) -> None:
    assert extract_findings(f"{pseudo} fever") == {"fever": {True}}


@pytest.mark.parametrize("terminator", sorted(TERMINATORS))
def test_every_terminator_closes_the_window(terminator: str) -> None:
    assert extract_findings(f"denies {terminator} fever") == {"fever": {True}}


@pytest.mark.parametrize("drug", sorted(GENERIC_DRUGS))
def test_every_drug_extracts_as_itself(drug: str) -> None:
    assert extract_med_status(drug) == {drug: {"active"}}


@pytest.mark.parametrize(("name", "drug"), sorted(BRAND_TO_GENERIC.items()))
def test_every_other_name_extracts_as_its_generic(name: str, drug: str) -> None:
    assert extract_med_status(name) == {drug: {"active"}}


def test_every_other_name_means_a_listed_drug_and_none_is_one() -> None:
    # L126: GENERIC_DRUGS is the vocabulary, and BRAND_TO_GENERIC maps onto it
    assert set(BRAND_TO_GENERIC.values()) <= GENERIC_DRUGS
    assert not GENERIC_DRUGS & set(BRAND_TO_GENERIC)


@pytest.mark.parametrize("cue", sorted(FINDING_NEG_PRE | MED_STOP_CUES))
def test_every_negation_or_stop_cue_stops_the_drug_after_it(cue: str) -> None:
    assert extract_med_status(f"{cue} metformin") == {"metformin": {"stopped"}}


@pytest.mark.parametrize("cue", sorted(FINDING_NEG_POST | MED_STOP_POST))
def test_every_post_negation_or_stop_cue_stops_the_drug_before_it(cue: str) -> None:
    assert extract_med_status(f"metformin {cue}") == {"metformin": {"stopped"}}


@pytest.mark.parametrize("cue", sorted(MED_START_CUES))
def test_every_start_cue_starts_the_drug_after_it(cue: str) -> None:
    assert extract_med_status(f"{cue} metformin") == {"metformin": {"active"}}
    assert new_prescriptions(f"{cue} metformin") == {"metformin"}


@pytest.mark.parametrize("cue", sorted(MED_START_POST))
def test_every_post_start_cue_starts_the_drug_before_it(cue: str) -> None:
    assert extract_med_status(f"metformin {cue}") == {"metformin": {"active"}}
    assert new_prescriptions(f"metformin {cue}") == {"metformin"}


def test_a_phrase_has_one_role_unless_it_is_one_classs_pre_and_post_cue() -> None:
    # longest-first matching gives a phrase one role; L121 rules on a class's pre/post pair
    roles = {
        "finding": FINDINGS,
        "drug": GENERIC_DRUGS | set(BRAND_TO_GENERIC),
        "negation": FINDING_NEG_PRE,
        "negation, post": FINDING_NEG_POST,
        "stop": MED_STOP_CUES,
        "stop, post": MED_STOP_POST,
        "start": MED_START_CUES,
        "start, post": MED_START_POST,
        "pseudo": PSEUDO_NEGATIONS,
        "terminator": TERMINATORS,
    }
    pairs = [{"negation", "negation, post"}, {"stop", "stop, post"}, {"start", "start, post"}]
    shared = {
        (a, b, phrase)
        for (a, x), (b, y) in itertools.combinations(roles.items(), 2)
        if {a, b} not in pairs
        for phrase in _phrases(x).keys() & _phrases(y).keys()
    }
    assert shared == set()


# --- the module boundary (invariant 13) and the sign-off's form (L120) ------------


def _imports(path: Path) -> set[str]:
    """Every module path names in an import; a relative import keeps its dots."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add("." * node.level + (node.module or ""))
    return names


def test_lexicons_imports_nothing() -> None:
    assert _imports(_CLINICAL / "lexicons.py") == set()


def test_clinical_imports_nothing_but_the_standard_library_and_lexicons() -> None:
    outside = {
        (path.name, name)
        for path in sorted(_CLINICAL.rglob("*.py"))
        for name in _imports(path)
        if name.split(".")[0] not in sys.stdlib_module_names and name != "backend.clinical.lexicons"
    }
    assert outside == set()


_SIGN_OFF = re.compile(r"# Clinical sign-off: [^,]+, [0-9]{4}-[0-9]{2}-[0-9]{2}[.]")


def test_each_table_is_signed_off_and_each_entry_carries_its_rationale() -> None:
    source = (_CLINICAL / "lexicons.py").read_text(encoding="utf-8")
    lines = source.splitlines()
    body = ast.parse(source).body
    assert not [node for node in body if isinstance(node, ast.Assign)]  # each table annotated
    tables = [node for node in body if isinstance(node, ast.AnnAssign)]
    assert tables
    for table in tables:
        name = ast.unparse(table.target)
        top = table.lineno - 1  # the table's own line; walk up through its comment block
        while top > 0 and lines[top - 1].startswith("#"):
            top -= 1
        assert _SIGN_OFF.fullmatch(lines[top]), name
        if isinstance(table.value, ast.Set):
            for entry in table.value.elts:
                assert lines[entry.lineno - 2].lstrip().startswith("#"), ast.unparse(entry)
        elif isinstance(table.value, ast.Dict):
            for key in table.value.keys:
                assert key is not None, name  # no ** unpacking
                assert lines[key.lineno - 2].lstrip().startswith("#"), ast.unparse(key)
        else:
            assert isinstance(table.value, ast.Constant), name
            assert table.lineno - 1 - top >= 2, name  # the sign-off line, then a rationale
