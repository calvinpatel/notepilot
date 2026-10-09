"""Pins extraction's scope engine and extractors.

Spec §7, §11; D1, D10, D12, L31, L33, L120-L135, L140.
"""

import ast
import itertools
import re
import sys
from pathlib import Path

import pytest

from backend.clinical.extract import (
    Dose,
    _phrases,
    extract_allergies,
    extract_diagnoses,
    extract_doses,
    extract_drugs,
    extract_excluded_diagnoses,
    extract_findings,
    extract_med_status,
    new_prescriptions,
)
from backend.clinical.lexicons import (
    ALLERGY_ALIASES,
    ALLERGY_CUES,
    ALLERGY_POST,
    BRAND_TO_GENERIC,
    CERTAINTY_CUES,
    CERTAINTY_POST,
    DIAGNOSES,
    DIAGNOSIS_ALIASES,
    DIFFERENTIAL_CUES,
    DOSE_FREQUENCIES,
    DOSE_UNITS,
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


# --- allergies: context, sections, and lists (D10, L30, L128, L129) ---------------


def test_an_allergy_cue_makes_its_drug_an_allergen_and_no_medication() -> None:
    # §7's case: "allergic to penicillin" mentions a drug and prescribes nothing
    assert extract_allergies("Allergic to amoxicillin.") == {"amoxicillin"}
    assert extract_med_status("Allergic to amoxicillin.") == {}


def test_an_allergen_brand_reads_as_its_generic() -> None:
    # L30: an Augmentin allergy is an amoxicillin-clavulanate allergy
    assert extract_allergies("Augmentin allergy") == {"amoxicillin-clavulanate"}


def test_an_allergy_header_governs_the_list_after_it() -> None:
    assert extract_allergies("Allergies: PCN, sulfa") == {"penicillin", "sulfa"}


def test_an_allergy_section_crosses_semicolons() -> None:
    assert extract_allergies("Allergies: PCN; sulfa; NSAIDs") == {"penicillin", "sulfa", "nsaid"}


VERTICAL = "Allergies:\n- Penicillin (hives)\n- Sulfa (rash)\n\nMeds:\n- Lisinopril 10 mg daily"


@pytest.mark.parametrize("line_break", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_an_allergy_section_reads_a_vertical_list(line_break: str) -> None:
    # L128: by window alone, the line break after the header closed it before the list
    text = VERTICAL.replace("\n", line_break)
    assert extract_allergies(text) == {"penicillin", "sulfa"}
    assert extract_drugs(text) == {"lisinopril"}


def test_a_blank_line_ends_an_allergy_section() -> None:
    text = "Allergies: PCN\n\nLisinopril 10 mg daily"
    assert extract_allergies(text) == {"penicillin"}
    assert extract_drugs(text) == {"lisinopril"}


def test_the_next_header_ends_an_allergy_section() -> None:
    text = "Allergies: penicillin (anaphylaxis)\nMedications: amoxicillin 500 mg tid"
    assert extract_allergies(text) == {"penicillin"}
    assert extract_drugs(text) == {"amoxicillin"}


def test_a_header_after_a_period_ends_an_allergy_section() -> None:
    text = "Allergies: NKDA. Meds: lisinopril 10 mg daily."
    assert extract_allergies(text) == {"nkda"}
    assert extract_drugs(text) == {"lisinopril"}


def test_a_line_starting_with_an_allergen_and_a_colon_is_no_header() -> None:
    text = "Allergies:\nPenicillin: hives\nSulfa: rash"
    assert extract_allergies(text) == {"penicillin", "sulfa"}


def test_an_allergy_header_opens_a_section_only_at_a_lines_start() -> None:
    text = "Pt reports allergies: PCN. Lisinopril 10 mg daily"
    assert extract_allergies(text) == {"penicillin"}
    assert extract_drugs(text) == {"lisinopril"}


def test_only_an_allergy_cue_ending_in_a_colon_opens_a_section() -> None:
    text = "Allergic to penicillin.\nAmoxicillin 500 mg tid"
    assert extract_allergies(text) == {"penicillin"}
    assert extract_drugs(text) == {"amoxicillin"}


def test_an_order_inside_an_allergy_section_still_governs_its_drug() -> None:
    text = "Allergies: PCN\nStart amoxicillin 500 mg tid"
    assert extract_allergies(text) == {"penicillin"}
    assert new_prescriptions(text) == {"amoxicillin"}


def test_a_bare_medication_line_under_an_allergy_header_reads_as_an_allergen() -> None:
    # L128's accepted cost: it fails loud, since allergy_preserved fires on it
    text = "Allergies: PCN\nAmoxicillin 500 mg tid"
    assert extract_allergies(text) == {"penicillin", "amoxicillin"}


@pytest.mark.parametrize(
    ("text", "allergens"),
    [
        ("PCN and sulfa allergies", {"penicillin", "sulfa"}),
        ("PCN, sulfa, and NSAID allergies", {"penicillin", "sulfa", "nsaid"}),
        ("Augmentin/sulfa allergy", {"amoxicillin-clavulanate", "sulfa"}),
    ],
    ids=["and", "commas", "slash"],
)
def test_an_allergy_post_cue_reaches_back_over_a_list(text: str, allergens: set[str]) -> None:
    # L128: one allergen per post-cue read "PCN and sulfa allergies" as sulfa alone
    assert extract_allergies(text) == allergens


def test_a_word_ends_the_list_an_allergy_post_cue_reaches() -> None:
    text = "lisinopril 10 mg daily, sulfa allergy"
    assert extract_allergies(text) == {"sulfa"}
    assert extract_drugs(text) == {"lisinopril"}


def test_an_allergy_list_takes_no_mention_another_cue_governs() -> None:
    text = "start amoxicillin and sulfa allergy"
    assert extract_allergies(text) == {"sulfa"}
    assert new_prescriptions(text) == {"amoxicillin"}


def test_a_list_can_reach_back_into_a_medication() -> None:
    # L128's accepted cost: it fails loud, since allergy_preserved fires on it
    assert extract_allergies("takes lisinopril, sulfa allergy") == {"lisinopril", "sulfa"}


@pytest.mark.parametrize(
    ("text", "statement"),
    [("NKDA", "nkda"), ("No known allergies", "nka"), ("Allergies: none", "nka")],
)
def test_nkda_and_nka_need_no_allergy_cue(text: str, statement: str) -> None:
    # D10: NKDA and NKA are different facts
    assert extract_allergies(text) == {statement}


def test_a_denied_allergy_names_no_allergen() -> None:
    assert extract_allergies("Not allergic to amoxicillin; denies allergy to penicillin") == set()


@pytest.mark.parametrize(
    "text",
    ["no allergies to penicillin", "no known allergies to sulfa", "denies allergies to NSAIDs"],
)
def test_a_denied_allergy_in_the_plural_names_no_allergen_and_no_nka(text: str) -> None:
    # without the plurals, the NKA aliases matched, or "allergies to" replaced the denial
    assert extract_allergies(text) == set()


def test_an_order_cue_closes_an_allergy_window() -> None:
    text = "allergic to amoxicillin, start azithromycin"
    assert extract_allergies(text) == {"amoxicillin"}
    assert new_prescriptions(text) == {"azithromycin"}


# --- doses (D1, L33, L131, L133) -------------------------------------------------


@pytest.mark.parametrize(
    "text", ["Amoxicillin 500 mg TID", "amoxicillin 500mg tid", "AMOXICILLIN 500 MG t.i.d."]
)
def test_parsed_doses_compare_equal_across_spacing_and_case(text: str) -> None:
    # §11's case (L33)
    assert extract_doses(text) == {"amoxicillin": {Dose(500.0, "mg", "tid")}}


def test_a_titration_keeps_both_doses() -> None:
    text = "metformin 500 mg daily, increase to 1000 mg daily"
    assert extract_doses(text) == {
        "metformin": {Dose(500.0, "mg", "daily"), Dose(1000.0, "mg", "daily")}
    }


def test_a_frequency_reaches_no_further_than_the_next_dose() -> None:
    text = "metformin 500 mg, increase to 1000 mg bid"
    assert extract_doses(text) == {
        "metformin": {Dose(500.0, "mg", None), Dose(1000.0, "mg", "bid")}
    }


def test_a_dose_belongs_to_the_most_recent_drug_before_it() -> None:
    assert extract_doses("metformin 500 mg and lisinopril 10 mg daily") == {
        "metformin": {Dose(500.0, "mg", None)},
        "lisinopril": {Dose(10.0, "mg", "daily")},
    }


@pytest.mark.parametrize("text", ["Tylenol 1,000 mg q6h", "Tylenol 1,000mg q6h"])
def test_a_thousands_comma_joins_the_number(text: str) -> None:
    # with the unit fused, "000mg" alone once read as a zero dose
    assert extract_doses(text) == {"acetaminophen": {Dose(1000.0, "mg", "q6h")}}


def test_a_terminator_ends_a_doses_reach_for_a_frequency() -> None:
    assert extract_doses("lisinopril 10 mg; daily") == {"lisinopril": {Dose(10.0, "mg", None)}}


def test_a_dose_takes_its_drug_whatever_the_drugs_status() -> None:
    assert extract_doses("discontinue lisinopril 10 mg") == {"lisinopril": {Dose(10.0, "mg", None)}}


def test_a_unit_is_canonical_but_never_converted() -> None:
    # whether 1 g equals 1000 mg is dose_consistency's call (4c)
    text = "acetaminophen 1 g every 6 hours"
    assert extract_doses(text) == {"acetaminophen": {Dose(1.0, "g", "q6h")}}


def test_a_micro_sign_reads_as_mu() -> None:
    # the micro sign, U+00B5, casefolds to the Greek mu the table holds
    assert extract_doses("metformin 75 µg daily") == {"metformin": {Dose(75.0, "μg", "daily")}}


@pytest.mark.parametrize("text", ["acetaminophen 650 mg q6h prn", "acetaminophen 650 mg prn q6h"])
def test_prn_yields_to_an_interval_in_either_order(text: str) -> None:
    assert extract_doses(text) == {"acetaminophen": {Dose(650.0, "mg", "q6h")}}


def test_prn_is_the_frequency_when_no_interval_is_charted() -> None:
    text = "acetaminophen 650 mg as needed"
    assert extract_doses(text) == {"acetaminophen": {Dose(650.0, "mg", "prn")}}


@pytest.mark.parametrize(
    "text",
    [
        "acetaminophen 5-10 mg q4h",
        "acetaminophen 5 to 10 mg q4h",
        "acetaminophen 5mg-10mg q4h",
        "acetaminophen 5 mg - 10 mg q4h",
    ],
)
def test_a_range_reads_as_no_dose(text: str) -> None:
    # so a range changed to a fixed dose still differs from its source (L133)
    assert extract_doses(text) == {}


def test_a_hyphen_before_a_number_without_a_unit_joins_no_range() -> None:
    text = "lisinopril 10 mg - 1 tab daily"
    assert extract_doses(text) == {"lisinopril": {Dose(10.0, "mg", "daily")}}


@pytest.mark.parametrize(
    "text", ["metformin from 500 mg to 1000 mg daily", "metformin from 500mg to 1000mg daily"]
)
def test_two_doses_joined_by_to_are_a_titration(text: str) -> None:
    # "to" joins a range only after a number without a unit (L133)
    assert extract_doses(text) == {
        "metformin": {Dose(500.0, "mg", None), Dose(1000.0, "mg", "daily")}
    }


@pytest.mark.parametrize("text", ["metformin 500", "metformin 1,000 daily"])
def test_a_number_without_a_unit_is_no_dose(text: str) -> None:
    assert extract_doses(text) == {}


def test_a_dose_before_its_drug_reads_as_nothing() -> None:
    # L133's accepted cost
    assert extract_doses("500 mg of amoxicillin") == {}


def test_a_dose_in_the_next_sentence_reads_as_nothing() -> None:
    # L133's accepted cost
    text = "Metformin 500 mg daily. Increase to 1000 mg daily next week."
    assert extract_doses(text) == {"metformin": {Dose(500.0, "mg", "daily")}}


# --- diagnoses, certainty, and exclusions (D7, D12, L134, L135, L140) ------------


def test_a_diagnosis_no_cue_governs_is_definite() -> None:
    assert extract_diagnoses("hypertensive urgency") == {"hypertensive urgency": {"definite"}}


def test_a_rule_out_and_its_upgrade_read_apart() -> None:
    # D12's trap: "r/o PE" written as "PE"
    assert extract_diagnoses("r/o PE") == {"pulmonary embolism": {"rule_out"}}
    assert extract_diagnoses("PE") == {"pulmonary embolism": {"definite"}}


@pytest.mark.parametrize("text", ["likely pneumonia", "pneumonia likely"])
def test_a_certainty_cue_governs_before_or_after_its_diagnosis(text: str) -> None:
    assert extract_diagnoses(text) == {"pneumonia": {"probable"}}


@pytest.mark.parametrize("text", ["PE ruled out", "no pneumonia", "negative for PE"])
def test_a_negated_diagnosis_is_not_asserted(text: str) -> None:
    # "PE ruled out" says it was excluded; "rule out PE" is a plan to exclude it
    assert extract_diagnoses(text) == {}


@pytest.mark.parametrize(
    ("text", "excluded"),
    [
        ("PE ruled out", {"pulmonary embolism"}),
        ("no pneumonia", {"pneumonia"}),
        ("negative for PE", {"pulmonary embolism"}),
    ],
    ids=["ruled-out", "no", "negative-for"],
)
def test_a_negated_diagnosis_is_excluded(text: str, excluded: set[str]) -> None:
    # L140: the mentions extract_diagnoses drops, read beside it
    assert extract_excluded_diagnoses(text) == excluded


@pytest.mark.parametrize(
    "text", ["r/o PE", "PE", "likely PE", "cannot rule out PE", "PE not ruled out", "PNA vs PE"]
)
def test_a_diagnosis_asserted_at_any_certainty_is_not_excluded(text: str) -> None:
    assert extract_excluded_diagnoses(text) == set()


def test_a_rule_out_and_its_result_read_apart_in_one_statement() -> None:
    # the workup and its answer: to be excluded, then excluded
    text = "r/o PE; CTA negative, PE ruled out"
    assert extract_diagnoses(text) == {"pulmonary embolism": {"rule_out"}}
    assert extract_excluded_diagnoses(text) == {"pulmonary embolism"}


@pytest.mark.parametrize("text", ["cannot rule out PE", "PE not ruled out"])
def test_a_diagnosis_not_excluded_is_possible(text: str) -> None:
    assert extract_diagnoses(text) == {"pulmonary embolism": {"possible"}}


@pytest.mark.parametrize("text", ["PNA vs PE", "pneumonia versus pulmonary embolism"])
def test_a_differential_cue_governs_both_its_sides(text: str) -> None:
    # L135: as a pre-cue alone, "PNA vs PE" read pneumonia as definite
    assert extract_diagnoses(text) == {
        "pneumonia": {"possible"},
        "pulmonary embolism": {"possible"},
    }


def test_a_differential_cue_leaves_a_governed_diagnosis_before_it() -> None:
    text = "likely PNA vs PE"
    assert extract_diagnoses(text) == {
        "pneumonia": {"probable"},
        "pulmonary embolism": {"possible"},
    }


def test_a_comma_keeps_a_certainty_cue_off_the_diagnosis_before_it() -> None:
    text = "PE, likely pneumonia"
    assert extract_diagnoses(text) == {
        "pulmonary embolism": {"definite"},
        "pneumonia": {"probable"},
    }


def test_a_vital_sign_names_no_diagnosis() -> None:
    # D7 and D12's trap: "BP 190/110" written as "hypertensive urgency"
    assert extract_diagnoses("BP 190/110") == {}


def test_an_exam_header_reads_as_pulmonary_embolism() -> None:
    # L134's accepted cost: "PE" also charts the physical exam
    text = "PE: lungs clear, no edema"
    assert extract_diagnoses(text) == {"pulmonary embolism": {"definite"}}


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


@pytest.mark.parametrize("cue", sorted(ALLERGY_CUES))
def test_every_allergy_cue_makes_the_drug_after_it_an_allergen(cue: str) -> None:
    assert extract_allergies(f"{cue} amoxicillin") == {"amoxicillin"}


@pytest.mark.parametrize("cue", sorted(ALLERGY_POST))
def test_every_post_allergy_cue_makes_the_drug_before_it_an_allergen(cue: str) -> None:
    assert extract_allergies(f"amoxicillin {cue}") == {"amoxicillin"}


@pytest.mark.parametrize(("name", "key"), sorted(ALLERGY_ALIASES.items()))
def test_every_allergen_name_means_its_class_or_statement(name: str, key: str) -> None:
    # L129: a class needs an allergy cue; NKDA and NKA are allergy statements by themselves
    text = name if key in {"nkda", "nka"} else f"{name} allergy"
    assert extract_allergies(text) == {key}


def test_allergen_names_mean_classes_and_d10s_statements_never_a_listed_drug() -> None:
    # L129: a drug's other names belong in BRAND_TO_GENERIC
    assert not set(ALLERGY_ALIASES.values()) & GENERIC_DRUGS
    assert {"nkda", "nka"} <= set(ALLERGY_ALIASES.values())


@pytest.mark.parametrize(("name", "unit"), sorted(DOSE_UNITS.items()))
def test_every_dose_unit_reads_as_its_canonical_unit(name: str, unit: str) -> None:
    assert extract_doses(f"metformin 5 {name}") == {"metformin": {Dose(5.0, unit, None)}}


@pytest.mark.parametrize(("name", "freq"), sorted(DOSE_FREQUENCIES.items()))
def test_every_frequency_reads_as_its_canonical_frequency(name: str, freq: str) -> None:
    assert extract_doses(f"metformin 5 mg {name}") == {"metformin": {Dose(5.0, "mg", freq)}}


@pytest.mark.parametrize("diagnosis", sorted(DIAGNOSES))
def test_every_diagnosis_extracts_as_itself(diagnosis: str) -> None:
    assert extract_diagnoses(diagnosis) == {diagnosis: {"definite"}}


@pytest.mark.parametrize(("name", "diagnosis"), sorted(DIAGNOSIS_ALIASES.items()))
def test_every_other_diagnosis_name_extracts_as_its_diagnosis(name: str, diagnosis: str) -> None:
    assert extract_diagnoses(name) == {diagnosis: {"definite"}}


def test_every_other_diagnosis_name_means_a_listed_diagnosis_and_none_is_one() -> None:
    # L134: DIAGNOSES is the vocabulary, and DIAGNOSIS_ALIASES maps onto it
    assert set(DIAGNOSIS_ALIASES.values()) <= DIAGNOSES
    assert not DIAGNOSES & set(DIAGNOSIS_ALIASES)


@pytest.mark.parametrize(("cue", "certainty"), sorted(CERTAINTY_CUES.items()))
def test_every_certainty_cue_governs_the_diagnosis_after_it(cue: str, certainty: str) -> None:
    assert extract_diagnoses(f"{cue} pneumonia") == {"pneumonia": {certainty}}


@pytest.mark.parametrize(("cue", "certainty"), sorted(CERTAINTY_POST.items()))
def test_every_post_certainty_cue_governs_the_diagnosis_before_it(cue: str, certainty: str) -> None:
    assert extract_diagnoses(f"pneumonia {cue}") == {"pneumonia": {certainty}}


@pytest.mark.parametrize(("cue", "certainty"), sorted(DIFFERENTIAL_CUES.items()))
def test_every_differential_cue_governs_both_its_sides(cue: str, certainty: str) -> None:
    text = f"pneumonia {cue} pulmonary embolism"
    assert extract_diagnoses(text) == {"pneumonia": {certainty}, "pulmonary embolism": {certainty}}


@pytest.mark.parametrize("cue", sorted(FINDING_NEG_PRE))
def test_every_pre_negation_cue_negates_the_diagnosis_after_it(cue: str) -> None:
    assert extract_diagnoses(f"{cue} pneumonia") == {}


@pytest.mark.parametrize("cue", sorted(FINDING_NEG_POST))
def test_every_post_negation_cue_negates_the_diagnosis_before_it(cue: str) -> None:
    assert extract_diagnoses(f"pneumonia {cue}") == {}


@pytest.mark.parametrize("cue", sorted(FINDING_NEG_PRE))
def test_every_pre_negation_cue_excludes_the_diagnosis_after_it(cue: str) -> None:
    assert extract_excluded_diagnoses(f"{cue} pneumonia") == {"pneumonia"}


@pytest.mark.parametrize("cue", sorted(FINDING_NEG_POST))
def test_every_post_negation_cue_excludes_the_diagnosis_before_it(cue: str) -> None:
    assert extract_excluded_diagnoses(f"pneumonia {cue}") == {"pneumonia"}


@pytest.mark.parametrize("cue", sorted(MED_START_CUES))
def test_every_start_cue_starts_the_drug_after_it(cue: str) -> None:
    assert extract_med_status(f"{cue} metformin") == {"metformin": {"active"}}
    assert new_prescriptions(f"{cue} metformin") == {"metformin"}


@pytest.mark.parametrize("cue", sorted(MED_START_POST))
def test_every_post_start_cue_starts_the_drug_before_it(cue: str) -> None:
    assert extract_med_status(f"metformin {cue}") == {"metformin": {"active"}}
    assert new_prescriptions(f"metformin {cue}") == {"metformin"}


def test_a_phrase_has_one_role_unless_it_is_a_pre_and_post_cue_of_one_class() -> None:
    # longest-first matching gives a phrase one role; L121 rules on a class's pre/post pair
    roles = {
        "finding": FINDINGS,
        "drug": GENERIC_DRUGS | set(BRAND_TO_GENERIC),
        "allergen": set(ALLERGY_ALIASES),
        "allergy": ALLERGY_CUES,
        "allergy, post": ALLERGY_POST,
        "dose unit": set(DOSE_UNITS),
        "frequency": set(DOSE_FREQUENCIES),
        "diagnosis": DIAGNOSES | set(DIAGNOSIS_ALIASES),
        "certainty": set(CERTAINTY_CUES),
        "certainty, post": set(CERTAINTY_POST),
        "differential": set(DIFFERENTIAL_CUES),
        "negation": FINDING_NEG_PRE,
        "negation, post": FINDING_NEG_POST,
        "stop": MED_STOP_CUES,
        "stop, post": MED_STOP_POST,
        "start": MED_START_CUES,
        "start, post": MED_START_POST,
        "pseudo": PSEUDO_NEGATIONS,
        "terminator": TERMINATORS,
    }
    pairs = [
        {"negation", "negation, post"},
        {"stop", "stop, post"},
        {"start", "start, post"},
        {"allergy", "allergy, post"},
        {"certainty", "certainty, post"},
    ]
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
