"""Pins the spine types (spec §4.1, §4.2; D4, L6, L9, L10, L25, L36, L42, L43, L86, L89, L102,
L103, L106, L201, L203, L205, L212, L224-L227).

Rejection tests validate a dict through model_validate — the §5.4 entry point
(L12) — and pin the single error's type and loc, so no test passes on an
unrelated error. Strings are synthetic.
"""

import pytest
from pydantic import ValidationError

from backend.schemas import (
    CaseResult,
    ChecksConfig,
    ClaimDraft,
    ClinicalClaim,
    CorpusMetrics,
    CorpusRunRecord,
    EvalCase,
    EvalReport,
    EvalResult,
    NotAddItem,
    PreserveItem,
    RunMetadata,
    SafetyFlag,
    Severity,
    SOAPNote,
    SOAPNoteDraft,
    TokenUsage,
)

BLANK = ("", "   ", "\n\t", "\x1c\x1f")  # str.isspace() whitespace pydantic's strip kept (L106)


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


def test_strip_removes_what_grounding_calls_whitespace() -> None:
    # L106: the boundary strips what str.isspace() calls whitespace, as grounding does
    assert ClaimDraft(text="fact-1", section="S", source_quote="x\x1c").source_quote == "x"


@pytest.mark.parametrize("value", [5, b"   "], ids=["int", "bytes"])
def test_source_quote_rejects_a_non_string(value: object) -> None:
    # the strip passes a non-string through, so the strict str schema rejects it; a lax one
    # would decode bytes after the strip and accept b"   " as a blank quote
    with pytest.raises(ValidationError) as exc:
        ClaimDraft.model_validate(_claim(source_quote=value))
    (err,) = exc.value.errors()
    assert err["type"] == "string_type"
    assert err["loc"] == ("source_quote",)


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
        results=list(results),
        checks_run=frozenset({"check-1"}),
        checks_version="hash-1",
        checks_config=ChecksConfig(fuzzy_score_cutoff=90.0, min_quote_content_tokens=2),
        judge_version=None,
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


def test_eval_report_requires_its_checks_config() -> None:
    # L334: a report names the knobs it was checked under, with no default to fall back on
    data: dict[str, object] = {
        "results": [],
        "checks_run": [],
        "checks_version": "hash-1",
        "judge_version": None,
    }
    with pytest.raises(ValidationError) as exc:
        EvalReport.model_validate(data)
    (err,) = exc.value.errors()
    assert (err["type"], err["loc"]) == ("missing", ("checks_config",))


def test_eval_report_requires_its_judge_version() -> None:
    # L336: None says no judge ran, so it is stated, never defaulted
    config = {"fuzzy_score_cutoff": 90.0, "min_quote_content_tokens": 2}
    data: dict[str, object] = {
        "results": [],
        "checks_run": [],
        "checks_version": "hash-1",
        "checks_config": config,
    }
    with pytest.raises(ValidationError) as exc:
        EvalReport.model_validate(data)
    (err,) = exc.value.errors()
    assert (err["type"], err["loc"]) == ("missing", ("judge_version",))


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


# --- the reference items (§4.2, §8.5; D4, L10, L36, L103) ----------------------


def test_preserve_item_is_present_by_default() -> None:
    # L36: polarity is opt-out; a label states a finding's absence only when it says so
    item = PreserveItem.model_validate({"text": "item-1", "kind": "finding"})
    assert item.present is True


@pytest.mark.parametrize("kind", ["allergy", "medication", "dose", "finding", "diagnosis"])
def test_preserve_item_accepts_each_kind(kind: str) -> None:
    assert PreserveItem.model_validate({"text": "item-1", "kind": kind}).kind == kind


@pytest.mark.parametrize("kind", ["medication", "finding", "diagnosis"])
def test_not_add_item_accepts_each_kind(kind: str) -> None:
    assert NotAddItem.model_validate({"text": "item-1", "kind": kind}).kind == kind


@pytest.mark.parametrize("kind", ["allergy", "dose"])
def test_not_add_item_rejects_the_kinds_only_preserve_has(kind: str) -> None:
    with pytest.raises(ValidationError) as exc:
        NotAddItem.model_validate({"text": "item-1", "kind": kind})
    (err,) = exc.value.errors()
    assert err["type"] == "literal_error"
    assert err["loc"] == ("kind",)


def test_preserve_item_rejects_unknown_key() -> None:
    # L103: a misspelled `present` would otherwise leave the item present=True
    with pytest.raises(ValidationError) as exc:
        PreserveItem.model_validate({"text": "item-1", "kind": "finding", "presnt": False})
    (err,) = exc.value.errors()
    assert err["type"] == "extra_forbidden"
    assert err["loc"] == ("presnt",)


