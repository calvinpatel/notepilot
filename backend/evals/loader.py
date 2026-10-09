"""The case loader: evals/cases/<id>.yaml files to EvalCases (spec §8.5; L103, L118, L119).

load_cases reads a directory of case files and checks each answer key against the registry:
every expected_flags entry must name a registered check. It collects every file's problems
and raises them together, so one run shows an author the whole directory's.

ruamel.yaml's safe loader reads YAML 1.2, so `no` stays a string, and rejects a duplicate key
(L118). A problem names the file, then the line or the field, then what's wrong. It never
carries the file's text: not the parser's snippet, not a duplicate key's values (ruamel's
message quotes both), and not pydantic's input, which can be the whole raw_text.
"""

from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import MarkedYAMLError, YAMLError

from backend.evals.registry import REGISTRY
from backend.schemas import EvalCase

# where the corpus lives (§13): one <id>.yaml per case
CASES_DIR = Path(__file__).resolve().parent / "cases"


class CaseLoadError(ValueError):
    """Every problem load_cases found, one per line, in file-name order."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = tuple(problems)
        noun = "problem" if len(problems) == 1 else "problems"
        super().__init__("\n".join([f"{len(problems)} {noun} loading cases:", *problems]))


def load_cases(directory: Path) -> list[EvalCase]:
    """Every case in directory, sorted by id; CaseLoadError if any file has a problem.

    Each file must be <id>.yaml (L119): a .yml file, any other file, or a subdirectory is a
    problem, not a case silently skipped. Dotfiles are skipped.
    """
    yaml = YAML(typ="safe", pure=True)
    cases: list[EvalCase] = []
    problems: list[str] = []
    for path in sorted(directory.iterdir()):  # sorted by file name, which is the id
        if path.name.startswith("."):
            continue
        loaded = _load_one(path, yaml)
        if isinstance(loaded, EvalCase):
            cases.append(loaded)
        else:
            problems.extend(loaded)
    if problems:
        raise CaseLoadError(problems)
    return cases


def _load_one(path: Path, yaml: YAML) -> EvalCase | list[str]:
    """One file's case, or its problems: errors as values, raised once by load_cases."""
    name = path.name
    if path.is_dir() or path.suffix != ".yaml":
        return [f"{name}: not a case file; each case is <id>.yaml"]
    try:
        data = yaml.load(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return [f"{name}: not UTF-8 text"]
    except DuplicateKeyError as exc:  # its problem quotes both values; the line is enough
        return [f"{name}: {_where(exc)}duplicate key"]
    except MarkedYAMLError as exc:
        return [f"{name}: {_where(exc)}{exc.problem or type(exc).__name__}"]
    except YAMLError as exc:
        return [f"{name}: {type(exc).__name__}"]
    try:
        case = EvalCase.model_validate(data)
    except ValidationError as exc:
        return [
            f"{name}: {'.'.join(map(str, e['loc'])) or '(case)'}: {e['msg']}"
            for e in exc.errors(include_input=False)
        ]
    problems: list[str] = []
    if case.id != path.stem:
        problems.append(f"{name}: id {case.id!r} doesn't match the file name")
    unknown = [flag for flag in case.expected_flags if flag not in REGISTRY]
    if unknown:
        problems.append(f"{name}: expected_flags names unregistered checks: {', '.join(unknown)}")
    return problems or case


def _where(exc: MarkedYAMLError) -> str:
    """'line N: ' where ruamel marked the problem; ruamel types problem_mark as Any."""
    return f"line {exc.problem_mark.line + 1}: " if exc.problem_mark is not None else ""
