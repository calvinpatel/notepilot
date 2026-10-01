"""Raw encounter text -> SummarizationResult, via one forced Anthropic tool call.

EDGE adapter (spec §0). Anthropic's message format appears here and in
judge_client.py, nowhere else; everything handed inward is a spine type. No
FastAPI import: api.py applies Depends(get_client). LLMClient is the typed seam
that both AsyncAnthropic and the test fake satisfy; get_client builds the real
client once per process.

summarize() returns a schema-valid draft with its RunMetadata, or raises an
OrchestratorError subclass carrying the TokenUsage spent so far, failed
attempts included. It never returns a partial draft.

It retries only when the next request differs from the last (spec §5.4). A
validation error goes back to the model as an is_error tool_result. Truncation
or a missing tool block would reproduce itself, so both fail fast. Transport
retries (429/5xx) belong to the SDK, not this loop.

PROMPT_VERSION is derived from everything the model is conditioned on: the
system prompt, tool schema, correction template, and call config. Editing any
of them changes it; it is never bumped by hand.

Exception messages can carry model-emitted clinical text, so callers log these
errors by .code only (spec §9.4, §9.8).
"""
