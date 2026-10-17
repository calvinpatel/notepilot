"""What the suite checks about itself: module state no test may change (§11; L257)."""

import hashlib
from collections.abc import Mapping

import backend.clinical.lexicons as lexicons


def _canonical(value: object) -> object:
    """value as plain, ordered data: a set's or a dict's iteration order is not part of it."""
    if isinstance(value, Mapping):
        return sorted((repr(k), _canonical(v)) for k, v in value.items())
    if isinstance(value, (set, frozenset)):
        return sorted(repr(_canonical(v)) for v in value)
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return repr(value)


def lexicon_digest() -> dict[str, str]:
    """Each table in lexicons.py, a module-level set or dict, hashed under its name."""
    return {
        name: hashlib.sha256(repr(_canonical(value)).encode()).hexdigest()
        for name, value in vars(lexicons).items()
        if name.isupper() and isinstance(value, (set, frozenset, dict))
    }
