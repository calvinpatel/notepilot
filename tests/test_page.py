"""Pins GET /, the phase-1 page (spec §9.10; L68, L92, L100).

The route serves backend/static/index.html by a path derived from backend/api.py, never the
cwd. The suite runs from the repo root, where a cwd-relative path would also resolve, so the
serving test moves the cwd first. The page's bytes are read from this file's own location:
a test that imported the route's path would agree with any path the route used.

The page renders the model's claims, and a source_quote copies the paste, so markup in a
paste would execute through a string-to-HTML sink. The scan reads the served text and bans
the sinks _SINKS names; a string scan can't name them all. The page's rendering runs in a
browser, not here.
"""

from pathlib import Path
from typing import Final

import pytest
from fastapi.testclient import TestClient

from backend.api import app

_PAGE: Final = Path(__file__).resolve().parent.parent / "backend" / "static" / "index.html"
_SINKS: Final = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write")


def test_root_serves_the_page_from_any_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.content == _PAGE.read_bytes()


@pytest.mark.parametrize("sink", _SINKS)
def test_served_page_has_no_html_sink(sink: str) -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200  # a 404 body would pass the scan
    assert sink not in response.text
