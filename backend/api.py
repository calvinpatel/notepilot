"""The HTTP edge: the app, its routes, and the input boundary (spec §9.1, §9.4, §9.8, §9.10).

EDGE adapter (spec §0): FastAPI's types appear here and nowhere inward. The /summarize route
is a composition root with no logic (§9.1): it awaits summarize() and returns the wire shape.
SummarizeRequest and SummarizeResponse are the HTTP edge shapes §13 sanctions outside
schemas.py; SummarizationResult never goes on the wire (L76).

GET / serves backend/static/index.html, the phase-1 page (§9.10, L68), by a path derived
from this file, never from the cwd. The page renders the model's claims, and a source_quote
copies the paste, so markup in a paste would execute through a string-to-HTML sink. The
served page contains none of innerHTML, outerHTML, insertAdjacentHTML, or document.write.

SummarizeRequest counts CONTENT (stripped length, L87) and never mutates raw_text: §6.2's
source spans are offsets into the exact paste. An oversized paste fails honestly at
max_length (§9.1).

A RequestValidationError becomes 422 {"error": "input_invalid", "request_id": ...} and is
logged by code only (L70). FastAPI's default handler echoes the paste as `input` whenever
the body parses; this one never reads exc.errors(), str(exc), or the body (L53,
invariant 19).

Framework errors take the same shape (L80, L98). A handler on
starlette.exceptions.HTTPException, the class the router raises, returns {"error": <code>,
"request_id": ...} with the original status and the exception's headers, so a 405 keeps the
Allow header RFC 9110 requires: 404 not_found, 405 method_not_allowed, anything else
http_error. It is logged by code and status, never exc.detail.

A ModelOutputError becomes 502 with the exception's own code (L14, L73): OutputTruncatedError
reaches the same handler by MRO and reports output_truncated. It is logged by code only,
never with exc_info or the message: a ValidationError chained as __cause__ carries
model-emitted text (L53, invariant 19).

Anthropic SDK failures are attributed by whose fault they are (L54, L71, L99), one handler
per class, resolved by MRO. RateLimitError is 503 upstream_busy, with upstream's Retry-After
when it sent one. APIStatusError is decided by its status, never its subclass, and totally:
429 and 529 are 503 upstream_busy, any other 4xx is 500 internal_error at ERROR (our request
or config), and any other status is 502 upstream_error. APITimeoutError, our own client's
timeout, is 504 upstream_timeout; any other APIError, a non-timeout connection failure
included, is 502 upstream_error. Each logs one upstream_failure line with the code and the
request id, then upstream_status (the two status-error handlers) or exc_type (the other
two). None reads the exception's message, its body, or its request, whose content is the
whole paste; the one header read is RateLimitError's Retry-After.

request_id is minted per request by RequestIdMiddleware (L73), a pure ASGI middleware, on
request.state. The root logger is configured once here (§9.8): plain text with timestamp,
level, and logger name; fields render in the message as key=value pairs via %-style args,
never extra= (L79).

Any exception no handler claims is caught by CatchAllMiddleware (L69), a pure ASGI
middleware inside RequestIdMiddleware and outside Starlette's ExceptionMiddleware. It logs
ONE ERROR line: the code, the request id, the exception's type name, and the traceback's
frames as file:line:function. It never logs the message, the chained cause, or exc_info:
each can carry the paste or model-emitted text (L53, invariant 19). If the response has not
started it sends 500 {"error": "internal_error", "request_id": ...}; if it has, it returns.
It never re-raises: past it, ServerErrorMiddleware re-raises for the server, and uvicorn
logs the full traceback, message and chained cause included.
"""

import logging
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Final
from uuid import uuid4

from anthropic import APIError, APIStatusError, APITimeoutError, RateLimitError
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.config import settings
from backend.orchestrator import LLMClient, ModelOutputError, get_client, summarize
from backend.schemas import RunMetadata, SOAPNoteDraft

# §9.8 (L79): configured once, at app construction. Every field a log call carries goes in
# the message as key=value via %-style args. Never extra=: with no custom formatter it
# attaches attributes to the record that no handler prints.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


