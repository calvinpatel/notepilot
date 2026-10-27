"""Every knob, validated at boot (spec §10).

Every field declares its domain (L77). `max_output_tokens` is a read-only property derived
from `max_input_chars` and `output_tokens_per_input_char` (L94), checked against the model's
declared output ceiling at construction (L16, L72); `max_request_tokens`, what the daily
budget reserves per request, is derived beside it (L348). Boot checks beyond the fields'
bounds, each a validation error: the derived output ceiling, the input bounds, runs_path's
.jsonl name (L232), a judge timeout below summarize's (L314), with persist_enabled a
database_url on the asyncpg driver (L341), a rate_limit that parses and admits a request,
and, with a daily budget, no judge (L332), one validation attempt, and room for one request
(L348). A boot error names its rule, never the input, which holds the key and the database
password (L341).

Tests run with dotenv disabled; see tests/conftest.py.
"""

import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Self

from limits import parse_many
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.schemas import ChecksConfig

_REPO_ROOT = Path(__file__).resolve().parent.parent


# The reservation's measured terms (§9.8, L348): count_tokens on summarize's exact request
# (system prompt, tool, forced tool choice, message form), Oct 27. A 20-character paste cost
# 1,689 input tokens; past it, the costliest script measured 4.005 tokens per character
# (supplementary-plane code points, about one token per UTF-8 byte), clinical English 0.421.
# The factor is that worst case plus a margin, since the counts are estimates. Both terms
# belong to one prompt on one model's tokenizer: a test fails when either moves.
RESERVATION_MEASURED_AT: Final = ("claude-haiku-5-5", "306bbaa5126a")  # model, PROMPT_VERSION
RESERVATION_PROMPT_TOKENS: Final = 1_689
RESERVATION_TOKENS_PER_INPUT_CHAR: Final = 4.1


def _dotenv_path(env: Mapping[str, str]) -> Path | None:
    """The .env file to load, or None when NOTEPILOT_IGNORE_DOTENV is exactly "1"."""
    if env.get("NOTEPILOT_IGNORE_DOTENV") == "1":
        return None
    return _REPO_ROOT / ".env"


class Settings(BaseSettings):
    # frozen: a mutable settings object could bypass the boot checks after construction.
    # hide_input_in_errors (L341): a failed check's message would otherwise end with the raw
    # input, the key and the database URL's password among it (invariant 19).
    model_config = SettingsConfigDict(
        env_file=_dotenv_path(os.environ), frozen=True, hide_input_in_errors=True
    )

    # min_length=1 and nothing else, ever. hide_input_in_errors keeps the input out of an
    # error's message, but errors() still carries it, so a check that can reject a non-empty
    # key could leak it wherever errors() were logged (invariant 19). min_length=1 can only
    # reject "".
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
    #     + ceil(pairs / judge_concurrency) × judge_timeout_s × (sdk_transport_retries + 1)
    # because the SDK retries timeouts, each validation attempt can take nearly a full
    # window, and with the judge on (L318) a note's pair calls follow summarize.
    max_validation_retries: int = Field(2, ge=0)
    sdk_transport_retries: int = Field(2, ge=0)
    llm_timeout_s: float = Field(90.0, gt=0, allow_inf_nan=False)  # L54

    # The judge (§8.2; L312, L314, L318): off unless judge_enabled; one call per claim pair,
    # at most judge_concurrency of a note's calls in flight, each bounded by judge_timeout_s
    # and retried by the SDK like summarize's (its term is in the formula above). A corpus
    # run's judges multiply the calls in flight by corpus_concurrency.
    judge_enabled: bool = False  # read per request, at the edge (L318)
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

    # Persistence (§9.5, §9.6): off unless persist_enabled, as the public demo runs it (§9.8).
    # database_url is the asyncpg DSN, a secret because it carries the password (L341).
    persist_enabled: bool = False
    database_url: SecretStr | None = None

    # The wallet (§9.8): a per-IP rate limit, a slowapi limit string such as "5/minute", and
    # a daily token budget the route reserves against before any call (L56). Unset, a local
    # run has neither; the deploy sets both (L348).
    rate_limit: str | None = None
    daily_token_budget: int | None = Field(None, ge=1)

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

    @property
    def max_request_tokens(self) -> int:
        """What the daily budget reserves per request (§9.8, L56): one attempt's worst case.

        One attempt, since boot refuses a budget with validation retries (L348): the measured
        prompt overhead, the measured bound per pasted character, and the output ceiling.
        """
        return (
            RESERVATION_PROMPT_TOKENS
            + math.ceil(self.max_input_chars * RESERVATION_TOKENS_PER_INPUT_CHAR)
            + self.max_output_tokens
        )

    @field_validator("rate_limit")
    @classmethod
    def _rate_limit_admits_requests(cls, value: str | None) -> str | None:
        """rate_limit parses as slowapi's limits read it, and every limit admits a request."""
        if value is None:
            return value
        try:
            limits = parse_many(value)
        except ValueError:
            limits = []
        if not limits or any(limit.amount < 1 for limit in limits):
            raise PydanticCustomError(
                "rate_limit_invalid",
                "rate_limit={value} must be a limit string such as 5/minute, each limit at "
                "least 1 (§9.8)",
                {"value": value},
            )
        return value

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

    @model_validator(mode="after")
    def _database_url_when_persisting(self) -> Self:
        """persist_enabled needs a database_url on the asyncpg driver (§9.8, L341).

        Without one, persist() would fail on every request, logged and swallowed (§9.6).
        Neither message shows the URL: it carries the password.
        """
        if not self.persist_enabled:
            return self
        if self.database_url is None:
            raise PydanticCustomError(
                "database_url_missing",
                "persist_enabled needs database_url; set it, or leave persist_enabled off",
                {},
            )
        if not self.database_url.get_secret_value().startswith("postgresql+asyncpg://"):
            raise PydanticCustomError(
                "database_url_not_asyncpg",
                "database_url must name the postgresql+asyncpg:// driver (§9.8)",
                {},
            )
        return self

    @model_validator(mode="after")
    def _no_judge_under_a_budget(self) -> Self:
        """The reservation charges summarize alone, so a budget runs no judge (L332)."""
        if self.daily_token_budget is not None and self.judge_enabled:
            raise PydanticCustomError(
                "judge_under_budget",
                "judge_enabled with daily_token_budget set: the reservation charges summarize "
                "alone, so the judge would spend outside the cap (§9.8, L332)",
                {},
            )
        return self

    @model_validator(mode="after")
    def _one_attempt_under_a_budget(self) -> Self:
        """A budget reserves one attempt: a retry's correction quotes the invalid output (L348)."""
        if self.daily_token_budget is not None and self.max_validation_retries > 0:
            raise PydanticCustomError(
                "retries_under_budget",
                "max_validation_retries={retries} with daily_token_budget set: a retry's "
                "correction quotes the invalid output, which nothing bounds, so a budget "
                "reserves one attempt; set max_validation_retries=0 (§9.8, L348)",
                {"retries": self.max_validation_retries},
            )
        return self

    @model_validator(mode="after")
    def _budget_admits_a_request(self) -> Self:
        """A budget below one request's reservation would answer 503 to every request."""
        budget, reservation = self.daily_token_budget, self.max_request_tokens
        if budget is not None and budget < reservation:
            raise PydanticCustomError(
                "budget_below_one_request",
                "daily_token_budget={budget} is below max_request_tokens={reservation}: no "
                "request could reserve; raise the budget or lower max_input_chars (L348)",
                {"budget": budget, "reservation": reservation},
            )
        return self


settings = Settings.model_validate({})
