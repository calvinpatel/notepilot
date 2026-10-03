"""The HTTP edge: the app, its routes, and the input boundary (spec §9.1, §9.4, §9.8).

EDGE adapter (spec §0): FastAPI's types appear here and nowhere inward. The route is a
composition root with no logic (§9.1): it awaits summarize() and returns the wire shape.
SummarizeRequest and SummarizeResponse are the HTTP edge shapes §13 sanctions outside
schemas.py; SummarizationResult never goes on the wire (L76).

SummarizeRequest counts CONTENT (stripped length, L87) and never mutates raw_text: §6.2's
source spans are offsets into the exact paste. An oversized paste fails honestly at
max_length (§9.1).

A RequestValidationError becomes 422 {"error": "input_invalid", "request_id": ...} and is
logged by code only (L70). FastAPI's default handler echoes the paste as `input` whenever
the body parses; this one never reads exc.errors(), str(exc), or the body (L53,
invariant 19).

request_id is minted per request by RequestIdMiddleware (L73), a pure ASGI middleware, on
request.state. The root logger is configured once here (§9.8): plain text with timestamp,
level, and logger name; fields render in the message as key=value pairs via %-style args,
never extra= (L79).
"""

import logging
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.config import settings
from backend.orchestrator import LLMClient, get_client, summarize
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


app = FastAPI(title="NotePilot")
app.add_middleware(RequestIdMiddleware)


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
