"""Pins config wiring (spec §10; L209, L232, L233, L314).

Settings is built at import time, so test_dotenv_disabled_under_pytest sees the
environment conftest set before backend was first imported. _dotenv_path is pure,
so its branches are tested directly with a passed-in environment.

Domain tests build Settings through _settings, which passes every knob explicitly:
init kwargs outrank environment variables in pydantic-settings, so an exported shell
variable can never reach the knob under test. Each rejection pins the single error's
type and loc (the step-1 pattern), so no test passes on an unrelated error.
"""

import math
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import SecretStr, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from backend.config import Settings, _dotenv_path
from backend.schemas import ChecksConfig, CorpusRunRecord
from tests.fakes import checks_config_with


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
_RUNS_PATH = Path("runs/corpus_runs.jsonl")


def _settings(
    *,
    max_input_chars: int = 100,
    min_input_chars: int = 1,
    output_tokens_per_input_char: float = 0.5,
    model_max_output_tokens: int = 1000,
    max_validation_retries: int = 2,
    sdk_transport_retries: int = 2,
    llm_timeout_s: float = 90.0,
    judge_timeout_s: float = 10.0,
    judge_concurrency: int = 2,
    fuzzy_score_cutoff: float = 50.0,
    min_quote_content_tokens: int = 2,
    corpus_repeats: int = 2,
    corpus_concurrency: int = 1,
    runs_path: Path = _RUNS_PATH,
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
        judge_timeout_s=judge_timeout_s,
        judge_concurrency=judge_concurrency,
        fuzzy_score_cutoff=fuzzy_score_cutoff,
        min_quote_content_tokens=min_quote_content_tokens,
        corpus_repeats=corpus_repeats,
        corpus_concurrency=corpus_concurrency,
        runs_path=runs_path,
    )