class RequestIdMiddleware:
    """Mints request.state.request_id = uuid4().hex per HTTP request (L73).

    Pure ASGI, not BaseHTTPMiddleware: it touches the scope and nothing else. Registered
    with add_middleware, so it runs outside ExceptionMiddleware and every handler sees the
    id. Non-http scopes pass through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope.setdefault("state", {})["request_id"] = uuid4().hex
        await self.app(scope, receive, send)


# Frames render repo files relative to this root (L69). Derived from this file, never from
# sys.path or the cwd: under uvicorn sys.path[0] is '', under pytest the absolute repo root,
# so a sys.path-relative file would render differently in tests than in production.
_REPO_ROOT: Final = Path(__file__).resolve().parents[1]


def _display_path(filename: str) -> str:
    """A frame's file, shortened: after site-packages, relative to the repo, or a basename.

    site-packages is checked first: .venv sits inside the repo root, so the repo-relative
    form of an installed module would start with .venv/lib/.../site-packages/.
    """
    path = Path(filename)
    parts = path.parts
    if "site-packages" in parts:
        return "/".join(parts[parts.index("site-packages") + 1 :])
    if path.is_relative_to(_REPO_ROOT):
        return path.relative_to(_REPO_ROOT).as_posix()
    return path.name


def _frames(exc: Exception) -> str:
    """The traceback as file:line:function entries, outermost first, joined by '>' (L69).

    Frames carry no PHI; the message and the chained cause can (a ValidationError carries
    input_value), so frames and the type name are all the 500 path records about it.
    """
    return ">".join(
        f"{_display_path(frame.filename)}:{frame.lineno}:{frame.name}"
        for frame in traceback.extract_tb(exc.__traceback__)
    )


class CatchAllMiddleware:
    """Any Exception no handler claims becomes 500 internal_error, logged by structure (L69).

    Pure ASGI, inside RequestIdMiddleware (it reads the id) and outside ExceptionMiddleware
    (it sees only what no handler took). Not @app.exception_handler(Exception): Starlette's
    ServerErrorMiddleware calls that handler and then re-raises, so the server logs the full
    traceback anyway. Logs the code, the request id, the exception's type name, and its
    frames; never str(exc), exc.args, the chained cause, or exc_info (L53, invariant 19).

    If the response has already started it logs and returns: a 500 can't follow a started
    response, and re-raising hands the exception to ServerErrorMiddleware and the server's
    exc_info log. Non-http scopes pass through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            # minted by RequestIdMiddleware, which wraps this one (test_user_middleware_order)
            rid: str = scope["state"]["request_id"]
            code = "internal_error"
            # frames last: a stray space in a file name can't corrupt the other fields
            logger.error(
                "unhandled_exception code=%s request_id=%s exc_type=%s frames=%s",
                code,
                rid,
                type(exc).__name__,
                _frames(exc),
            )
            if started:
                return
            response = JSONResponse(status_code=500, content={"error": code, "request_id": rid})
            await response(scope, receive, send)


app = FastAPI(title="NotePilot")
# add_middleware inserts at index 0, so the last call is outermost: RequestIdMiddleware wraps
# CatchAllMiddleware, which reads the id it minted.
app.add_middleware(CatchAllMiddleware)
app.add_middleware(RequestIdMiddleware)

# Derived from this file, never the cwd (§9.10, L68).
_INDEX_HTML: Final = Path(__file__).resolve().parent / "static" / "index.html"


@app.get("/")
async def index() -> FileResponse:
    """The phase-1 page (§9.10, L68)."""
    return FileResponse(_INDEX_HTML)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class SummarizeRequest(BaseModel):
    """HTTP-boundary shape (§9.1); sanctioned outside schemas.py by §13."""

    # An oversized paste fails honestly at validation (422); chunking to accept one is a
    # deliberate non-feature (§9.8, §15).
    raw_text: str = Field(max_length=settings.max_input_chars)

    @field_validator("raw_text")
    @classmethod
    def _enough_content(cls, v: str) -> str:
        # L87: the degenerate-input guard (§10) counts CONTENT, and never mutates: §6.2
        # defines source spans as offsets into the exact paste, so stripping here would
        # shift every one of them. settings is read at call time.
        if len(v.strip()) < settings.min_input_chars:
            raise ValueError("too short")
        return v


class SummarizeResponse(BaseModel):
    """The wire shape, exactly {draft, metadata} (L76): an edge type, not the domain's."""

    draft: SOAPNoteDraft
    metadata: RunMetadata


@app.post("/summarize")
async def summarize_endpoint(
    req: SummarizeRequest, client: Annotated[LLMClient, Depends(get_client)]
) -> SummarizeResponse:
    """Composition root (§9.1): wires the pipeline in order; no logic lives here."""
    result = await summarize(req.raw_text, client=client)
    return SummarizeResponse(draft=result.draft, metadata=result.metadata)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422 input_invalid (§9.4, L70): the INPUT is the problem.

    Never reads exc.errors(), str(exc), or the body: the errors carry the paste as `input`
    (L53, invariant 19). The body has §9.4's one shape; the log line carries the code and
    the request id in the message (L79).
    """
    rid: str = request.state.request_id
    code = "input_invalid"
    logger.warning("input_rejected code=%s request_id=%s", code, rid)
    return JSONResponse(status_code=422, content={"error": code, "request_id": rid})


# Framework codes (L80): not rows of §9.4's table, and not part of the phase-1 reach list.
_FRAMEWORK_CODES: Final[Mapping[int, str]] = {404: "not_found", 405: "method_not_allowed"}


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Framework errors, §9.4's one shape (L80, L98): not_found, method_not_allowed, or http_error.

    Registered on Starlette's class, not FastAPI's: the router raises the Starlette one, and
    handlers resolve by MRO, so a FastAPI-class registration would never see a 404 or 405.
    The headers are protocol, not content: the router's 405 carries Allow, which RFC 9110
    requires (L98). Never reads exc.detail, the path, or the body (invariant 19). No branch
    for bodiless statuses (204, 304, 1xx): nothing here raises one.
    """
    rid: str = request.state.request_id
    code = _FRAMEWORK_CODES.get(exc.status_code, "http_error")
    logger.warning("framework_error code=%s status=%d request_id=%s", code, exc.status_code, rid)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": code, "request_id": rid},
        headers=exc.headers,
    )


