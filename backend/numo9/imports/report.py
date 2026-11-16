"""What an import does, row by row (shared by every importer).

A dry run and an applied import produce the same ``ImportReport``: one ``RowResult`` per data row
with its **action** — ``create``, ``update`` (with the changed fields as ``[before, after]``),
``unchanged`` or ``error`` (with the reasons) — and the totals. A dry run is the same work in a
transaction that is rolled back, so what the review step shows is exactly what applying does.

B-03-T07 stores these results (``ImportRun`` / ``ImportRunRow``) for the wizard and the job tray;
the in-memory form here is what importers return.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from django.utils.translation import gettext as _

#: A cell with this value empties the field (a blank cell leaves it unchanged).
CLEAR_TOKEN = "__CLEAR__"  # noqa: S105 (a cell value, not a secret)


class Action(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    ERROR = "error"


@dataclass(frozen=True)
class RowError:
    field: str  # the field key ("" for the whole row)
    code: str
    message: str


@dataclass
class RowResult:
    row: int  # row number in the file
    key: str  # the match key's value (e.g. the account code)
    action: Action = Action.UNCHANGED
    label: str = ""  # how the record is shown ("1060 · Chequing")
    changes: dict[str, list[Any]] = field(default_factory=dict)
    errors: list[RowError] = field(default_factory=list)

    def fail(self, field_key: str, code: str, message: str) -> None:
        self.action = Action.ERROR
        self.errors.append(RowError(field_key, code, message))


@dataclass
class ImportReport:
    entity: str
    applied: bool
    rows: list[RowResult] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        found = Counter(row.action.value for row in self.rows)
        return {action.value: found.get(action.value, 0) for action in Action}

    @property
    def changed(self) -> int:
        return self.counts[Action.CREATE] + self.counts[Action.UPDATE]

    def errors_csv(self, labels: dict[str, str] | None = None) -> bytes:
        """The errors as a CSV a spreadsheet opens (UTF-8 with BOM): row, column, reason."""
        labels = labels or {}
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow([_("Row"), _("Column"), _("Reason")])
        for row in self.rows:
            for error in row.errors:
                writer.writerow([row.row, labels.get(error.field, error.field), error.message])
        return ("﻿" + buffer.getvalue()).encode("utf-8")