def test_not_add_item_has_no_polarity() -> None:
    # L36: a not-add label has no polarity field, so `present` on one is rejected
    with pytest.raises(ValidationError) as exc:
        NotAddItem.model_validate({"text": "item-1", "kind": "finding", "present": False})
    (err,) = exc.value.errors()
    assert err["type"] == "extra_forbidden"
    assert err["loc"] == ("present",)


def test_eval_case_reference_lists_default_empty() -> None:
    case = EvalCase.model_validate(_case())
    assert (case.must_preserve, case.must_not_add) == ([], [])


def test_eval_case_types_its_reference_items() -> None:
    case = EvalCase.model_validate(
        _case(
            species="fidelity",
            expected_flags=[],
            must_preserve=[{"text": "item-1", "kind": "finding", "present": False}],
            must_not_add=[{"text": "item-2", "kind": "medication"}],
        )
    )
    assert case.must_preserve == [PreserveItem(text="item-1", kind="finding", present=False)]
    assert case.must_not_add == [NotAddItem(text="item-2", kind="medication")]


@pytest.mark.parametrize(
    ("field", "item", "error", "loc"),
    [
        (
            "must_preserve",
            {"text": "item-1", "kind": "finding", "extra": 1},
            "extra_forbidden",
            "extra",
        ),
        ("must_not_add", {"text": "item-1", "kind": "dose"}, "literal_error", "kind"),
    ],
)
def test_eval_case_validates_each_item(
    field: str, item: dict[str, object], error: str, loc: str
) -> None:
    with pytest.raises(ValidationError) as exc:
        EvalCase.model_validate(_case(**{field: [item]}))
    (err,) = exc.value.errors()
    assert err["type"] == error
    assert err["loc"] == (field, 0, loc)


# --- the verdict knobs (§4.2, L187) ---------------------------------------------


def test_checks_config_rejects_attribute_assignment() -> None:
    cfg = ChecksConfig(fuzzy_score_cutoff=90.0, min_quote_content_tokens=2)
    with pytest.raises(ValidationError) as exc:
        cfg.fuzzy_score_cutoff = 50.0  # type: ignore[misc]
    (err,) = exc.value.errors()
    assert err["type"] == "frozen_instance"
    assert err["loc"] == ("fuzzy_score_cutoff",)


def test_checks_config_declares_no_defaults() -> None:
    # The defaults are Settings' (§10). A default here is a second copy that could drift,
    # and a config built without a knob would silently take it.
    assert all(field.is_required() for field in ChecksConfig.model_fields.values())


# --- the corpus record (§4.2; L201, L203, L205, L212, L224-L227) ----------------


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "case_id": "case-1",
        "repeat": 0,
        "species": "control",
        "status": "passed",
        "fired_checks": [],
        "fired_critical": [],
        "missing_expected": [],
        "unexpected_fired": [],
        "usage": {"input_tokens": 1, "output_tokens": 1},
        "validation_attempts": 1,
        "summarize_wall_s": 1.5,
        "draft": {"claims": [_claim()]},
    }
    return {**base, **overrides}


def _row_error(data: dict[str, object]) -> str:
    with pytest.raises(ValidationError) as exc:
        CaseResult.model_validate(data)
    (err,) = exc.value.errors()
    assert err["type"] == "value_error"
    assert err["loc"] == ()
    return str(err["msg"])


def test_case_result_accepts_a_clean_row() -> None:
    row = CaseResult.model_validate(_row())
    assert row.error is None
    assert row.errored_checks == []


def test_case_result_requires_fired_critical() -> None:
    data = _row()
    del data["fired_critical"]
    with pytest.raises(ValidationError) as exc:
        CaseResult.model_validate(data)
    (err,) = exc.value.errors()
    assert err["type"] == "missing"
    assert err["loc"] == ("fired_critical",)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("repeat", -1, "greater_than_equal"),
        ("validation_attempts", 0, "greater_than_equal"),
        ("summarize_wall_s", -0.5, "greater_than_equal"),
        ("summarize_wall_s", float("inf"), "finite_number"),
        ("summarize_wall_s", float("nan"), "finite_number"),
    ],
    ids=["repeat-negative", "attempts-zero", "wall-negative", "wall-inf", "wall-nan"],
)
def test_case_result_rejects_a_value_outside_its_domain(
    field: str, value: object, error: str
) -> None:
    with pytest.raises(ValidationError) as exc:
        CaseResult.model_validate(_row(**{field: value}))
    (err,) = exc.value.errors()
    assert err["type"] == error
    assert err["loc"] == (field,)


