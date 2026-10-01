"""Pins config wiring (spec §10).

Settings is built at import time, so test_dotenv_disabled_under_pytest sees the
environment conftest set before backend was first imported. _dotenv_path is pure,
so its branches are tested directly with a passed-in environment.

Domain tests build Settings through _settings, which passes every knob explicitly:
init kwargs outrank environment variables in pydantic-settings, so an exported shell
variable can never reach the knob under test. Each rejection pins the single error's
type and loc (the step-1 pattern), so no test passes on an unrelated error.
"""

import math
from collections.abc import Callable

import pytest
from pydantic import SecretStr, ValidationError

from backend.config import Settings, _dotenv_path


def test_dotenv_disabled_under_pytest() -> None:
    assert Settings.model_config.get("env_file") is None


def test_dotenv_path_is_none_when_flag_is_one() -> None:
    assert _dotenv_path({"NOTEPILOT_IGNORE_DOTENV": "1"}) is None


@pytest.mark.parametrize(
    "env",
    [{}, {"NOTEPILOT_IGNORE_DOTENV": "0"}],
    ids=["flag-unset", "flag-not-one"],
)
def test_dotenv_path_is_repo_root_env_otherwise(env: dict[str, str]) -> None:
    path = _dotenv_path(env)
    assert path is not None
    assert path.name == ".env"
    assert (path.parent / "pyproject.toml").is_file()


# --- the explicit baseline (one place) ------------------------------------------
# Small and self-consistent on purpose: 100 chars x 0.5 = 50 tokens <= ceiling 1000, so
# each test's arithmetic reads at a glance. Not the production defaults.

_DUMMY_KEY = SecretStr("test-dummy-key")  # module-level: ruff B008 forbids a call in a default


def _settings(
    *,
    max_input_chars: int = 100,
    min_input_chars: int = 1,
    output_tokens_per_input_char: float = 0.5,
    model_max_output_tokens: int = 1000,
    max_validation_retries: int = 2,
    sdk_transport_retries: int = 2,
    llm_timeout_s: float = 90.0,
    model: str = "model-id-1",
    anthropic_api_key: SecretStr = _DUMMY_KEY,
) -> Settings:
    return Settings(
        anthropic_api_key=anthropic_api_key,
        model=model,
        model_max_output_tokens=model_max_output_tokens,
        max_input_chars=max_input_chars,
        min_input_chars=min_input_chars,
        output_tokens_per_input_char=output_tokens_per_input_char,
        max_validation_retries=max_validation_retries,
        sdk_transport_retries=sdk_transport_retries,
        llm_timeout_s=llm_timeout_s,
    )


# Typed builders keyed by knob name, so a parametrized test can set one knob by name
# without a **{name: value} call that mypy cannot type against the kw-only signature.
_RETRY_KNOBS: dict[str, Callable[[int], Settings]] = {
    "max_validation_retries": lambda v: _settings(max_validation_retries=v),
    "sdk_transport_retries": lambda v: _settings(sdk_transport_retries=v),
}
_POSITIVE_FLOAT_KNOBS: dict[str, Callable[[float], Settings]] = {
    "llm_timeout_s": lambda v: _settings(llm_timeout_s=v),
    "output_tokens_per_input_char": lambda v: _settings(output_tokens_per_input_char=v),
}


# --- retry counts: ge=0 (§10, L5) -------------------------------------------------


@pytest.mark.parametrize("name", list(_RETRY_KNOBS))
def test_retry_knobs_reject_negative(name: str) -> None:
    with pytest.raises(ValidationError) as exc:
        _RETRY_KNOBS[name](-1)
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than_equal"
    assert err["loc"] == (name,)


@pytest.mark.parametrize("name", list(_RETRY_KNOBS))
def test_retry_knobs_accept_zero(name: str) -> None:
    assert getattr(_RETRY_KNOBS[name](0), name) == 0


# --- input bounds: ge=1 each, and min < max (§10) --------------------------------


def test_min_input_chars_rejects_zero() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(min_input_chars=0)
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than_equal"
    assert err["loc"] == ("min_input_chars",)


def test_min_input_chars_accepts_one() -> None:
    assert _settings(min_input_chars=1).min_input_chars == 1


def test_max_input_chars_rejects_zero_at_field_level() -> None:
    # The single-error unpack also proves the bounds validator did not fire on top.
    with pytest.raises(ValidationError) as exc:
        _settings(max_input_chars=0)
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than_equal"
    assert err["loc"] == ("max_input_chars",)


def test_max_input_chars_accepts_two_with_min_one() -> None:
    assert _settings(max_input_chars=2, min_input_chars=1).max_input_chars == 2


