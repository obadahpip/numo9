"""C-02-T14 — import-linter contract: only ``numo9.ledger.services`` writes ``JournalLine``.

Acceptance: the lint fails on a direct-write fixture. ``find_writes`` reports every kind of write
in ``tests/fixtures/ledger_writes/direct_write.py.txt`` (constructor, create, bulk_create, a
queryset chain ending in update/delete, raw SQL) and none of its reads; the contract is broken when
a module of the package contains such a write, kept for the real code base (``lint-imports``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tools import import_contracts
from tools.import_contracts import LedgerWritesContract, find_writes

BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).with_name("fixtures") / "ledger_writes" / "direct_write.py.txt"


def test_every_direct_write_is_found_reads_are_not() -> None:
    writes = find_writes(FIXTURE.read_text(encoding="utf-8"))
    assert [w.line for w in writes] == [9, 10, 11, 12, 13, 15, 16]
    assert [w.what for w in writes][:5] == [
        "JournalLine(...)",
        "JournalLine.objects.create()",
        "JournalLine.objects.bulk_create()",
        "JournalLine.objects.filter.update()",
        "JournalLine._base_manager.filter.delete()",
    ]


class FakeGraph:
    def __init__(self, modules: dict[str, str], importers: set[str]) -> None:
        self.sources, self.importers = modules, importers

    @property
    def modules(self) -> set[str]:
        return set(self.sources)

    def find_modules_that_directly_import(self, module: str) -> set[str]:
        return self.importers


def _contract() -> LedgerWritesContract:
    return LedgerWritesContract(
        name="ledger writes",
        session_options={},
        contract_options={
            "models_module": "numo9.ledger.models",
            "allowed_modules": ["numo9.ledger.services"],
        },
    )


def test_contract_breaks_on_the_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    sources = {
        "numo9.sales.posting": FIXTURE.read_text(encoding="utf-8"),
        "numo9.ledger.services": "JournalLine.objects.bulk_create([])",
        "numo9.ledger.migrations.0004_x": "x = 'UPDATE ledger_journalline SET a = 1'",
        "numo9.reports.raw": "q = 'INSERT INTO ledger_journalline VALUES (1)'",
        "numo9.reports.reader": "JournalLine.objects.create()",  # doesn't import the model
    }
    monkeypatch.setattr(import_contracts, "_source", lambda module: sources[module])
    graph: Any = FakeGraph(sources, {"numo9.sales.posting", "numo9.ledger.services"})
    check = _contract().check(graph, verbose=False)
    assert not check.kept
    violations = (check.metadata or {})["violations"]
    assert sorted(violations) == ["numo9.reports.raw", "numo9.sales.posting"]
    assert len(violations["numo9.sales.posting"]) == 7


def test_contract_is_kept_for_the_code_base() -> None:
    lint = Path(sys.executable).with_name("lint-imports")
    result = subprocess.run(
        [str(lint), "--no-cache"], cwd=BACKEND, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 kept, 0 broken" in result.stdout
