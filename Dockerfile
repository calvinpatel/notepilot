# The deploy's image (§9.8, L353): python -m backend.serve over the locked runtime
# dependencies. CI's image job builds it, boots it, and checks it (§11). Each image is
# pinned by the digest its tag resolved to in CI's first build; the tag stays as a label.
FROM python:3.14.8-slim@sha256:fbecd461fc72d21b2143c6eaba25143738079154a6d0ea3da3aec724f50eed4a

# uv from its own image; the base image's Python, never a download.
COPY --from=ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b /uv /bin/uv
ENV UV_PYTHON_DOWNLOADS=never

# The image's repo root and its working directory, as in a checkout: config.py reads .env
# from the repo root and slowapi from the working directory (L349), and .dockerignore keeps
# .env out of the build context.
WORKDIR /app

# Two layers: the locked dependencies, then backend/.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev
COPY backend/ backend/

# The server runs as uid 10001, not root.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin notepilot
USER 10001

# Every interface, so the platform's proxy reaches the server. PORT is the platform's to
# set; unset, the setting's default is 8000 (§10).
ENV HOST=0.0.0.0
# Exec form: Python is PID 1, so a stop's SIGTERM reaches uvicorn, which shuts down.
CMD ["/app/.venv/bin/python", "-m", "backend.serve"]