def test_min_equal_to_max_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(min_input_chars=100, max_input_chars=100)
    (err,) = exc.value.errors()
    assert err["type"] == "input_bounds_inverted"
    assert err["loc"] == ()


def test_min_one_below_max_accepted() -> None:
    s = _settings(min_input_chars=99, max_input_chars=100)
    assert (s.min_input_chars, s.max_input_chars) == (99, 100)


# --- positive, finite floats: gt=0, allow_inf_nan=False (L54, L94) ---------------


@pytest.mark.parametrize("name", list(_POSITIVE_FLOAT_KNOBS))
def test_positive_float_knobs_reject_zero(name: str) -> None:
    with pytest.raises(ValidationError) as exc:
        _POSITIVE_FLOAT_KNOBS[name](0)
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than"
    assert err["loc"] == (name,)


def test_ratio_rejects_negative() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(output_tokens_per_input_char=-0.5)
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than"
    assert err["loc"] == ("output_tokens_per_input_char",)


@pytest.mark.parametrize("value", [math.inf, math.nan], ids=["inf", "nan"])
@pytest.mark.parametrize("name", list(_POSITIVE_FLOAT_KNOBS))
def test_positive_float_knobs_reject_non_finite(name: str, value: float) -> None:
    with pytest.raises(ValidationError) as exc:
        _POSITIVE_FLOAT_KNOBS[name](value)
    (err,) = exc.value.errors()
    assert err["type"] == "finite_number"
    assert err["loc"] == (name,)


@pytest.mark.parametrize("name", list(_POSITIVE_FLOAT_KNOBS))
def test_positive_float_knobs_accept_small_positive(name: str) -> None:
    assert getattr(_POSITIVE_FLOAT_KNOBS[name](0.001), name) == 0.001


# --- max_output_tokens: derived, checked against the ceiling (L16, L72, L94) ------


def test_derived_equal_to_ceiling_accepted() -> None:
    s = _settings(max_input_chars=100, output_tokens_per_input_char=0.5, model_max_output_tokens=50)
    assert s.max_output_tokens == s.model_max_output_tokens == 50


def test_derived_above_ceiling_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(max_input_chars=100, output_tokens_per_input_char=0.5, model_max_output_tokens=49)
    (err,) = exc.value.errors()
    assert err["type"] == "output_ceiling_exceeded"
    assert err["loc"] == ()


# 3 x 0.5 = 1.5 separates ceil (2) from int (1); 5 x 0.5 = 2.5 also separates ceil (3)
# from round (2, banker's), which 1.5 would not (round(1.5) == 2 too).
@pytest.mark.parametrize(("chars", "expected"), [(3, 2), (5, 3)], ids=["3", "5"])
def test_max_output_tokens_rounds_up(chars: int, expected: int) -> None:
    s = _settings(max_input_chars=chars, output_tokens_per_input_char=0.5)
    assert s.max_output_tokens == expected


def test_max_output_tokens_is_not_a_field() -> None:
    # A @computed_field would land in model_computed_fields, not model_fields (L94).
    assert "max_output_tokens" not in Settings.model_fields
    assert "max_output_tokens" not in Settings.model_computed_fields


# --- existing fields gain domains (L77, L84, L72) ----------------------------------


def test_model_rejects_empty() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(model="")
    (err,) = exc.value.errors()
    assert err["type"] == "string_too_short"
    assert err["loc"] == ("model",)


def test_model_max_output_tokens_rejects_zero() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(model_max_output_tokens=0)
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than"
    assert err["loc"] == ("model_max_output_tokens",)


def test_api_key_rejects_empty() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(anthropic_api_key=SecretStr(""))
    (err,) = exc.value.errors()
    # SecretStr length is validated as a sequence, so the type is too_short, not
    # string_too_short like model's. The asymmetry is pydantic's, not a typo.
    assert err["type"] == "too_short"
    assert err["loc"] == ("anthropic_api_key",)


# --- frozen: the boot checks cannot be bypassed after construction ---------------


def test_settings_rejects_attribute_assignment() -> None:
    s = _settings()
    with pytest.raises(ValidationError) as exc:
        s.model = "model-id-2"  # type: ignore[misc]
    (err,) = exc.value.errors()
    assert err["type"] == "frozen_instance"
    assert err["loc"] == ("model",)


# --- the defaults pass their own boot checks --------------------------------------

# The key is excluded because conftest supplies it; every other knob must fall to default.
_KNOB_ENV_NAMES = [n.upper() for n in Settings.model_fields if n != "anthropic_api_key"]


def test_defaults_construct(monkeypatch: pytest.MonkeyPatch) -> None:
    # Values are deliberately not asserted: that would be a change detector.
    for name in _KNOB_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    Settings()
