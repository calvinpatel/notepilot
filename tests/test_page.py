"""Pins GET / and GET /assets/{name}: the frontend's build, served (spec §9.10; L364).

The routes read settings.frontend_dist when a request comes, so each test writes a small build
into a temp folder and points the setting at it: the tests run the same with or without a
real build in the checkout. config.py derives the default from its own location, and the test
that pins it derives the repo root from this file's, so the two can't agree by sharing a
path.
"""

from pathlib import Path
from typing import Final

import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend.config import Settings, settings

_PAGE: Final = "<!doctype html><title>NotePilot</title>"
_ASSET: Final = "index-0a1b2c3d.js"
_SCRIPT: Final = "console.log(1);"


@pytest.fixture
def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(_PAGE, encoding="utf-8")
    (dist / "assets" / _ASSET).write_text(_SCRIPT, encoding="utf-8")
    (dist / "assets" / "a b.js").write_text(_SCRIPT, encoding="utf-8")  # outside the name rule
    (dist / "assets" / ".hidden.js").write_text(_SCRIPT, encoding="utf-8")  # opens with a dot
    (dist / "secret.txt").write_text("not an asset", encoding="utf-8")
    monkeypatch.setattr("backend.api.settings", settings.model_copy(update={"frontend_dist": dist}))
    return dist


def _not_found(path: str) -> None:
    response = TestClient(app).get(path)
    assert response.status_code == 404, path
    body = response.json()
    assert body == {"error": "not_found", "request_id": body.get("request_id")}, path


def test_root_serves_the_builds_page_revalidated_on_every_load(
    built: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # the page comes from the setting, wherever the cwd is
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == _PAGE
    assert response.headers["cache-control"] == "no-cache"


def test_an_asset_is_served_as_javascript_and_cached_for_good(built: Path) -> None:
    response = TestClient(app).get(f"/assets/{_ASSET}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.text == _SCRIPT
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.parametrize(
    "path",
    [
        "/assets/missing.js",
        "/assets/%2E%2E",
        "/assets/..%2Fsecret.txt",
        "/assets/a%20b.js",
        "/assets/.hidden.js",
        "/assets/",
    ],
    ids=[
        "missing",
        "parent",
        "encoded-slash",
        "outside-the-name-rule",
        "opens-with-a-dot",
        "no-name",
    ],
)
def test_any_other_asset_path_is_a_404_in_the_one_shape(built: Path, path: str) -> None:
    _not_found(path)


def test_with_no_build_both_routes_are_a_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "no-build"
    monkeypatch.setattr(
        "backend.api.settings", settings.model_copy(update={"frontend_dist": missing})
    )
    _not_found("/")
    _not_found(f"/assets/{_ASSET}")


def test_the_page_routes_are_not_in_the_schema() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/" not in paths
    assert "/assets/{name}" not in paths


def test_the_default_build_is_the_repos_frontend_dist() -> None:
    root = Path(__file__).resolve().parent.parent
    assert Settings.model_fields["frontend_dist"].default == root / "frontend" / "dist"
