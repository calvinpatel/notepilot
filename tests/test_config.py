"""Pins config wiring (spec §10).

Settings is built at import time, so test_dotenv_disabled_under_pytest sees the
environment conftest set before backend was first imported. _dotenv_path is pure,
so its branches are tested directly with a passed-in environment.
"""

import pytest

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
