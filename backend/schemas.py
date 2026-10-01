"""The spine: the pipeline's data contract (spec §4).

Imports only the standard library and pydantic: nothing from this app, no
vendor SDK, no web framework. The pipeline layers import it. clinical/ does
not; it works on plain strings.

ClaimDraft and SOAPNoteDraft are the model's contract. SOAPNoteDraft's JSON
schema IS the tool's input schema, so any change to either draft type's fields
or descriptions is prompt text the model reads. It changes PROMPT_VERSION and
breaks the tool-schema snapshot on purpose. Descriptions state shape
(verbatim, contiguous, one fact), never clinical rules; those live in the
system prompt.

New pipeline data shapes go here. The only shapes defined elsewhere are HTTP
edge shapes in api.py and check-internal shapes in evals/registry.py
(spec §13).
"""
