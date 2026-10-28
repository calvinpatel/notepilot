"""Pins the deploy's entrypoint (spec §9.8; L58, L352).

main hands uvicorn one worker, proxy headers, and settings' forwarded_allow_ips, each passed
explicitly. The two uvicorn behaviors it exists for are pinned too, so a uvicorn that changes
either fails here: unpassed, the worker count and the trust come from the environment; and
under a trust of *, the key is the client's own X-Forwarded-For entry.
"""

from typing import Any

import pytest
import uvicorn
from uvicorn.config import Config
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from backend import serve
from backend.config import settings


def test_main_passes_one_worker_proxy_headers_and_the_proxy_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Values no default reaches, so the test can't pass on the defaults.
    deployed = settings.model_copy(
        update={"host": "0.0.0.0", "port": 8080, "forwarded_allow_ips": "10.0.0.0/8"}
    )
    monkeypatch.setattr(serve, "settings", deployed)
    calls: list[tuple[str, dict[str, object]]] = []

    def run(app: str, **options: object) -> None:
        calls.append((app, options))

    monkeypatch.setattr(uvicorn, "run", run)
    serve.main()
    assert calls == [
        (
            "backend.api:app",
            {
                "host": "0.0.0.0",
                "port": 8080,
                "workers": 1,
                "proxy_headers": True,
                "forwarded_allow_ips": "10.0.0.0/8",
            },
        )
    ]


def test_uvicorn_reads_unpassed_workers_and_trust_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Why main passes both: unpassed, uvicorn takes them from the environment.
    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    unpassed = Config("backend.api:app")
    passed = Config("backend.api:app", workers=1, forwarded_allow_ips="10.0.0.0/8")
    assert (unpassed.workers, unpassed.forwarded_allow_ips) == (4, "*")
    assert (passed.workers, passed.forwarded_allow_ips) == (1, "10.0.0.0/8")


async def _keyed(trusted: str, forwarded_for: str) -> str:
    """The client address uvicorn's proxy headers hand the app, for a request from 10.0.0.5.

    The app, the scope, and the channels are Any: uvicorn's ASGI types and Starlette's don't
    unify, and the middleware reads only the scope's type, client, and headers.
    """
    seen: list[str] = []

    async def app(scope: Any, receive: Any, send: Any) -> None:
        seen.append(scope["client"][0])

    scope: Any = {
        "type": "http",
        "client": ("10.0.0.5", 50000),
        "headers": [(b"x-forwarded-for", forwarded_for.encode())],
    }
    channel: Any = None  # the middleware hands both to the app, which reads neither
    await ProxyHeadersMiddleware(app, trusted)(scope, channel, channel)
    (key,) = seen
    return key


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("trusted", "key"),
    [
        ("10.0.0.0/8", "203.0.113.7"),
        ("*", "6.6.6.6"),
        ("10.0.0.5/8", "10.0.0.5"),
        ("10.0.0.0/8,*", "203.0.113.7"),
        (" * ", "10.0.0.5"),
    ],
    ids=["range", "any", "host-bits-set", "listed-any", "padded-any"],
)
async def test_a_range_keys_the_real_client_and_any_keys_the_clients_own_entry(
    trusted: str, key: str
) -> None:
    # The client sent 6.6.6.6 and the proxy, at 10.0.0.5, appended the real 203.0.113.7: a
    # range walks from the right to the real client; * takes the client's entry (L352). An
    # entry uvicorn can't parse trusts nothing: a network with host bits set, or a * that
    # isn't the whole value, which a range beside it outlives.
    assert await _keyed(trusted, "6.6.6.6, 203.0.113.7") == key
