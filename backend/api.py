"""The HTTP edge: the app, its routes, and the input boundary (spec §9.1, §9.4, §9.8, §9.10).

EDGE adapter (spec §0): FastAPI's types appear here and nowhere inward. The /summarize route
is a composition root with no logic (§9.1): it awaits summarize(), grounds the draft against
the exact paste, awaits run_checks() in production mode, and returns the wire shape (L166).
SummarizeRequest, SummarizeResponse, and ErrorBody are the HTTP edge shapes §13 sanctions
outside schemas.py; SummarizationResult never goes on the wire (L76).

GET / serves backend/static/index.html, the phase-1 page (§9.10, L68), by a path derived
from this file, never from the cwd. The page renders the model's claims, and a source_quote
copies the paste, so markup in a paste would execute through a string-to-HTML sink. The
served page contains none of innerHTML, outerHTML, insertAdjacentHTML, or document.write.

SummarizeRequest counts CONTENT (stripped length, L87) and never mutates raw_text: §6.2's
source spans are offsets into the exact paste. An oversized paste fails honestly at
max_length (§9.1).

Admission comes before any call (§9.8, L350). admit, a dependency of the route, takes the
validated request, so a paste that fails validation never reaches it. It checks the client's
rate limit through slowapi first, so a request over its limit reserves nothing; then it
reserves the day's worst case against the daily budget, and returns the request it admitted.
Each defense is off while its setting is unset. RateLimitExceeded becomes 429 rate_limited, with
Retry-After the seconds until the client's window resets; BudgetExhaustedError becomes 503
budget_exhausted, with Retry-After the seconds until the next UTC midnight. Each logs one
admission_refused line with the code, the request id, and the Retry-After.

A request the route completes logs one INFO line, request_completed (L351): the request id,
the note id, the model, wall_s (the route's, summarize through the checks), summarize_wall_s
(summarize's alone, as the corpus measures it), the validation attempts, and summarize's and
the judge's token counts. Ids and numbers only (L53, invariant 19).

Every error body is an ErrorBody (L358): the code, an ErrorCode, and the request id.
_error_response builds one, so mypy checks the code each handler names; the 502 handler's
code is the orchestrator's str, which ErrorBody checks at run time. /openapi.json
documents ErrorBody for each status /summarize answers, described by that status's codes, and
for a 500 on every route, which the catch-all can answer. Declaring the 422 drops FastAPI's
default HTTPValidationError, a body the API never sends.

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
429 and 529 are 503 upstream_busy, 408 and 409 are 502 upstream_error at WARNING (an
intermediary's, after the SDK's retries; L255), any other 4xx is 500 internal_error at ERROR
(our request or config), and any other status is 502 upstream_error. APITimeoutError, our
own client's timeout, is 504 upstream_timeout; any other APIError, a non-timeout connection
failure included, is 502 upstream_error. Each logs one upstream_failure line with the code
and the request id, then upstream_status (the two status-error handlers) or exc_type (the
other two). None reads the exception's message, its body, or its request, whose content is
the whole paste; the one header read is RateLimitError's Retry-After.

With cors_origins set, CORSMiddleware lets a page on a listed origin call the API, the React
dev server's among them (§9.8, L359): POST with Content-Type, and Retry-After exposed so the
page can read a 429's or a budget 503's wait. Registered last, it is the outermost
middleware, so its headers reach every response, the catch-all's 500 included. Starlette
answers a preflight itself, in plain text, the one body outside §9.4's shape. Unset, it isn't
registered: the deploy's page shares the API's origin, and an OPTIONS request keeps §9.4's
405 body.

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

import asyncio
import functools
import logging
import math
import time
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any, Final, Literal
from uuid import UUID, uuid4

from anthropic import APIError, APIStatusError, APITimeoutError, RateLimitError
from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.config import settings
from backend.db import get_sessions, persist
from backend.evals.judge import Judge
from backend.evals.runner import run_checks
from backend.grounding import ground
from backend.judge_client import get_judge
from backend.orchestrator import LLMClient, ModelOutputError, get_client, summarize
from backend.schemas import EvalReport, RunMetadata, SOAPNote
from backend.tracebacks import format_frames

# §9.8 (L79): configured once, at app construction. Every field a log call carries goes in
# the message as key=value via %-style args. Never extra=: with no custom formatter it
# attaches attributes to the record that no handler prints.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


# --- §9.4's one error shape (L358) -----------------------------------------------------

# Every code an error body carries: §9.4's table, and the framework's three (L80).
ErrorCode = Literal[
    "input_invalid",
    "rate_limited",
    "budget_exhausted",
    "output_truncated",
    "model_output_invalid",
    "upstream_busy",
    "upstream_timeout",
    "upstream_error",
    "internal_error",
    "not_found",
    "method_not_allowed",
    "http_error",
]


class ErrorBody(BaseModel):
    """§9.4's one error shape: the code and the request id, never a message (L53, L358)."""

    error: ErrorCode
    request_id: str