# Typed builders keyed by knob name, so a parametrized test can set one knob by name
# without a **{name: value} call that mypy cannot type against the kw-only signature.
_RETRY_KNOBS: dict[str, Callable[[int], Settings]] = {
    "max_validation_retries": lambda v: _settings(max_validation_retries=v),
    "sdk_transport_retries": lambda v: _settings(sdk_transport_retries=v),
}
_CORPUS_COUNT_KNOBS: dict[str, Callable[[int], Settings]] = {
    "corpus_repeats": lambda v: _settings(corpus_repeats=v),
    "corpus_concurrency": lambda v: _settings(corpus_concurrency=v),
}
# llm_timeout_s's builder holds the judge's timeout below every value the tests pass, so the
# boot check that orders the two (L314) never adds a second error.
_POSITIVE_FLOAT_KNOBS: dict[str, Callable[[float], Settings]] = {
    "llm_timeout_s": lambda v: _settings(llm_timeout_s=v, judge_timeout_s=0.0001),
    "judge_timeout_s": lambda v: _settings(judge_timeout_s=v),
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


# --- fuzzy_score_cutoff: a finite score, 0 to 100 (§6.3, §10; L105) --------------


@pytest.mark.parametrize(
    ("value", "error"),
    [(-0.1, "greater_than_equal"), (100.1, "less_than_equal")],
    ids=["below-0", "above-100"],
)
def test_fuzzy_score_cutoff_rejects_out_of_range(value: float, error: str) -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(fuzzy_score_cutoff=value)
    (err,) = exc.value.errors()
    assert err["type"] == error
    assert err["loc"] == ("fuzzy_score_cutoff",)


@pytest.mark.parametrize("value", [math.inf, math.nan], ids=["inf", "nan"])
def test_fuzzy_score_cutoff_rejects_non_finite(value: float) -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(fuzzy_score_cutoff=value)
    (err,) = exc.value.errors()
    assert err["type"] == "finite_number"
    assert err["loc"] == ("fuzzy_score_cutoff",)


@pytest.mark.parametrize("value", [0.0, 100.0], ids=["0", "100"])
def test_fuzzy_score_cutoff_accepts_the_bounds(value: float) -> None:
    assert _settings(fuzzy_score_cutoff=value).fuzzy_score_cutoff == value


# --- min_quote_content_tokens: ge=1 (§8.4, §10; L161) ----------------------------


def test_min_quote_content_tokens_rejects_zero() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(min_quote_content_tokens=0)
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than_equal"
    assert err["loc"] == ("min_quote_content_tokens",)


def test_min_quote_content_tokens_accepts_one() -> None:
    assert _settings(min_quote_content_tokens=1).min_quote_content_tokens == 1


# --- the corpus knobs: counts ge=1, a .jsonl run log (§8.7, §10; L209, L232) -------


@pytest.mark.parametrize("name", list(_CORPUS_COUNT_KNOBS))
def test_corpus_count_knobs_reject_zero(name: str) -> None:
    with pytest.raises(ValidationError) as exc:
        _CORPUS_COUNT_KNOBS[name](0)
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than_equal"
    assert err["loc"] == (name,)


@pytest.mark.parametrize("name", list(_CORPUS_COUNT_KNOBS))
def test_corpus_count_knobs_accept_one(name: str) -> None:
    assert getattr(_CORPUS_COUNT_KNOBS[name](1), name) == 1


@pytest.mark.parametrize(
    "value",
    ["", "backend/evals/runs/", "runs/corpus_runs.json", "runs/.jsonl"],
    ids=["empty", "directory", "json", "dotfile"],
)
def test_runs_path_rejects_a_path_that_is_not_a_jsonl_file(value: str) -> None:
    # L232: "" becomes Path("."), the working directory, and a trailing slash is dropped
    # (measured); each would fail at the run's last step, after the spend
    with pytest.raises(ValidationError) as exc:
        _settings(runs_path=Path(value))
    (err,) = exc.value.errors()
    assert err["type"] == "runs_path_not_jsonl"
    assert err["loc"] == ("runs_path",)


def test_runs_path_accepts_a_jsonl_file() -> None:
    assert _settings(runs_path=Path("runs/x.jsonl")).runs_path == Path("runs/x.jsonl")


@pytest.mark.parametrize(
    ("knob", "field"),
    [("corpus_repeats", "repeats"), ("corpus_concurrency", "concurrency")],
)
def test_corpus_count_bounds_match_the_record(knob: str, field: str) -> None:
    # L233: a knob the record would reject fails at boot, not after the spend
    assert _bounds(CorpusRunRecord.model_fields[field]) == _bounds(Settings.model_fields[knob])


# --- the judge: a count of calls, and a timeout below summarize's (§8.2, §10; L314) ---


def test_judge_concurrency_rejects_zero() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(judge_concurrency=0)
    (err,) = exc.value.errors()
    assert err["type"] == "greater_than_equal"
    assert err["loc"] == ("judge_concurrency",)


def test_judge_concurrency_accepts_one() -> None:
    assert _settings(judge_concurrency=1).judge_concurrency == 1


@pytest.mark.parametrize("judge_timeout_s", [30.0, 31.0], ids=["equal", "above"])
def test_judge_timeout_not_below_llm_timeout_rejected(judge_timeout_s: float) -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(llm_timeout_s=30.0, judge_timeout_s=judge_timeout_s)
    (err,) = exc.value.errors()
    assert err["type"] == "judge_timeout_not_below_llm_timeout"
    assert err["loc"] == ()


def test_judge_timeout_below_llm_timeout_accepted() -> None:
    s = _settings(llm_timeout_s=30.0, judge_timeout_s=29.5)
    assert (s.judge_timeout_s, s.llm_timeout_s) == (29.5, 30.0)


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


def test_api_key_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    # Missing is not empty: min_length rejects an empty key; a missing one is rejected as
    # missing because the field has no default (L77). Each field's upper-case env var is
    # removed first, so a knob exported in upper case can't add an error.
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    with pytest.raises(ValidationError) as exc:
        Settings()
    (err,) = exc.value.errors()
    assert err["type"] == "missing"
    assert err["loc"] == ("anthropic_api_key",)


# --- the verdict knobs, handed inward (§4.2, §10; L187) ---------------------------


def test_checks_config_carries_both_knobs() -> None:
    # Non-defaults, so a hard-coded or swapped field changes the result.
    s = _settings(fuzzy_score_cutoff=73.5, min_quote_content_tokens=4)
    assert s.checks_config() == ChecksConfig(fuzzy_score_cutoff=73.5, min_quote_content_tokens=4)


def _bounds(field: FieldInfo) -> tuple[object, list[str]]:
    # repr, not ==: pydantic's allow_inf_nan marker compares by identity, so two identical
    # declarations compare unequal (measured).
    return field.annotation, [repr(m) for m in field.metadata]


@pytest.mark.parametrize("name", list(ChecksConfig.model_fields))
def test_checks_config_bounds_match_settings(name: str) -> None:
    # L187: the two bounds are declared twice, in Settings and in ChecksConfig.
    assert _bounds(ChecksConfig.model_fields[name]) == _bounds(Settings.model_fields[name])


def test_checks_config_with_validates_the_knob_it_varies() -> None:
    # tests/fakes.py's helper; model_copy(update=...) would accept 101 (measured)
    with pytest.raises(ValidationError) as exc:
        checks_config_with(fuzzy_score_cutoff=101.0)
    (err,) = exc.value.errors()
    assert err["type"] == "less_than_equal"
    assert err["loc"] == ("fuzzy_score_cutoff",)


def test_checks_config_with_rejects_an_unknown_knob() -> None:
    # validation ignores extra keys, so a misspelled knob would leave the default in place
    with pytest.raises(TypeError, match="fuzzy_cutoff"):
        checks_config_with(fuzzy_cutoff=50.0)


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


_ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"


def test_env_example_shows_the_real_defaults() -> None:
    # .env.example says its commented values are the defaults, and nothing tied the two: a
    # default could move (as L184's do) and leave the example stale. Read back, not pinned:
    # a default may change, as long as the example changes with it. Each value is read as
    # its field's type reads it: bool("False") is True, so a type() call can't read a bool.
    shown = re.findall(r"^# ([A-Z][A-Z0-9_]*)=(.*)$", _ENV_EXAMPLE.read_text(), re.M)
    assert shown, "no commented knob lines found"
    for env_name, raw in shown:
        field = Settings.model_fields.get(env_name.lower())
        assert field is not None, f"{env_name} is not a Settings field"
        default = field.default
        read: object = TypeAdapter(field.annotation).validate_python(raw)
        assert read == default, f"{env_name}={raw}, default is {default!r}"
