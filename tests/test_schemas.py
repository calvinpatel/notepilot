"""Pins the spine types (spec §4.1, §4.2; L6, L9, L25, L42, L43, L86, L89, L102, L103).

Rejection tests validate a dict through model_validate — the §5.4 entry point
(L12) — and pin the single error's type and loc, so no test passes on an
unrelated error. Strings are synthetic.
"""

import pytest
from pydantic import ValidationError

from backend.schemas import (
    ClaimDraft,
    ClinicalClaim,
    EvalCase,
    EvalReport,
    EvalResult,
    RunMetadata,
    SafetyFlag,
    Severity,
    SOAPNote,
    SOAPNoteDraft,
    TokenUsage,
)

BLANK = ("", "   ", "\n\t")


def _claim(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {"text": "fact-1", "section": "S", "source_quote": "quote-1"}
    return {**base, **overrides}


# --- extra="forbid" (§4.1, §5.4 retry) -----------------------------------------


def test_claim_draft_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError) as exc:
        ClaimDraft.model_validate(_claim(bogus=1))
    (err,) = exc.value.errors()
    assert err["type"] == "extra_forbidden"
    assert err["loc"] == ("bogus",)


def test_soap_note_draft_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError) as exc:
        SOAPNoteDraft.model_validate({"claims": [], "bogus": 1})
    (err,) = exc.value.errors()
    assert err["type"] == "extra_forbidden"
    assert err["loc"] == ("bogus",)


# --- NonBlankStr: stripped, non-empty (L86 text, L25 quote) --------------------


@pytest.mark.parametrize("value", BLANK)
def test_text_rejects_blank(value: str) -> None:
    with pytest.raises(ValidationError) as exc:
        ClaimDraft.model_validate(_claim(text=value))
    (err,) = exc.value.errors()
    assert err["type"] == "string_too_short"
    assert err["loc"] == ("text",)


@pytest.mark.parametrize("value", BLANK)
def test_source_quote_rejects_blank(value: str) -> None:
    with pytest.raises(ValidationError) as exc:
        ClaimDraft.model_validate(_claim(source_quote=value))
    (err,) = exc.value.errors()
    assert err["type"] == "string_too_short"
    assert err["loc"] == ("source_quote",)


def test_text_is_stripped() -> None:
    assert ClaimDraft(text="  x  ", section="S", source_quote="quote-1").text == "x"


def test_source_quote_is_stripped() -> None:
    assert ClaimDraft(text="fact-1", section="S", source_quote="  x  ").source_quote == "x"


# --- Section literal (§4.1) ----------------------------------------------------


@pytest.mark.parametrize("letter", ["S", "O", "A", "P"])
def test_section_accepts_each_letter(letter: str) -> None:
    assert ClaimDraft.model_validate(_claim(section=letter)).section == letter


@pytest.mark.parametrize("value", ["s", "X", ""])
def test_section_rejects_other_values(value: str) -> None:
    with pytest.raises(ValidationError) as exc:
        ClaimDraft.model_validate(_claim(section=value))
    (err,) = exc.value.errors()
    assert err["type"] == "literal_error"
    assert err["loc"] == ("section",)


# --- the empty note is valid (§4.1) --------------------------------------------


def test_soap_note_draft_allows_empty_claims() -> None:
    assert SOAPNoteDraft(claims=[]).claims == []


# --- TokenUsage (L89) ----------------------------------------------------------


def test_token_usage_defaults_to_zero() -> None:
    usage = TokenUsage()
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
def test_token_usage_rejects_negative(field: str) -> None:
    with pytest.raises(ValidationError) as exc:
        TokenUsage.model_validate({field: -1})
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than_equal"
    assert err["loc"] == (field,)


