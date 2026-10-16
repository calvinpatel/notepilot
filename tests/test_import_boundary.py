"""The domain's import boundary (§0, §11; invariant 1; L187, L188, L234).

grounding.py, evals/, schemas.py, and tracebacks.py read no settings, know no vendor, and
import no edge module. An AST walk finds every import in them, at module level or inside a
function, and resolves each to the modules it names: `from backend import config` names
backend.config, and so does `from .. import config` inside evals/. None may be anthropic or
fastapi, or inside them, and none may be a backend module outside the domain: schemas,
tracebacks, grounding, evals, and clinical. That one rule refuses backend.config and the edge
modules alike, so an edge module needs no entry here. clinical/ has its own, stricter test
(invariant 13). A dynamic import (importlib, __import__) is outside what an AST walk can see.
"""

import ast
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
_DOMAIN = sorted(
    [
        _BACKEND / "grounding.py",
        _BACKEND / "schemas.py",
        _BACKEND / "tracebacks.py",
        *(_BACKEND / "evals").rglob("*.py"),
    ]
)
_VENDORS = ("anthropic", "fastapi")
# §0's domain modules: the walk refuses every other backend module
_DOMAIN_MODULES = (
    "backend.schemas",
    "backend.tracebacks",
    "backend.grounding",
    "backend.evals",
    "backend.clinical",
)


def _module_names(source: str, package: str) -> set[str]:
    """Every module an import in source names, resolved against package (dotted)."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                module = f"{base}.{node.module}" if node.module else base
            else:
                module = node.module or ""
            names.add(module)
            # `from backend import config` names the submodule, not just the package
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def _under(name: str, roots: tuple[str, ...]) -> bool:
    """name is one of roots, or a module inside one."""
    return any(name == root or name.startswith(root + ".") for root in roots)


def _forbidden(names: set[str]) -> set[str]:
    return {
        n
        for n in names
        if _under(n, _VENDORS) or (n.startswith("backend.") and not _under(n, _DOMAIN_MODULES))
    }


def _package(path: Path) -> str:
    return ".".join(("backend", *path.parent.relative_to(_BACKEND).parts))


@pytest.mark.parametrize("path", _DOMAIN, ids=lambda p: p.relative_to(_BACKEND).as_posix())
def test_the_domain_imports_only_the_domain_and_no_vendor(path: Path) -> None:
    names = _module_names(path.read_text(encoding="utf-8"), _package(path))
    assert _forbidden(names) == set()


def test_the_domain_list_covers_evals() -> None:
    # rglob finding nothing would leave evals/ untested and the parametrized test green
    assert {p.name for p in _DOMAIN} >= {"checks.py", "registry.py", "runner.py"}


@pytest.mark.parametrize(
    ("source", "package"),
    [
        ("from backend.config import settings", "backend"),
        ("from backend import config", "backend"),
        ("import backend.config", "backend"),
        ("def f():\n    from backend.config import settings", "backend"),
        ("from .. import config", "backend.evals"),
        ("from ..config import settings", "backend.evals"),
        ("from . import config", "backend"),
        ("import anthropic", "backend"),
        ("from anthropic.types import Message", "backend"),
        ("import fastapi.responses", "backend"),
        ("from backend.orchestrator import LLMClient", "backend.evals"),
        ("from .. import api", "backend.evals"),
        ("from backend.edge_module import x", "backend"),
        ("from backend.schemas_v2 import x", "backend"),
    ],
)
def test_the_walk_sees_each_form_of_a_forbidden_import(source: str, package: str) -> None:
    # The boundary test is only as good as the walk: every spelling must resolve.
    assert _forbidden(_module_names(source, package))


@pytest.mark.parametrize(
    ("source", "package"),
    [
        ("from backend.schemas import SOAPNote", "backend"),
        ("from . import schemas", "backend.evals"),
        ("from backend import schemas", "backend.evals"),
        ("from backend.clinical.extract import Dose", "backend.evals"),
        ("from backend.grounding import ground", "backend.evals"),
        ("from .registry import Finding", "backend.evals"),
        ("import configparser", "backend"),
        ("import fastapi_utils", "backend"),
    ],
)
def test_the_walk_passes_an_allowed_import(source: str, package: str) -> None:
    assert _forbidden(_module_names(source, package)) == set()
