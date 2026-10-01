"""Env setup that must run before any test imports backend.

Settings is built at import time (spec §10).
"""

import os

# config.py skips .env when this is set, so local and CI test runs see identical settings
os.environ["NOTEPILOT_IGNORE_DOTENV"] = "1"
# assignment, not setdefault: a key exported in your shell must never reach tests
os.environ["ANTHROPIC_API_KEY"] = "test-dummy-key"
