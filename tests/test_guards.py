"""The lexicon-table guard sees a write to any table (§11; L257)."""

import pytest

import backend.clinical.lexicons as lexicons
from tests.guards import lexicon_digest

TABLES = sorted(
    name
    for name, value in vars(lexicons).items()
    if name.isupper() and isinstance(value, (set, frozenset, dict))
)


def test_the_digest_covers_each_table_and_nothing_else() -> None:
    assert sorted(lexicon_digest()) == TABLES
    assert "NEGATION_WINDOW" not in lexicon_digest()  # an int, not a table


def test_the_digest_is_stable_across_calls() -> None:
    assert lexicon_digest() == lexicon_digest()


@pytest.mark.parametrize("name", TABLES)
def test_a_changed_table_changes_the_digest(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # replaced, never written: the guard itself must not see this test (monkeypatch restores)
    table = getattr(lexicons, name)
    if isinstance(table, dict):
        key = next(iter(table))
        changed: object = {**table, key: (table[key], "changed")}
    else:
        changed = {*table, "an entry no table holds"}
    before = lexicon_digest()
    monkeypatch.setattr(lexicons, name, changed)
    after = lexicon_digest()
    assert {n for n in before if before[n] != after[n]} == {name}
