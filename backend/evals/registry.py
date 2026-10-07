"""The check registry and stamp (spec §8.7).

@register_check records a check under its name. Registering a name twice raises, so a module
imported twice fails loudly instead of doubling the roster. stamp turns a Finding into a
failed EvalResult under the check's name, at the check's severity or a lower one the finding
names (L38).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol, overload

from backend.evals.judge import Judge
from backend.schemas import EvalCase, EvalResult, Severity, SOAPNote

# who creates the danger: the model, or the source text (§8.5, L42)
type Origin = Literal["model", "source"]


@dataclass(frozen=True)
class Finding:
    """What a check returns: the facts of one violation (§8.7).

    Layer-internal, so it lives here, not in schemas.py (§13, L104).
    """

    detail: str
    claim_ids: tuple[int, ...] = ()  # () = note-level (§9.7)
    severity: Severity | None = None  # None = the check's; a downgrade only (L38)


# What a check returns: its findings, or an awaitable of them (§8.7)
type CheckOutput = list[Finding] | Awaitable[list[Finding]]

# A check's signature (§8.4). register_check's decorator is bound by it, so mypy checks a
# decorated check's parameters and return; Check.fn keeps §8.7's looser type.
type CheckFn = Callable[[SOAPNote, str, EvalCase | None], CheckOutput]


class JudgedCheckFn(Protocol):
    """A judged check's signature: CheckFn's, plus a required keyword judge (§8.7).

    A Protocol, because Callable can't spell a keyword-only parameter.
    """

    def __call__(
        self, note: SOAPNote, raw_text: str, case: EvalCase | None, /, *, judge: Judge
    ) -> CheckOutput: ...


@dataclass(frozen=True)
class Check:
    """What @register_check records under a check's name (§8.7)."""

    name: str
    severity: Severity
    fn: Callable[..., CheckOutput]
    requires_reference: bool
    needs_judge: bool
    origin: Origin


REGISTRY: dict[str, Check] = {}


@overload
def register_check[F: CheckFn](
    *,
    name: str,
    severity: Severity,
    requires_reference: bool = ...,
    needs_judge: Literal[False] = ...,
    origin: Origin = ...,
) -> Callable[[F], F]: ...
@overload
def register_check[F: JudgedCheckFn](
    *,
    name: str,
    severity: Severity,
    requires_reference: bool = ...,
    needs_judge: Literal[True],
    origin: Origin = ...,
) -> Callable[[F], F]: ...
def register_check[F: Callable[..., CheckOutput]](
    *,
    name: str,
    severity: Severity,
    requires_reference: bool = False,
    needs_judge: bool = False,
    origin: Origin = "model",
) -> Callable[[F], F]:
    """Record the decorated check under name, once.

    The overloads tie needs_judge to the signature: True takes a JudgedCheckFn, the default
    a CheckFn, so mypy rejects a flag the parameters don't match.
    """

    def deco(fn: F) -> F:
        if name in REGISTRY:
            raise RuntimeError(f"duplicate check name: {name}")
        REGISTRY[name] = Check(
            name=name,
            severity=severity,
            fn=fn,
            requires_reference=requires_reference,
            needs_judge=needs_judge,
            origin=origin,
        )
        return fn

    return deco


_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}


def stamp(check: Check, finding: Finding) -> EvalResult:
    """One finding -> one failed EvalResult under the check's name (§8.7).

    Raises ValueError for a finding above the check's severity (L38).
    """
    severity = check.severity if finding.severity is None else finding.severity
    if _RANK[severity] > _RANK[check.severity]:
        raise ValueError(f"{check.name}: finding severity exceeds the check's")
    return EvalResult(
        check=check.name,
        severity=severity,
        passed=False,
        detail=finding.detail,
        claim_ids=finding.claim_ids,
    )