@pytest.mark.parametrize(
    "cost",
    [
        {"usage": None, "validation_attempts": 1},
        {"usage": {"input_tokens": 1, "output_tokens": 1}, "validation_attempts": None},
    ],
    ids=["usage-lost", "attempts-lost"],
)
def test_case_result_cost_is_known_together(cost: dict[str, object]) -> None:
    data = _row(status="failed", error="APIError", draft=None, **cost)
    assert _row_error(data) == "Value error, usage and validation_attempts are None together"


@pytest.mark.parametrize("status", ["passed", "not_applicable"])
def test_case_result_with_an_error_is_failed(status: str) -> None:
    data = _row(status=status, error="APIError")
    assert _row_error(data) == "Value error, a case with an error is failed"


@pytest.mark.parametrize(
    "lost",
    [
        {"draft": None, "usage": None, "validation_attempts": None},
        {"draft": None, "validation_attempts": 3},
        {},
    ],
    ids=["crash-in-summarize", "orchestrator-error", "crash-after-summarize"],
)
def test_case_result_with_an_error_may_lack_its_draft_or_cost(lost: dict[str, object]) -> None:
    row = CaseResult.model_validate(_row(status="failed", error="code-1", **lost))
    assert row.error == "code-1"


@pytest.mark.parametrize(
    "lost",
    [{"draft": None}, {"usage": None, "validation_attempts": None}],
    ids=["draft", "cost"],
)
def test_case_result_without_an_error_keeps_its_draft_and_cost(lost: dict[str, object]) -> None:
    data = _row(**lost)
    assert _row_error(data) == "Value error, a case without an error keeps its draft and its cost"


def test_case_result_records_no_claim_ids_by_default() -> None:
    # L335: a row written before the field loads, reading nothing recorded
    assert CaseResult.model_validate(_row()).fired_claim_ids is None


@pytest.mark.parametrize(
    ("fired", "claim_ids"),
    [([], {}), (["a", "b"], {"a": [0, 2], "b": []})],
    ids=["none-fired", "claims-and-note-level"],
)
def test_case_result_accepts_claim_ids_for_exactly_the_fired_checks(
    fired: list[str], claim_ids: dict[str, list[int]]
) -> None:
    row = CaseResult.model_validate(_row(fired_checks=fired, fired_claim_ids=claim_ids))
    assert row.fired_claim_ids == claim_ids


@pytest.mark.parametrize(
    ("fired", "claim_ids"),
    [
        (["a", "b"], {"a": [0]}),
        (["a"], {"a": [0], "b": [1]}),
        (["a"], {"a": [2, 0]}),
        (["a"], {"a": [0, 0]}),
    ],
    ids=["a-fired-check-missing", "a-check-that-didnt-fire", "unsorted", "repeated"],
)
def test_case_result_rejects_claim_ids_other_than_the_fired_checks_sorted(
    fired: list[str], claim_ids: dict[str, list[int]]
) -> None:
    data = _row(fired_checks=fired, fired_claim_ids=claim_ids)
    assert _row_error(data) == (
        "Value error, fired_claim_ids names each fired check's claims, sorted"
    )


_RATES = (
    "detection_recall",
    "control_specificity",
    "model_fidelity",
    "fidelity_caught",
    "pass_rate",
)


