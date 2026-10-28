"""The deploy's entrypoint (§9.8, L352): `python -m backend.serve`.

uvicorn reads WEB_CONCURRENCY and FORWARDED_ALLOW_IPS from the environment whenever they
aren't passed, and either would undo the deploy: N workers keep N counters, so N times the
daily cap (§9.8), and a trust of * keys the rate limit by the client's own X-Forwarded-For
entry. So main passes both, with proxy headers on: one worker, and settings'
forwarded_allow_ips, which boot has checked. EDGE: settings and uvicorn, nothing else.
"""

import uvicorn

from backend.config import settings


def main() -> None:
    """Serves backend.api's app until the process stops."""
    uvicorn.run(
        "backend.api:app",
        host=settings.host,
        port=settings.port,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips=settings.forwarded_allow_ips,
    )


if __name__ == "__main__":
    main()
