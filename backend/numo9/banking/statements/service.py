"""Statement import services: dry-run preview (F-02-T08).

``build_preview(bank, source)`` reads every line of a ``BankStatementSource`` and says what an
import would do with each one — **without writing anything**:

- ``new`` — readable, and its fingerprint (F-02-T07) isn't in the bank account yet;
- ``duplicate`` — the account already has the line (imported before, or an overlapping
  statement); the reason names the row and that it won't be imported twice;
- ``error`` — the line can't be read; its reasons name the row and the fix (F-02-T15).

The commit (F-02-T09) builds the same preview again under a lock on the bank account and inserts
exactly its ``new`` lines, so the preview's counts are the committed counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ..models import BankAccount
from . import errors
from .errors import LineProblem
from .fingerprint import account_key, existing_fingerprints, fingerprint_lines
from .layout import RawLine
from .source import BankStatementSource, FileStatementSource, StatementBalances


class LineStatus(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    ERROR = "error"


@dataclass(frozen=True)
class PreviewLine:
    line: RawLine
    status: LineStatus
    fingerprint: str | None
    reasons: tuple[LineProblem, ...] = ()


@dataclass(frozen=True)
class Preview:
    source_name: str
    lines: tuple[PreviewLine, ...]
    format: str = ""
    encoding: str = ""
    delimiter: str = ""
    warnings: tuple[str, ...] = ()
    balances: StatementBalances = field(default_factory=StatementBalances)

    def of(self, status: LineStatus) -> list[PreviewLine]:
        return [line for line in self.lines if line.status == status]

    @property
    def counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in LineStatus}
        for line in self.lines:
            counts[line.status.value] += 1
        return {"total": len(self.lines), **counts}


def build_preview(bank: BankAccount, source: BankStatementSource) -> Preview:
    """What importing ``source`` into ``bank`` would do (see the module docstring)."""
    lines = source.fetch_lines()
    prints = fingerprint_lines(account_key(bank), lines)
    existing = existing_fingerprints(bank, prints)
    preview: list[PreviewLine] = []
    for line, fingerprint in zip(lines, prints, strict=True):
        if fingerprint is None:
            preview.append(PreviewLine(line, LineStatus.ERROR, None, line.problems))
        elif fingerprint in existing:
            reason = LineProblem(errors.ROW_DUPLICATE, {"row": line.row})
            preview.append(PreviewLine(line, LineStatus.DUPLICATE, fingerprint, (reason,)))
        else:
            preview.append(PreviewLine(line, LineStatus.NEW, fingerprint))
    parsed = source.parsed if isinstance(source, FileStatementSource) else None
    return Preview(
        source_name=source.source_name,
        lines=tuple(preview),
        format=parsed.format if parsed else "",
        encoding=parsed.encoding if parsed else "",
        delimiter=parsed.delimiter if parsed else "",
        warnings=parsed.warnings if parsed else (),
        balances=source.balances(),
    )