def _metrics(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {rate: None for rate in _RATES}
    return {**base, "flaky_cases": [], **overrides}


@pytest.mark.parametrize("rate", _RATES)
def test_corpus_metrics_accepts_none_and_both_bounds(rate: str) -> None:
    assert getattr(CorpusMetrics.model_validate(_metrics()), rate) is None
    assert getattr(CorpusMetrics.model_validate(_metrics(**{rate: 0.0})), rate) == 0.0
    assert getattr(CorpusMetrics.model_validate(_metrics(**{rate: 1.0})), rate) == 1.0


@pytest.mark.parametrize("rate", _RATES)
@pytest.mark.parametrize(
    ("value", "error"),
    [(-0.01, "greater_than_equal"), (1.01, "less_than_equal"), (float("nan"), "less_than_equal")],
    ids=["below-zero", "above-one", "nan"],
)
def test_corpus_metrics_rejects_a_rate_outside_zero_to_one(
    rate: str, value: float, error: str
) -> None:
    with pytest.raises(ValidationError) as exc:
        CorpusMetrics.model_validate(_metrics(**{rate: value}))
    (err,) = exc.value.errors()
    assert err["type"] == error
    assert err["loc"] == (rate,)


def _record(rows: list[tuple[str, int]], **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ran_at": "2026-10-15T12:00:00Z",
        "git_sha": "sha-1",
        "git_dirty": False,
        "model": "model-id-1",
        "prompt_version": "prompt-hash-1",
        "corpus_version": "corpus-hash-1",
        "checks_version": "checks-hash-1",
        "checks_config": {"fuzzy_score_cutoff": 90.0, "min_quote_content_tokens": 2},
        "judge_enabled": False,
        "repeats": 2,
        "concurrency": 1,
        "n_cases": 2,
        "metrics": _metrics(),
        "usage": {"input_tokens": 4, "output_tokens": 4},
        "judge_usage": {},
        "cases": [_row(case_id=case_id, repeat=repeat) for case_id, repeat in rows],
    }
    return {**base, **overrides}


_FULL = [("case-b", 1), ("case-a", 0), ("case-b", 0), ("case-a", 1)]


def test_corpus_run_record_accepts_each_case_once_per_repeat_in_any_order() -> None:
    record = CorpusRunRecord.model_validate(_record(_FULL))
    assert [(row.case_id, row.repeat) for row in record.cases] == _FULL


def test_corpus_run_record_rejects_a_naive_ran_at() -> None:
    with pytest.raises(ValidationError) as exc:
        CorpusRunRecord.model_validate(_record(_FULL, ran_at="2026-10-15T12:00:00"))
    (err,) = exc.value.errors()
    assert err["type"] == "timezone_aware"
    assert err["loc"] == ("ran_at",)


@pytest.mark.parametrize("field", ["repeats", "concurrency", "n_cases"])
def test_corpus_run_record_rejects_a_zero_count(field: str) -> None:
    with pytest.raises(ValidationError) as exc:
        CorpusRunRecord.model_validate(_record(_FULL, **{field: 0}))
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than_equal"
    assert err["loc"] == (field,)


def _record_error(data: dict[str, object]) -> str:
    with pytest.raises(ValidationError) as exc:
        CorpusRunRecord.model_validate(data)
    (err,) = exc.value.errors()
    assert err["type"] == "value_error"
    assert err["loc"] == ()
    return str(err["msg"])


@pytest.mark.parametrize(
    ("rows", "n_cases"),
    [
        ([("case-a", 0), ("case-a", 0), ("case-a", 1)], 1),
        ([("case-a", 0), ("case-a", 2)], 1),
        ([("case-a", 0), ("case-a", 1), ("case-b", 0)], 2),
        ([("case-a", 0), ("case-a", 0), ("case-a", 7), ("case-b", 0)], 2),
    ],
    ids=["duplicate", "repeat-out-of-range", "repeat-missing", "right-count-wrong-rows"],
)
def test_corpus_run_record_holds_one_row_per_case_and_repeat(
    rows: list[tuple[str, int]], n_cases: int
) -> None:
    data = _record(rows, n_cases=n_cases)
    assert _record_error(data) == "Value error, cases holds one row per case and repeat"


@pytest.mark.parametrize(
    ("rows", "n_cases"),
    [([("case-a", 0), ("case-a", 0)], 2), ([("case-a", 0), ("case-b", 0)], 1)],
    ids=["fewer-ids", "more-ids"],
)
def test_corpus_run_record_n_cases_counts_distinct_case_ids(
    rows: list[tuple[str, int]], n_cases: int
) -> None:
    data = _record(rows, repeats=1, n_cases=n_cases)
    assert _record_error(data) == "Value error, n_cases counts the distinct case ids"


def test_corpus_run_record_round_trips_through_json() -> None:
    record = CorpusRunRecord.model_validate(_record(_FULL))
    assert CorpusRunRecord.model_validate_json(record.model_dump_json()) == record


def test_a_judged_run_records_its_judges_version_through_json() -> None:
    # L317: set exactly when the run has a judge
    data = _record(_FULL, judge_enabled=True, judge_version="judge-hash-1")
    record = CorpusRunRecord.model_validate(data)
    assert record.judge_version == "judge-hash-1"
    assert CorpusRunRecord.model_validate_json(record.model_dump_json()) == record


def test_a_record_written_before_judge_version_loads_without_one() -> None:
    # L317: the records committed before the field ran without a judge and don't name it
    data = _record(_FULL)
    assert "judge_version" not in data
    assert CorpusRunRecord.model_validate(data).judge_version is None


@pytest.mark.parametrize(
    ("judge_enabled", "judge_version"),
    [(True, None), (False, "judge-hash-1")],
    ids=["judge-without-version", "version-without-judge"],
)
def test_corpus_run_record_holds_judge_version_to_its_judge(
    judge_enabled: bool, judge_version: str | None
) -> None:
    data = _record(_FULL, judge_enabled=judge_enabled, judge_version=judge_version)
    assert _record_error(data) == (
        "Value error, judge_version is set exactly when judge_enabled is true"
    )