def _error_response(
    status: int, code: ErrorCode, rid: str, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    """The status, with ErrorBody(code, rid) as its body and the headers when given."""
    body = ErrorBody(error=code, request_id=rid)
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


def _documented(errors: Mapping[int, tuple[ErrorCode, ...]]) -> dict[int | str, dict[str, Any]]:
    """FastAPI's responses= for errors: each status as ErrorBody, described by its codes."""
    return {
        status: {"model": ErrorBody, "description": ", ".join(codes)}
        for status, codes in errors.items()
    }


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
            code: ErrorCode = "internal_error"
            # frames last: a stray space in a file name can't corrupt the other fields
            logger.error(
                "unhandled_exception code=%s request_id=%s exc_type=%s frames=%s",
                code,
                rid,
                type(exc).__name__,
                format_frames(exc),
            )
            if started:
                return
            await _error_response(500, code, rid)(scope, receive, send)


# The catch-all can answer any route (L69), so each documents a 500 (L358).
_ANY_ROUTE_ERRORS: Final[Mapping[int, tuple[ErrorCode, ...]]] = {500: ("internal_error",)}

app = FastAPI(title="NotePilot", responses=_documented(_ANY_ROUTE_ERRORS))
# add_middleware inserts at index 0, so the last call is outermost: RequestIdMiddleware wraps
# CatchAllMiddleware, which reads the id it minted.
app.add_middleware(CatchAllMiddleware)
app.add_middleware(RequestIdMiddleware)
# L359: last, so outermost; its headers reach every response, the catch-all's 500 included.
if settings.cors_origins is not None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
        expose_headers=["Retry-After"],
    )

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
    """The wire shape, exactly {note_id, note, report, metadata} (L76, L166): an edge type."""

    note_id: UUID
    note: SOAPNote
    report: EvalReport
    metadata: RunMetadata


# --- admission: the rate limit, then the reservation (§9.8, L350) -----------------------

# §9.8's per-IP rate limit, in this process's memory, keyed by the client's address
# (slowapi's get_remote_address). Boot refuses the environment slowapi would read (L349).
limiter = Limiter(key_func=get_remote_address)


def _rate_limit() -> str:
    """The limit string, read per request; admit checks the limit only when one is set."""
    return settings.rate_limit or ""


@limiter.limit(_rate_limit)
async def _count_against_rate_limit(request: Request) -> None:
    """Empty: slowapi's decorator counts the request against the client's limit before this
    runs, and raises RateLimitExceeded past it."""


class BudgetExhaustedError(Exception):
    """The day's budget can't cover another reservation (§9.8): 503 budget_exhausted."""

    def __init__(self, retry_after_s: int) -> None:
        super().__init__(retry_after_s)
        self.retry_after_s = retry_after_s  # until the next UTC midnight


