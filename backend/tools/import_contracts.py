"""Custom import-linter contracts (C-02-T14).

``ledger_writes`` — **only ``numo9.ledger.services`` writes ``JournalLine``** (ADR-0003: every
posting goes through the engine; posted lines are append-only). import-linter's built-in
contracts work on whole modules, and other apps must import ``numo9.ledger.models`` (accounts,
entries to read), so this contract uses the import graph to find every module that imports the
ledger models and checks the **code** of each for a journal-line write:

- ``JournalLine(...)`` — building a line;
- ``JournalLine.objects`` / ``JournalLine._base_manager`` … ``.create``, ``.bulk_create``,
  ``.get_or_create``, ``.update_or_create``, ``.update``, ``.bulk_update``, ``.delete`` (also at
  the end of a queryset chain: ``JournalLine.objects.filter(...).update(...)``);
- raw SQL in any module of the package: ``INSERT INTO`` / ``UPDATE`` / ``DELETE FROM``
  ``ledger_journalline``.

Modules allowed (``allowed_modules``): the posting service; migrations are skipped (schema, not
data). Reading lines (``filter``, ``aggregate``…) is fine anywhere.

Configured in ``backend/pyproject.toml`` (``[tool.importlinter]``); run ``lint-imports`` from
``backend/`` (CI backend job).
"""

from __future__ import annotations

import ast
import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from importlinter import Contract, ContractCheck, fields, output

MODEL = "JournalLine"
MANAGERS = frozenset({"objects", "_base_manager", "_default_manager"})
WRITES = frozenset(
    {
        "create",
        "bulk_create",
        "get_or_create",
        "update_or_create",
        "update",
        "bulk_update",
        "delete",
    }
)
RAW_SQL = re.compile(
    r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+\"?ledger_journalline\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Write:
    line: int
    what: str


def _root_name(node: ast.AST) -> tuple[str | None, list[str]]:
    """The name at the root of an attribute/call chain and the attributes on the way."""
    attributes: list[str] = []
    while True:
        if isinstance(node, ast.Attribute):
            attributes.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Name):
            return node.id, list(reversed(attributes))
        else:
            return None, list(reversed(attributes))


def find_writes(source: str) -> list[Write]:
    """Journal-line writes in a module's source (see the module docstring)."""
    found: list[Write] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == MODEL:
                found.append(Write(node.lineno, f"{MODEL}(...)"))
                continue
            if isinstance(func, ast.Attribute) and func.attr in WRITES:
                root, chain = _root_name(func.value)
                if root == MODEL and chain and chain[0] in MANAGERS:
                    found.append(Write(node.lineno, f"{MODEL}.{'.'.join(chain)}.{func.attr}()"))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and RAW_SQL.search(node.value)
        ):
            found.append(Write(node.lineno, "raw SQL writing ledger_journalline"))
    return sorted(found, key=lambda w: w.line)


def _source(module: str) -> str | None:
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None or not spec.origin.endswith(".py"):
        return None
    return Path(spec.origin).read_text(encoding="utf-8")


class LedgerWritesContract(Contract):
    """Only the allowed modules write journal lines."""

    models_module = fields.StringField()
    allowed_modules = fields.ListField(subfield=fields.StringField())

    def check(self, graph: Any, verbose: bool) -> ContractCheck:
        models = str(self.models_module)
        root = models.split(".")[0]
        allowed = {str(m) for m in self.allowed_modules} | {models}  # type: ignore[attr-defined]
        importers = set(graph.find_modules_that_directly_import(models))
        violations: dict[str, list[dict[str, Any]]] = {}
        for module in sorted(graph.modules):
            if module != root and not module.startswith(f"{root}."):
                continue
            if module in allowed or ".migrations." in module:
                continue
            source = _source(module)
            if source is None:
                continue
            writes = find_writes(source)
            if module not in importers:
                # Without the model only raw SQL can write lines.
                writes = [w for w in writes if w.what.startswith("raw SQL")]
            if writes:
                violations[module] = [{"line": w.line, "what": w.what} for w in writes]
        return ContractCheck(kept=not violations, metadata={"violations": violations})

    def render_broken_contract(self, check: ContractCheck) -> None:
        violations = (check.metadata or {}).get("violations", {})
        for module, writes in violations.items():
            for write in writes:
                output.print_error(
                    f"{module}:{write['line']} writes journal lines ({write['what']}); post "
                    "through numo9.ledger.services instead.",
                    bold=False,
                )
            output.new_line()
