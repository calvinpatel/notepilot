"""Canary for the async test runner.

Guards two things. The anyio pytest plugin is active: with it gone, pytest 9 fails this
test as an unsupported ``async def``. And the backend is pinned in conftest rather than
inherited from whatever is importable: the body only passes on an asyncio loop, and the
pinned fixture is not parametrized, so this collects as exactly one item with no
``[asyncio]`` suffix.

The test deliberately takes no parameters. Requesting ``anyio_backend`` would activate the
runner by itself (the plugin dispatches on funcargs) and make the marker redundant, so do
not "improve" it by asserting the fixture's value.
"""

import asyncio

import pytest


@pytest.mark.anyio
async def test_canary_runs_on_asyncio_loop() -> None:
    asyncio.get_running_loop()  # raises RuntimeError unless an asyncio loop is running
