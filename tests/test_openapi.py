"""Pins GET /openapi.json against a committed snapshot, compared as text (spec §11; L356).

A change to the schema the API serves is a reviewed diff here. The comparison is by text, key
order included: a parse-and-compare passes a file whose keys were reordered. The file is the
body as json.dumps writes it with indent=2 and ensure_ascii=False, plus one newline; the
endpoint serves non-ASCII as itself, and so does the file. The schema embeds settings
(SummarizeRequest's max_length is settings.max_input_chars), so the file holds the values
tests/conftest.py gives the suite.

Every property the summarize response reaches is required in its schema (L357): the wire
carries a field with a default as it carries any other, so a type generated from the schema
can't call one optional. test_api.py pins the wire half.

Regenerate it, after a reviewed change to what /openapi.json serves, from the repo root in
CLAUDE.md's scratch environment: uv run python -c
'import tests.test_openapi as t; t.write_openapi_snapshot()'
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from fastapi.testclient import TestClient

from backend.api import app

_SNAPSHOT: Final = Path(__file__).parent / "snapshots" / "openapi.json"
_REF: Final = "#/components/schemas/"


def _served() -> str:
    """GET /openapi.json's body in the snapshot's written form."""
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    return json.dumps(response.json(), indent=2, ensure_ascii=False) + "\n"


def write_openapi_snapshot() -> None:
    """Rewrite the snapshot from what /openapi.json serves now (see the module docstring)."""
    _SNAPSHOT.write_text(_served(), encoding="utf-8")


def test_snapshot_is_what_openapi_json_serves() -> None:
    # L356: a schema change is a reviewed diff here; text, so key order counts too
    assert _SNAPSHOT.is_file(), f"missing snapshot {_SNAPSHOT}; see module docstring"
    assert _SNAPSHOT.read_text(encoding="utf-8") == _served()


def _refs(node: object) -> Iterator[str]:
    """The component names node's $refs point at, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value.removeprefix(_REF)
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


def test_every_property_the_summarize_response_reaches_is_required() -> None:
    # L357: source_span, errored, judge_usage, and the rest with defaults are required
    schema = json.loads(_served())
    components = schema["components"]["schemas"]
    pending = list(_refs(schema["paths"]["/summarize"]["post"]["responses"]["200"]))
    reached: set[str] = set()
    while pending:
        name = pending.pop()
        if name not in reached:
            reached.add(name)
            pending.extend(_refs(components[name]))
    # the four models with defaults: a walk that reached none of them would pass vacuously
    assert {"ClinicalClaim", "EvalResult", "EvalReport", "TokenUsage"} <= reached
    optional = {
        (name, prop)
        for name in reached
        for prop in components[name].get("properties", {})
        if prop not in components[name].get("required", [])
    }
    assert optional == set()
