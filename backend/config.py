"""Every knob, validated at boot (spec §10).

Tests run with dotenv disabled; see tests/conftest.py.
"""

import os
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOTENV = None if os.environ.get("NOTEPILOT_IGNORE_DOTENV") == "1" else _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_DOTENV)

    anthropic_api_key: SecretStr
    model: str = "claude-haiku-4-5-20251001"
    mode_max_output_tokens: int = 64000


settings = Settings()
