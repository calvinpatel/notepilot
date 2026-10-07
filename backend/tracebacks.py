"""Tracebacks as log structure: frames, never messages (spec §9.4; L69, L112).

Frames carry no PHI; an exception's message and its chained cause can (a ValidationError
carries input_value). Imports nothing from backend/, so edge and domain modules can both log
an exception this way.
"""

import traceback
from pathlib import Path
from typing import Final

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


def format_frames(exc: Exception) -> str:
    """The traceback as file:line:function entries, outermost first, joined by '>' (L69).

    Reads only exc's own traceback: never its message, and never its chained cause's frames.
    """
    return ">".join(
        f"{_display_path(frame.filename)}:{frame.lineno}:{frame.name}"
        for frame in traceback.extract_tb(exc.__traceback__)
    )
