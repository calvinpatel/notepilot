"""Pins the spine types (spec §4.1, §4.2; L6, L25, L86, L89).

Rejection tests validate a dict through model_validate — the §5.4 entry point
(L12) — and pin the single error's type and loc, so no test passes on an
unrelated error. Strings are synthetic.
"""

import pytest
from pydantic import ValidationError

from backend.schemas import (
    ClaimDraft,
    ClinicalClaim,
    RunMetadata,
    SafetyFlag,
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