class DailyTokenBudget:
    """The daily spend cap (§9.8, L56): tokens reserved per UTC day, in this process.

    Reserve before spend: a request reserves its worst case before any call, and nothing
    refunds it. clock returns the current time, aware and in UTC.
    """

    def __init__(self, cap: int, clock: Callable[[], datetime]) -> None:
        self._cap = cap
        self._clock = clock
        self._lock = asyncio.Lock()  # §9.8: concurrent reservations can't both pass the check
        self._day: date | None = None
        self._reserved = 0

    async def reserve(self, tokens: int) -> None:
        """Charges tokens to today, or raises BudgetExhaustedError if they don't fit."""
        async with self._lock:
            now = self._clock()
            today = now.date()
            if today != self._day:
                self._day, self._reserved = today, 0
            if self._reserved + tokens > self._cap:
                midnight = datetime.combine(today + timedelta(days=1), datetime.min.time(), UTC)
                raise BudgetExhaustedError(math.ceil((midnight - now).total_seconds()))
            self._reserved += tokens


def _utc_now() -> datetime:
    return datetime.now(UTC)


@functools.cache
def _budget() -> DailyTokenBudget:
    """The process's one counter (§9.8), built on first use, as db.py's engine is (L343).

    Only get_budget calls it, with daily_token_budget set.
    """
    if settings.daily_token_budget is None:
        raise RuntimeError("daily_token_budget is unset")
    return DailyTokenBudget(settings.daily_token_budget, _utc_now)


def get_budget() -> DailyTokenBudget | None:
    """The day's counter when settings.daily_token_budget is set, else None (§9.8).

    Read per request at the edge, as get_judge is (L318); the function object is the override
    key route tests replace.
    """
    return _budget() if settings.daily_token_budget is not None else None


async def admit(
    request: Request,
    req: SummarizeRequest,
    budget: Annotated[DailyTokenBudget | None, Depends(get_budget)],
) -> SummarizeRequest:
    """§9.8's two defenses, in this order, before any call (L350).

    The client's rate limit first, so a request over it reserves nothing; then the day's
    reservation, settings.max_request_tokens. It takes the validated request, so a paste that
    fails validation never reaches it, and returns it: the route holds the request admit let
    in.
    """
    if settings.rate_limit is not None:
        await _count_against_rate_limit(request)
    if budget is not None:
        await budget.reserve(settings.max_request_tokens)
    return req


def _log_completed(
    request: Request,
    note_id: UUID,
    metadata: RunMetadata,
    report: EvalReport,
    started: float,
    summarized: float,
) -> None:
    """The completed request's one line (§9.8, L351): ids and numbers, never content.

    started and summarized are perf_counter readings, taken as the route began and as
    summarize returned; wall_s runs to this call, after the checks.
    """
    usage, judge_usage = metadata.usage, report.judge_usage
    logger.info(
        "request_completed request_id=%s note_id=%s model=%s wall_s=%.3f summarize_wall_s=%.3f "
        "validation_attempts=%d input_tokens=%d output_tokens=%d judge_input_tokens=%d "
        "judge_output_tokens=%d",
        request.state.request_id,
        note_id,
        metadata.model,
        perf_counter() - started,
        summarized - started,
        metadata.validation_attempts,
        usage.input_tokens,
        usage.output_tokens,
        judge_usage.input_tokens,
        judge_usage.output_tokens,
    )


# The codes /summarize answers, by status: §9.4's rows (L73), and the framework's 400 for a
# body that isn't UTF-8 (L80). Declaring the 422 drops FastAPI's default HTTPValidationError,
# a body the API never sends (L358).
_SUMMARIZE_ERRORS: Final[Mapping[int, tuple[ErrorCode, ...]]] = {
    400: ("http_error",),
    422: ("input_invalid",),
    429: ("rate_limited",),
    500: ("internal_error",),
    502: ("output_truncated", "model_output_invalid", "upstream_error"),
    503: ("budget_exhausted", "upstream_busy"),
    504: ("upstream_timeout",),
}


