"""Pins config wiring (spec §10).

Settings is built at import time, so these tests see the environment
conftest set before backend was first imported.
"""

from backend.config import settings


def test_dotenv_disabled_under_pytest():
    assert settings.model_config.get("env_file") is None