@app.exception_handler(ModelOutputError)
async def handle_model_output_error(request: Request, exc: ModelOutputError) -> JSONResponse:
    """502 with the exception's own code (§9.4; L14, L73): the MODEL is the problem.

    exc.code, never a literal: OutputTruncatedError subclasses ModelOutputError, reaches this
    handler by MRO, and reports output_truncated. It never reads str(exc), the chained cause,
    or exc.usage, and never logs with exc_info: the cause can be a ValidationError carrying
    model-emitted text as input_value (L53, invariant 19).
    """
    rid: str = request.state.request_id
    logger.warning("model_output_failure code=%s request_id=%s", exc.code, rid)  # L79
    return JSONResponse(status_code=502, content={"error": exc.code, "request_id": rid})


@app.exception_handler(RateLimitError)
async def handle_rate_limit_error(request: Request, exc: RateLimitError) -> JSONResponse:
    """503 upstream_busy (§9.4): upstream throttled US; 429 is reserved for our own limit.

    Retry-After is protocol, not content (L98): forwarded verbatim when upstream sent one,
    never parsed, never tested for truthiness. Forwarding it is the one behavior this handler
    does not share with the status handler's 429 branch (L99). Of the exception it reads only
    the status code, for the log line, and the Retry-After header (invariant 19).
    """
    rid: str = request.state.request_id
    code = "upstream_busy"
    logger.warning(
        "upstream_failure code=%s request_id=%s upstream_status=%d", code, rid, exc.status_code
    )
    retry_after = exc.response.headers.get("retry-after")
    headers = None if retry_after is None else {"Retry-After": retry_after}
    return JSONResponse(
        status_code=503, content={"error": code, "request_id": rid}, headers=headers
    )


# L71, L99: overloaded and throttled mean the same thing to our client: upstream is busy.
_BUSY_STATUSES: Final[frozenset[int]] = frozenset({429, 529})


@app.exception_handler(APIStatusError)
async def handle_api_status_error(request: Request, exc: APIStatusError) -> JSONResponse:
    """Attributed by the status, never the subclass, and total over every int (§9.4; L71, L99).

    RateLimitError's handler claims the SDK's 429s first by MRO, so a 429 here is the base
    class; the busy check runs first because 429 is also a 4xx. ERROR only on the 500 branch:
    a 4xx is OUR request or config. It forwards no headers (L99). Of the exception it reads
    only the status code: never str(exc), exc.message, exc.body, exc.request, the response
    body, or the cause (invariant 19).
    """
    rid: str = request.state.request_id
    upstream = exc.status_code
    if upstream in _BUSY_STATUSES:
        status, code, level = 503, "upstream_busy", logging.WARNING
    elif 400 <= upstream < 500:
        status, code, level = 500, "internal_error", logging.ERROR
    else:  # 5xx, and any status outside 4xx/5xx (L99)
        status, code, level = 502, "upstream_error", logging.WARNING
    logger.log(
        level, "upstream_failure code=%s request_id=%s upstream_status=%d", code, rid, upstream
    )
    return JSONResponse(status_code=status, content={"error": code, "request_id": rid})


@app.exception_handler(APITimeoutError)
async def handle_api_timeout_error(request: Request, exc: APITimeoutError) -> JSONResponse:
    """504 upstream_timeout (§9.4, L54): OUR client gave up waiting (llm_timeout_s).

    An upstream 504 is a status, and takes the status handler as upstream's error (L99); this
    is the client-side timeout only. Of the exception it reads nothing but its type name:
    never str(exc), exc.message, exc.request, or the cause (invariant 19).
    """
    rid: str = request.state.request_id
    code = "upstream_timeout"
    logger.warning(
        "upstream_failure code=%s request_id=%s exc_type=%s", code, rid, type(exc).__name__
    )
    return JSONResponse(status_code=504, content={"error": code, "request_id": rid})


@app.exception_handler(APIError)
async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
    """502 upstream_error (§9.4, L71): any other API failure, non-timeout connection ones included.

    Logs exc_type because with no status to branch on, the type is what tells these failures
    apart. Of the exception it reads nothing but its type name: never str(exc), exc.message,
    exc.body, exc.request, or the cause (invariant 19).
    """
    rid: str = request.state.request_id
    code = "upstream_error"
    logger.warning(
        "upstream_failure code=%s request_id=%s exc_type=%s", code, rid, type(exc).__name__
    )
    return JSONResponse(status_code=502, content={"error": code, "request_id": rid})