@app.post("/summarize", responses=_documented(_SUMMARIZE_ERRORS))
async def summarize_endpoint(
    request: Request,
    req: Annotated[SummarizeRequest, Depends(admit)],
    background_tasks: BackgroundTasks,
    client: Annotated[LLMClient, Depends(get_client)],
    judge: Annotated[Judge | None, Depends(get_judge)],
    sessions: Annotated[async_sessionmaker[AsyncSession] | None, Depends(get_sessions)],
) -> SummarizeResponse:
    """Composition root (§9.1): wires the pipeline in order; no logic lives here.

    Phase 3's route (L166, L318, L347, L350, L351): §9.1's. The request is admit's, limited
    and reserved before any call. The judge is get_judge's, None unless settings.judge_enabled;
    run_checks selects the judged check only with one. The sessions are get_sessions', None
    unless settings.persist_enabled: persist writes the note after the response, in a session
    of its own (§9.6), and note_id names its row. With persistence off it names none (§9.10,
    L58). Before the response, the request's one request_completed line (L351).
    """
    note_id, started = uuid4(), perf_counter()
    result = await summarize(req.raw_text, client=client)
    summarized = perf_counter()
    config = settings.checks_config()  # L187: built here, at the edge, and passed inward
    note = ground(result.draft, req.raw_text, config=config)  # spans index the exact paste (L87)
    report = await run_checks(note, req.raw_text, mode="production", config=config, judge=judge)
    _log_completed(request, note_id, result.metadata, report, started, summarized)
    background_tasks.add_task(
        persist, sessions, note_id, req.raw_text, note, report, result.metadata
    )
    return SummarizeResponse(note_id=note_id, note=note, report=report, metadata=result.metadata)


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
    code: ErrorCode = "input_invalid"
    logger.warning("input_rejected code=%s request_id=%s", code, rid)
    return _error_response(422, code, rid)


@app.exception_handler(RateLimitExceeded)
async def handle_rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 rate_limited (§9.4, §9.8): THIS client is over its limit, and it reserved nothing.

    Retry-After is the seconds until the client's window resets, read from slowapi's window
    for the limit it hit, request.state.view_rate_limit, as slowapi's own handler reads it.
    Never reads exc.detail or the body (invariant 19). Registered on slowapi's class, which
    subclasses Starlette's HTTPException: without it, that handler would answer http_error.
    """
    rid: str = request.state.request_id
    code: ErrorCode = "rate_limited"
    item, key = request.state.view_rate_limit
    reset = limiter.limiter.get_window_stats(item, *key).reset_time
    retry_after = math.ceil(reset - time.time())
    logger.warning("admission_refused code=%s request_id=%s retry_after=%d", code, rid, retry_after)
    return _error_response(429, code, rid, {"Retry-After": str(retry_after)})


@app.exception_handler(BudgetExhaustedError)
async def handle_budget_exhausted(request: Request, exc: BudgetExhaustedError) -> JSONResponse:
    """503 budget_exhausted (§9.4, §9.8): the demo's daily cap, until the next UTC midnight."""
    rid: str = request.state.request_id
    code: ErrorCode = "budget_exhausted"
    logger.warning(
        "admission_refused code=%s request_id=%s retry_after=%d", code, rid, exc.retry_after_s
    )
    return _error_response(503, code, rid, {"Retry-After": str(exc.retry_after_s)})


# Framework codes (L80): not rows of §9.4's table, and not part of the phase-1 reach list.
_FRAMEWORK_CODES: Final[Mapping[int, ErrorCode]] = {404: "not_found", 405: "method_not_allowed"}


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
    code: ErrorCode = _FRAMEWORK_CODES.get(exc.status_code, "http_error")
    logger.warning("framework_error code=%s status=%d request_id=%s", code, exc.status_code, rid)
    return _error_response(exc.status_code, code, rid, exc.headers)


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
    # L358: exc.code is the orchestrator's str, so ErrorBody checks it here: a code no body may
    # carry raises, and the catch-all answers 500
    code = ErrorBody.model_validate({"error": exc.code, "request_id": rid}).error
    return _error_response(502, code, rid)


