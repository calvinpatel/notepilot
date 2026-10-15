"""Pins run_fresh, the fresh-interpreter helper (tests/fresh.py)."""

import pytest

from tests.fresh import run_fresh


def test_run_fresh_finds_the_repo_when_pythonsafepath_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # with PYTHONSAFEPATH set, `-c` leaves the cwd off sys.path: only run_fresh's PYTHONPATH
    # entry puts the repo root there
    monkeypatch.setenv("PYTHONSAFEPATH", "1")
    monkeypatch.delenv("PYTHONPATH", raising=False)
    completed = run_fresh("import backend.evals.loader")
    assert completed.returncode == 0, completed.stderr


def test_run_fresh_returns_a_failing_scripts_exit_code() -> None:
    completed = run_fresh("import sys; print('out'); sys.exit(3)")
    assert (completed.returncode, completed.stdout.strip()) == (3, "out")


def test_importing_tests_fresh_loads_only_the_standard_library() -> None:
    # the modules the import adds, minus the standard library's, are tests/fresh.py and its
    # package: a test file that imports run_fresh pulls in nothing else
    script = (
        "import sys; before = set(sys.modules); import tests.fresh; "
        "print(*sorted(m for m in set(sys.modules) - before "
        "if m.partition('.')[0] not in sys.stdlib_module_names))"
    )
    completed = run_fresh(script)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.split() == ["tests", "tests.fresh"]
