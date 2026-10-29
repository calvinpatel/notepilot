"""Pins two things the frontend's source never names (spec §9.8, §9.10; L362, #3 entry 2).

No HTML sink: every source_quote copies the paste verbatim, so markup in the paste would
run if the page wrote it as HTML. React writes text children as text; these names are how
code gets around that. No browser storage: the paste box is a PHI intake (§9.8), so the
page keeps the paste and the response in memory. A scan of names can't prove a page safe;
it fails the change that types one. Test files and src/test/ are not scanned: a test may
read a node's HTML to check what rendered.
"""

from pathlib import Path
from typing import Final

import pytest

_SRC: Final = Path(__file__).resolve().parent.parent / "frontend" / "src"
_SINKS: Final = (
    "dangerouslySetInnerHTML",
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
)
_STORAGE: Final = ("localStorage", "sessionStorage", "indexedDB", "document.cookie")


def _scanned() -> list[Path]:
    """The page's own source: .ts and .tsx under src/, less tests and src/test/."""
    return sorted(
        path
        for path in _SRC.rglob("*")
        if path.suffix in {".ts", ".tsx"}
        and ".test." not in path.name
        and path.relative_to(_SRC).parts[0] != "test"
    )


def test_the_scan_reads_the_page() -> None:
    # a scan that read nothing would pass every name below
    scanned = {path.relative_to(_SRC).as_posix() for path in _scanned()}
    assert {"App.tsx", "client.ts", "components/SourcePane.tsx"} <= scanned
    assert not any(".test." in name or name.startswith("test/") for name in scanned)


@pytest.mark.parametrize("name", _SINKS + _STORAGE)
def test_no_source_file_names_it(name: str) -> None:
    named = [p.relative_to(_SRC).as_posix() for p in _scanned() if name in p.read_text("utf-8")]
    assert named == []
