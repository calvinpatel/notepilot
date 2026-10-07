"""Every knob, validated at boot (spec §10).

Every field declares its domain (L77). `max_output_tokens` is a read-only property derived
from `max_input_chars` and `output_tokens_per_input_char` (L94), checked against the model's
declared output ceiling at construction (L16, L72). Two boot checks, both as validation
errors: the derived output ceiling and the input bounds.

Tests run with dotenv disabled; see tests/conftest.py.
"""

import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _dotenv_path(env: Mapping[str, str]) -> Path | None:
    """The .env file to load, or None when NOTEPILOT_IGNORE_DOTENV is exactly "1"."""
    if env.get("NOTEPILOT_IGNORE_DOTENV") == "1":
        return None
    return _REPO_ROOT / ".env"


class Settings(BaseSettings):
    # frozen: a mutable settings object could bypass both boot checks after construction.
    model_config = SettingsConfigDict(env_file=_dotenv_path(os.environ), frozen=True)

    # min_length=1 and nothing else, ever. A failed constraint prints input_value in the
    # boot traceback, so any check that can reject a non-empty key would leak it into logs
    # (invariant 19). min_length=1 can only reject "".
    anthropic_api_key: SecretStr = Field(min_length=1)  # required (L77)

    # A pinned model id (L84) — never an alias, never validated with a date regex. Its
    # output ceiling is declared directly beside it: the two change together (L72); the
    # phase-1 smoke run verifies the declaration against the Models API (L85).
    model: str = Field("claude-haiku-4-5-20251001", min_length=1)
    model_max_output_tokens: int = Field(64_000, gt=0)

    # Input bounds (§10). max_output_tokens is derived from max_input_chars via the ratio
    # (L94): the output is mostly verbatim copies of the input, so the two move together.
    max_input_chars: int = Field(20_000, ge=1)
    min_input_chars: int = Field(20, ge=1)
    output_tokens_per_input_char: float = Field(0.5, gt=0, allow_inf_nan=False)

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

    # Tier 3's floor (§6.3, L105): a rapidfuzz score, 0 to 100. allow_inf_nan=False makes a
    # non-finite value a finite_number error; ge and le alone report nan as less_than_equal.
    fuzzy_score_cutoff: float = Field(90.0, ge=0, le=100, allow_inf_nan=False)

    @property
    def max_output_tokens(self) -> int:
        """Derived, never a field (L94): a field could be set from the environment alone."""
        return math.ceil(self.max_input_chars * self.output_tokens_per_input_char)

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


settings = Settings()