def test_token_usage_rejects_attribute_assignment() -> None:
    usage = TokenUsage()
    with pytest.raises(ValidationError) as exc:
        usage.input_tokens = 5  # type: ignore[misc]
    (err,) = exc.value.errors()
    assert err["type"] == "frozen_instance"
    assert err["loc"] == ("input_tokens",)


def test_token_usage_add_sums_fieldwise_and_leaves_operands_unchanged() -> None:
    a = TokenUsage(input_tokens=1, output_tokens=2)
    b = TokenUsage(input_tokens=10, output_tokens=20)
    assert a + b == TokenUsage(input_tokens=11, output_tokens=22)
    assert a == TokenUsage(input_tokens=1, output_tokens=2)
    assert b == TokenUsage(input_tokens=10, output_tokens=20)


def test_token_usage_iadd_rebinds_to_new_object() -> None:
    u = TokenUsage(input_tokens=1, output_tokens=2)
    original = u
    u += TokenUsage(input_tokens=10, output_tokens=20)
    assert u is not original
    assert u == TokenUsage(input_tokens=11, output_tokens=22)
    assert original == TokenUsage(input_tokens=1, output_tokens=2)


# --- RunMetadata.validation_attempts >= 1 (L13, L89) ---------------------------


def _metadata(attempts: int) -> dict[str, object]:
    return {
        "model": "model-id-1",
        "prompt_version": "prompt-hash-1",
        "usage": {"input_tokens": 1, "output_tokens": 1},
        "validation_attempts": attempts,
    }


def test_run_metadata_rejects_zero_validation_attempts() -> None:
    with pytest.raises(ValidationError) as exc:
        RunMetadata.model_validate(_metadata(0))
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than_equal"
    assert err["loc"] == ("validation_attempts",)


def test_run_metadata_accepts_one_validation_attempt() -> None:
    assert RunMetadata.model_validate(_metadata(1)).validation_attempts == 1


# --- the grounded claim and note (§4.1; D6, L6) ---------------------------------


def _grounded(**overrides: object) -> dict[str, object]:
    return _claim(**{"id": 0, **overrides})


def test_safety_flag_wire_values() -> None:
    assert [flag.value for flag in SafetyFlag] == ["unsupported", "paraphrased"]


def test_clinical_claim_defaults_to_no_span_no_score_no_flags() -> None:
    claim = ClinicalClaim.model_validate(_grounded())
    assert claim.source_span is None
    assert claim.grounding_score is None
    assert claim.flags == ()


def test_clinical_claim_requires_id() -> None:
    # a pipeline that skips grounding cannot construct the enriched claim (§4.1)
    with pytest.raises(ValidationError) as exc:
        ClinicalClaim.model_validate(_claim())
    (err,) = exc.value.errors()
    assert err["type"] == "missing"
    assert err["loc"] == ("id",)


def test_clinical_claim_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError) as exc:
        ClinicalClaim.model_validate(_grounded(bogus=1))
    (err,) = exc.value.errors()
    assert err["type"] == "extra_forbidden"
    assert err["loc"] == ("bogus",)


@pytest.mark.parametrize("value", BLANK)
def test_clinical_claim_rejects_blank_quote(value: str) -> None:
    # the enriched claim keeps the boundary's constraint (L25)
    with pytest.raises(ValidationError) as exc:
        ClinicalClaim.model_validate(_grounded(source_quote=value))
    (err,) = exc.value.errors()
    assert err["type"] == "string_too_short"
    assert err["loc"] == ("source_quote",)


def test_clinical_claim_rejects_attribute_assignment() -> None:
    claim = ClinicalClaim.model_validate(_grounded())
    with pytest.raises(ValidationError) as exc:
        claim.flags = (SafetyFlag.UNSUPPORTED,)  # type: ignore[misc]
    (err,) = exc.value.errors()
    assert err["type"] == "frozen_instance"
    assert err["loc"] == ("flags",)


