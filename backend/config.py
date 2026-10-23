"""Every knob, validated at boot (spec §10).

Every field declares its domain (L77). `max_output_tokens` is a read-only property derived
from `max_input_chars` and `output_tokens_per_input_char` (L94), checked against the model's
declared output ceiling at construction (L16, L72). Four boot checks beyond the fields'
bounds, each a validation error: the derived output ceiling, the input bounds, runs_path's
.jsonl name (L232), and a judge timeout below summarize's (L314).

Tests run with dotenv disabled; see tests/conftest.py.
"""

import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.schemas import ChecksConfig

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _dotenv_path(env: Mapping[str, str]) -> Path | None:
    """The .env file to load, or None when NOTEPILOT_IGNORE_DOTENV is exactly "1"."""
    if env.get("NOTEPILOT_IGNORE_DOTENV") == "1":
        return None
    return _REPO_ROOT / ".env"


class Settings(BaseSettings):
    # frozen: a mutable settings object could bypass the boot checks after construction.
    model_config = SettingsConfigDict(env_file=_dotenv_path(os.environ), frozen=True)

    # min_length=1 and nothing else, ever. A failed constraint prints input_value in the
    # boot traceback, so any check that can reject a non-empty key would leak it into logs
    # (invariant 19). min_length=1 can only reject "".
    anthropic_api_key: SecretStr = Field(min_length=1)  # required (L77)

    # A pinned model id (L84) — never an alias, never validated with a date regex. Its
    # output ceiling is declared directly beside it: the two change together (L72); the
    # smoke run verifies the declaration against the Models API at each pin (L85, L180).
    model: str = Field("claude-haiku-5-5", min_length=1)
    model_max_output_tokens: int = Field(128_000, gt=0)

    # Input bounds (§10). max_output_tokens is derived from max_input_chars via the ratio
    # (L94): the output is mostly verbatim copies of the input, so the two move together.
    # The defaults are measured (L184): 1.6 is the pinned model's worst observed ratio
    # (1.32) plus about 20%, so 12,500 chars buy 20,000 tokens. That budget must also fit
    # llm_timeout_s at the model's output throughput (L185), a bound no boot check can
    # see: the smoke run measures throughput at each pin.
    max_input_chars: int = Field(12_500, ge=1)
    min_input_chars: int = Field(20, ge=1)
    output_tokens_per_input_char: float = Field(1.6, gt=0, allow_inf_nan=False)

    # Two retry loops, two names (L5, invariant 16). Validation retries are ours (§5.4):
    # the model sees its mistake, so the next request differs. Transport retries are the
    # SDK's: transport failures — connection errors, timeouts, 429, 5xx (§5.2, L5).
    # Worst-case wall time per request ≈
    #     llm_timeout_s × (sdk_transport_retries + 1) × (max_validation_retries + 1)
    # because the SDK retries timeouts and each validation attempt can take nearly a full
    # window.
    max_validation_retries: int = Field(2, ge=0)
    sdk_transport_retries: int = Field(2, ge=0)
    llm_timeout_s: float = Field(90.0, gt=0, allow_inf_nan=False)  # L54

    # The judge (§8.2; L312, L314): one call per claim pair, at most judge_concurrency of a
    # note's calls in flight, each bounded by judge_timeout_s and retried by the SDK like
    # summarize's. A note's judge adds, at worst, about
    #     ceil(pairs / judge_concurrency) × judge_timeout_s × (sdk_transport_retries + 1)
    # and a corpus run's judges multiply the calls in flight by corpus_concurrency.
    judge_timeout_s: float = Field(15.0, gt=0, allow_inf_nan=False)  # L54, L314
    judge_concurrency: int = Field(4, ge=1)  # L314

    # Tier 3's floor (§6.3, L105): a rapidfuzz score, 0 to 100. allow_inf_nan=False makes a
    # non-finite value a finite_number error; ge and le alone report nan as less_than_equal.
    fuzzy_score_cutoff: float = Field(90.0, ge=0, le=100, allow_inf_nan=False)

    # quote_informativeness's floor (§8.4, L161): a span with fewer content tokens is
    # degenerate. 2 flags a bare name ("pain") and passes a terse statement ("hold metformin").
    min_quote_content_tokens: int = Field(2, ge=1)

    # 2b's corpus scorer (§8.7, L209). Each case runs corpus_repeats times (D11);
    # corpus_concurrency bounds the calls in flight, 1 until the account's rate limits are
    # known. A run appends its record to runs_path (§13). The two counts' bounds are the
    # record's own (L233).
    corpus_repeats: int = Field(3, ge=1)
    corpus_concurrency: int = Field(1, ge=1)
    runs_path: Path = Path("backend/evals/runs/corpus_runs.jsonl")

    def checks_config(self) -> ChecksConfig:
        """The verdict knobs, for the edge to pass inward: the domain reads no settings (L187)."""
        return ChecksConfig(
            fuzzy_score_cutoff=self.fuzzy_score_cutoff,
            min_quote_content_tokens=self.min_quote_content_tokens,
        )

    @property
    def max_output_tokens(self) -> int:
        """Derived, never a field (L94): a field could be set from the environment alone."""
        return math.ceil(self.max_input_chars * self.output_tokens_per_input_char)

    @field_validator("runs_path")
    @classmethod
    def _runs_path_is_jsonl(cls, value: Path) -> Path:
        """runs_path names a .jsonl file (L232): a run writes its record last, after it spends."""
        if value.suffix != ".jsonl":
            raise PydanticCustomError(
                "runs_path_not_jsonl",
                "runs_path={path} must name a .jsonl file: a run appends its record there "
                "after its calls are paid for, so a bad path would lose the record",
                {"path": str(value)},
            )
        return value

    @model_validator(mode="after")
    def _output_fits_model_ceiling(self) -> Self:
        """The derived output budget must not exceed what the model can emit (L16, L72)."""
        if self.max_output_tokens > self.model_max_output_tokens:
            raise PydanticCustomError(
                "output_ceiling_exceeded",
                "max_output_tokens={derived} (= ceil(max_input_chars={max_input_chars} x "
                "output_tokens_per_input_char={ratio})) exceeds "
                "model_max_output_tokens={ceiling}; lower max_input_chars or "
                "output_tokens_per_input_char, or raise model_max_output_tokens only if the "
                "model's real ceiling allows it",
                {
                    "derived": self.max_output_tokens,
                    "max_input_chars": self.max_input_chars,
                    "ratio": self.output_tokens_per_input_char,
                    "ceiling": self.model_max_output_tokens,
                },
            )
        return self

    @model_validator(mode="after")
    def _input_bounds_ordered(self) -> Self:
        """min_input_chars must leave room below max_input_chars (§10)."""
        if self.min_input_chars >= self.max_input_chars:
            raise PydanticCustomError(
                "input_bounds_inverted",
                "min_input_chars={min_input_chars} must be less than "
                "max_input_chars={max_input_chars}; lower min_input_chars or raise "
                "max_input_chars",
                {
                    "min_input_chars": self.min_input_chars,
                    "max_input_chars": self.max_input_chars,
                },
            )
        return self

    @model_validator(mode="after")
    def _judge_timeout_below_llm_timeout(self) -> Self:
        """The judge's per-call timeout is shorter than summarize's (§8.2, L54, L314)."""
        if self.judge_timeout_s >= self.llm_timeout_s:
            raise PydanticCustomError(
                "judge_timeout_not_below_llm_timeout",
                "judge_timeout_s={judge} must be less than llm_timeout_s={llm}; lower "
                "judge_timeout_s or raise llm_timeout_s",
                {"judge": self.judge_timeout_s, "llm": self.llm_timeout_s},
            )
        return self


settings = Settings()
