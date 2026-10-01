"""Every knob, validated at boot (spec §10).

Tests run with dotenv disabled; see tests/conftest.py.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _dotenv_path(env: Mapping[str, str]) -> Path | None:
    """The .env file to load, or None when NOTEPILOT_IGNORE_DOTENV is exactly "1"."""
    if env.get("NOTEPILOT_IGNORE_DOTENV") == "1":
        return None
    return _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_dotenv_path(os.environ))

    anthropic_api_key: SecretStr
    model: str = "claude-haiku-4-5-20251001"
    model_max_output_tokens: int = 64000


settings = Settings()
