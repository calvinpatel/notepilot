"""Env setup that must run before any test imports backend, the hypothesis profile, and
the async-backend pin.

Settings is built at import time (spec §10).
"""

import os

import pytest
from hypothesis import settings

# config.py skips .env when this is set, so local and CI test runs see identical settings
os.environ["NOTEPILOT_IGNORE_DOTENV"] = "1"
# assignment, not setdefault: a key exported in your shell must never reach tests
os.environ["ANTHROPIC_API_KEY"] = "test-dummy-key"


# The free tier is deterministic (spec §11, invariant 20). Hypothesis loads its own "ci"
# profile on GitHub Actions and a randomized one elsewhere; this one loads everywhere, so
# local runs and CI draw the same examples, with no wall-clock deadline to flake on.
settings.register_profile("deterministic", derandomize=True, deadline=None)
settings.load_profile("deterministic")


# Pins the anyio plugin's backend to asyncio.
# Why override: the plugin's default anyio_backend is parametrized over every importable
# backend, so installing trio would silently double every async test.
# Why session scope, not the plugin's module scope: a future module- or session-scoped
# async fixture can never hit ScopeMismatch on this pin.
# Mode stays the plugin default (strict): every async test carries @pytest.mark.anyio, and
# under pytest 9 an unmarked async test fails loudly, so a forgotten marker can't pass.
# Activation rule: async tests never request anyio_backend as a parameter. The plugin
# dispatches on funcargs, so requesting it activates the runner by itself and makes the
# marker redundant.
@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
