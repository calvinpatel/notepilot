"""Env setup that must run before any test imports backend, the hypothesis profile, the
async-backend pin, and the registry fixture.

Settings is built at import time (spec §10).
"""

import os
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from hypothesis import settings

if TYPE_CHECKING:
    from backend.evals.registry import Check

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


@pytest.fixture
def registry() -> Iterator[dict[str, Check]]:
    """REGISTRY, emptied for the test and restored after it.

    In place, not rebound: a module that imported REGISTRY by name holds this same dict.
    Imported here, not at the top, so the env setup above runs before any backend import.
    """
    from backend.evals.registry import REGISTRY

    saved = dict(REGISTRY)
    REGISTRY.clear()
    yield REGISTRY
    REGISTRY.clear()
    REGISTRY.update(saved)