def test_clinical_claim_flags_are_a_tuple_even_from_a_list() -> None:
    # L6: frozen alone leaves a list appendable; the tuple leaves nothing to append to
    claim = ClinicalClaim.model_validate(_grounded(flags=["paraphrased"]))
    assert type(claim.flags) is tuple
    assert claim.flags == (SafetyFlag.PARAPHRASED,)


def test_soap_note_rejects_attribute_assignment() -> None:
    note = SOAPNote(claims=())
    with pytest.raises(ValidationError) as exc:
        note.claims = ()  # type: ignore[misc]
    (err,) = exc.value.errors()
    assert err["type"] == "frozen_instance"
    assert err["loc"] == ("claims",)


def test_soap_note_claims_are_a_tuple_even_from_a_list() -> None:
    note = SOAPNote.model_validate({"claims": [_grounded()]})
    assert type(note.claims) is tuple


def test_by_section_keeps_note_order_within_a_section() -> None:
    claims = [
        _grounded(id=0, section="P", text="plan-1"),
        _grounded(id=1, section="S", text="subjective-1"),
        _grounded(id=2, section="P", text="plan-2"),
    ]
    note = SOAPNote.model_validate({"claims": claims})
    assert [c.id for c in note.by_section("P")] == [0, 2]
    assert [c.id for c in note.by_section("S")] == [1]
    assert note.by_section("A") == []


# --- eval results and the report (§4.2; L43, L102) ----------------------------


def _result(severity: Severity, *, passed: bool, errored: bool = False) -> EvalResult:
    return EvalResult(check="check-1", severity=severity, passed=passed, errored=errored)


def _report(*results: EvalResult) -> EvalReport:
    return EvalReport(
        results=list(results), checks_run=frozenset({"check-1"}), checks_version="hash-1"
    )


def test_severity_wire_values() -> None:
    assert [s.value for s in Severity] == ["critical", "warning", "info"]


def test_eval_result_defaults() -> None:
    result = EvalResult(check="check-1", severity=Severity.WARNING, passed=True)
    assert result.errored is False
    assert result.detail == ""
    assert result.claim_ids == ()


def test_eval_result_rejects_errored_and_passed() -> None:
    with pytest.raises(ValidationError) as exc:
        EvalResult.model_validate(
            {"check": "check-1", "severity": Severity.CRITICAL, "passed": True, "errored": True}
        )
    (err,) = exc.value.errors()
    assert err["type"] == "value_error"
    assert err["loc"] == ()
    assert "an errored check cannot pass" in err["msg"]


def test_eval_result_rejects_attribute_assignment() -> None:
    result = _result(Severity.WARNING, passed=True)
    with pytest.raises(ValidationError) as exc:
        result.passed = False  # type: ignore[misc]
    (err,) = exc.value.errors()
    assert err["type"] == "frozen_instance"
    assert err["loc"] == ("passed",)


def test_eval_result_claim_ids_are_a_tuple_even_from_a_list() -> None:
    result = EvalResult.model_validate(
        {"check": "check-1", "severity": Severity.CRITICAL, "passed": False, "claim_ids": [0, 2]}
    )
    assert type(result.claim_ids) is tuple
    assert result.claim_ids == (0, 2)


def test_all_critical_passed_is_false_with_no_results() -> None:
    # invariant 12: a report with no CRITICAL result does not read as passed
    assert _report().all_critical_passed is False


def test_warnings_do_not_gate_the_verdict() -> None:
    report = _report(
        _result(Severity.CRITICAL, passed=True), _result(Severity.WARNING, passed=False)
    )
    assert report.all_critical_passed is True


def test_one_failing_critical_fails_the_verdict() -> None:
    report = _report(
        _result(Severity.CRITICAL, passed=True), _result(Severity.CRITICAL, passed=False)
    )
    assert report.all_critical_passed is False


def test_an_errored_critical_fails_the_verdict() -> None:
    # L43: a crash is a valid result, and it reads as a failure
    report = _report(_result(Severity.CRITICAL, passed=False, errored=True))
    assert report.all_critical_passed is False