@app.exception_handler(RateLimitError)
async def handle_rate_limit_error(request: Request, exc: RateLimitError) -> JSONResponse:
    """503 upstream_busy (§9.4): upstream throttled US; 429 is reserved for our own limit.

    Retry-After is protocol, not content (L98): forwarded verbatim when upstream sent one,
    never parsed, never tested for truthiness. Forwarding it is the one behavior this handler
    does not share with the status handler's 429 branch (L99). Of the exception it reads only
    the status code, for the log line, and the Retry-After header (invariant 19).
    """
    rid: str = request.state.request_id
    code: ErrorCode = "upstream_busy"
    logger.warning(
        "upstream_failure code=%s request_id=%s upstream_status=%d", code, rid, exc.status_code
    )
    retry_after = exc.response.headers.get("retry-after")
    headers = None if retry_after is None else {"Retry-After": retry_after}
    return _error_response(503, code, rid, headers)


# L71, L99: overloaded and throttled mean the same thing to our client: upstream is busy.
_BUSY_STATUSES: Final[frozenset[int]] = frozenset({429, 529})
# L255: a 4xx the SDK retries as transient, from an intermediary once its retries run out
_INTERMEDIARY_STATUSES: Final[frozenset[int]] = frozenset({408, 409})


@app.exception_handler(APIStatusError)
async def handle_api_status_error(request: Request, exc: APIStatusError) -> JSONResponse:
    """Attributed by the status, never the subclass, and total over every int (§9.4; L71, L99).

    RateLimitError's handler claims the SDK's 429s first by MRO, so a 429 here is the base
    class; the busy check runs first because 429 is also a 4xx. ERROR only on the 500
    branch: a 4xx other than 408 and 409 is OUR request or config (L255). It forwards no
    headers (L99). Of the exception it reads only the status code: never str(exc),
    exc.message, exc.body, exc.request, the response body, or the cause (invariant 19).
    """
    rid: str = request.state.request_id
    upstream = exc.status_code
    code: ErrorCode
    if upstream in _BUSY_STATUSES:
        status, code, level = 503, "upstream_busy", logging.WARNING
    elif upstream in _INTERMEDIARY_STATUSES:  # L255
        status, code, level = 502, "upstream_error", logging.WARNING
    elif 400 <= upstream < 500:
        status, code, level = 500, "internal_error", logging.ERROR
    else:  # 5xx, and any status outside 4xx/5xx (L99)
        status, code, level = 502, "upstream_error", logging.WARNING
    logger.log(
        level, "upstream_failure code=%s request_id=%s upstream_status=%d", code, rid, upstream
    )
    return _error_response(status, code, rid)


@app.exception_handler(APITimeoutError)
async def handle_api_timeout_error(request: Request, exc: APITimeoutError) -> JSONResponse:
    """504 upstream_timeout (§9.4, L54): OUR client gave up waiting (llm_timeout_s).

    An upstream 504 is a status, and takes the status handler as upstream's error (L99); this
    is the client-side timeout only. Of the exception it reads nothing but its type name:
    never str(exc), exc.message, exc.request, or the cause (invariant 19).
    """
    rid: str = request.state.request_id
    code: ErrorCode = "upstream_timeout"
    logger.warning(
        "upstream_failure code=%s request_id=%s exc_type=%s", code, rid, type(exc).__name__
    )
    return _error_response(504, code, rid)


@app.exception_handler(APIError)
async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
    """502 upstream_error (§9.4, L71): any other API failure, non-timeout connection ones included.

    Logs exc_type because with no status to branch on, the type is what tells these failures
    apart. Of the exception it reads nothing but its type name: never str(exc), exc.message,
    exc.body, exc.request, or the cause (invariant 19).
    """
    rid: str = request.state.request_id
    code: ErrorCode = "upstream_error"
    logger.warning(
        "upstream_failure code=%s request_id=%s exc_type=%s", code, rid, type(exc).__name__
    )
    return _error_response(502, code, rid)
