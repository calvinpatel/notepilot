"""run_fresh: a script run in a fresh interpreter, for what only a fresh one shows.

In-process, every module a test imports has already run its import side effects (the
roster's registration, the root logger's configuration), so whether one import does that
by itself is visible only from an interpreter that has imported nothing else. Standard
library only, so a test file that needs this pulls nothing else in.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

_REPO_ROOT: Final = Path(__file__).resolve().parents[1]


def run_fresh(script: str) -> subprocess.CompletedProcess[str]:
    """script, run by `python -c` in a fresh interpreter at the repo root.

    The child inherits the environment, plus the repo root on PYTHONPATH: `-c` puts the cwd
    on sys.path only when PYTHONSAFEPATH is unset. A failing script comes back as its return
    code and stderr, not as an exception.
    """
    existing = os.environ.get("PYTHONPATH")
    env = {
        **os.environ,
        "PYTHONPATH": str(_REPO_ROOT) + (os.pathsep + existing if existing else ""),
    }
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