def test_all_critical_passed_is_serialized() -> None:
    # L102: the verdict crosses the wire, and the response schema declares it
    report = _report(_result(Severity.CRITICAL, passed=False))
    assert report.model_dump(mode="json")["all_critical_passed"] is False
    schema = EvalReport.model_json_schema(mode="serialization")
    assert schema["properties"]["all_critical_passed"]["type"] == "boolean"


def test_judge_usage_defaults_to_zero() -> None:
    assert _report().judge_usage == TokenUsage()


# --- the case contract (§4.2, §8.5; L9, L42, L103) ------------------------------


def _case(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "case-1",
        "species": "detection",
        "raw_text": "raw-1",
        "trap": "trap-1",
        "expected_flags": ["check-1"],
    }
    return {**base, **overrides}


def _case_error(data: dict[str, object]) -> str:
    with pytest.raises(ValidationError) as exc:
        EvalCase.model_validate(data)
    (err,) = exc.value.errors()
    assert err["type"] == "value_error"
    assert err["loc"] == ()
    return str(err["msg"])


@pytest.mark.parametrize(
    "data",
    [
        _case(draft={"claims": [_claim()]}),
        _case(species="control", trap=None, expected_flags=[]),
        _case(species="fidelity", expected_flags=[]),
    ],
    ids=["injected-detection", "model-control", "model-fidelity"],
)
def test_eval_case_accepts_each_species(data: dict[str, object]) -> None:
    EvalCase.model_validate(data)


def test_eval_case_rejects_unknown_key() -> None:
    # L103: a misspelled draft key would otherwise make an injected case a model case
    with pytest.raises(ValidationError) as exc:
        EvalCase.model_validate(_case(drafts={"claims": [_claim()]}))
    (err,) = exc.value.errors()
    assert err["type"] == "extra_forbidden"
    assert err["loc"] == ("drafts",)


def test_eval_case_rejects_unknown_species() -> None:
    with pytest.raises(ValidationError) as exc:
        EvalCase.model_validate(_case(species="regression"))
    (err,) = exc.value.errors()
    assert err["type"] == "literal_error"
    assert err["loc"] == ("species",)


def test_eval_case_requires_trap() -> None:
    data = _case()
    del data["trap"]
    with pytest.raises(ValidationError) as exc:
        EvalCase.model_validate(data)
    (err,) = exc.value.errors()
    assert err["type"] == "missing"
    assert err["loc"] == ("trap",)


def test_injected_draft_passes_the_model_boundary() -> None:
    # an injected draft is validated like the model's output (§4.1)
    with pytest.raises(ValidationError) as exc:
        EvalCase.model_validate(_case(draft={"claims": [_claim(source_quote="   ")]}))
    (err,) = exc.value.errors()
    assert err["type"] == "string_too_short"
    assert err["loc"] == ("draft", "claims", 0, "source_quote")


def test_detection_requires_expected_flags() -> None:
    msg = _case_error(_case(expected_flags=[]))
    assert "detection traps, and only they, carry expected_flags" in msg


def test_only_detection_carries_expected_flags() -> None:
    msg = _case_error(_case(species="control", trap=None))
    assert "detection traps, and only they, carry expected_flags" in msg


def test_control_has_no_trap() -> None:
    msg = _case_error(_case(species="control", expected_flags=[]))
    assert "controls, and only they, have trap=None" in msg


def test_a_trap_names_its_danger() -> None:
    msg = _case_error(_case(species="fidelity", trap=None, expected_flags=[]))
    assert "controls, and only they, have trap=None" in msg


def test_fidelity_cannot_inject_a_draft() -> None:
    msg = _case_error(_case(species="fidelity", expected_flags=[], draft={"claims": []}))
    assert "a fidelity trap tests the MODEL; it cannot inject a draft" in msg
