"""Pins the frame formatter both layers log with (spec §9.4; L69, L112)."""

from backend.tracebacks import _REPO_ROOT, _display_path, format_frames

MESSAGE_SENTINEL = "sentinel-msg-7d13"
CAUSE_SENTINEL = "sentinel-cause-2b88"


class _Boom(Exception):
    """A local type, so _caught's except clause can't catch the ValueError cause."""


def _raise_cause() -> None:
    raise ValueError(CAUSE_SENTINEL)


def _inner() -> None:
    try:
        _raise_cause()
    except ValueError as cause:
        raise _Boom(MESSAGE_SENTINEL) from cause


def _outer() -> None:
    _inner()


def _caught() -> _Boom:
    """A fresh _Boom per call: raising writes __traceback__, so no instance is shared."""
    try:
        _outer()
    except _Boom as exc:
        return exc
    raise AssertionError("_outer did not raise")


def test_format_frames_renders_each_frame_outermost_first() -> None:
    entries = [entry.split(":") for entry in format_frames(_caught()).split(">")]
    assert [(file, function) for file, _, function in entries] == [
        ("tests/test_tracebacks.py", "_caught"),
        ("tests/test_tracebacks.py", "_outer"),
        ("tests/test_tracebacks.py", "_inner"),
    ]
    assert all(line.isdigit() for _, line, _ in entries)


def test_format_frames_never_carries_the_message_or_the_cause() -> None:
    rendered = format_frames(_caught())
    assert MESSAGE_SENTINEL not in rendered
    assert CAUSE_SENTINEL not in rendered
    assert "_raise_cause" not in rendered  # the chained cause's frames stay out too


def test_display_path_cuts_an_installed_file_after_site_packages() -> None:
    # site-packages wins over the repo: .venv sits inside the repo root
    installed = _REPO_ROOT / ".venv" / "lib" / "python3.14" / "site-packages" / "pkg" / "mod.py"
    assert _display_path(str(installed)) == "pkg/mod.py"


def test_display_path_renders_a_repo_file_relative_to_the_root() -> None:
    assert (_REPO_ROOT / "pyproject.toml").is_file()
    assert _display_path(str(_REPO_ROOT / "backend" / "api.py")) == "backend/api.py"


def test_display_path_renders_any_other_file_as_its_basename() -> None:
    assert _display_path(str(_REPO_ROOT.parent / "elsewhere" / "mod.py")) == "mod.py"
