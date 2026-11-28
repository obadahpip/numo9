"""Statement import services: dry-run preview (F-02-T08), commit and background job (F-02-T09),
undo (F-02-T10).

``build_preview(bank, source)`` reads every line of a ``BankStatementSource`` and says what an
import would do with each one — **without writing anything**:

- ``new`` — readable, and its fingerprint (F-02-T07) isn't in the bank account yet;
- ``duplicate`` — the account already has the line (imported before, or an overlapping
  statement); the reason names the row and that it won't be imported twice;
- ``error`` — the line can't be read; its reasons name the row and the fix (F-02-T15).

The commit (F-02-T09) builds the same preview again under a lock on the bank account and inserts
exactly its ``new`` lines, so the preview's counts are the committed counts.

``commit_import`` inserts them atomically; ``start_commit`` runs it at once for up to
``ASYNC_THRESHOLD`` (2,000) lines, otherwise as the background job
``numo9.banking.commit_statement_import`` (A-08: one run per import, progress in the job tray —
reading and checking the lines report progress as they go; the insert itself is one transaction,
so the lines appear all at once when it commits).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from django.db import transaction
from django.utils import timezone

from numo9.jobs.models import JobRun
from numo9.jobs.runtime import start_job

from ..models import (
    BankAccount,
    StatementImport,
    StatementImportStatus,
    StatementLine,
    StatementLineStatus,
    StatementMapping,
)
from . import errors
from .errors import LineProblem, StatementError
from .fingerprint import account_key, existing_fingerprints, fingerprint_lines
from .layout import Layout, RawLine
from .mappings import remember_mapping
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


def classify(
    bank: BankAccount, lines: Sequence[RawLine], prints: Sequence[str | None]
) -> tuple[PreviewLine, ...]:
    """Each line's status against what the bank account holds now (one query per 5,000)."""
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
    return tuple(preview)


def _preview(source: BankStatementSource, lines: tuple[PreviewLine, ...]) -> Preview:
    parsed = source.parsed if isinstance(source, FileStatementSource) else None
    return Preview(
        source_name=source.source_name,
        lines=lines,
        format=parsed.format if parsed else "",
        encoding=parsed.encoding if parsed else "",
        delimiter=parsed.delimiter if parsed else "",
        warnings=parsed.warnings if parsed else (),
        balances=source.balances(),
    )


def build_preview(bank: BankAccount, source: BankStatementSource) -> Preview:
    """What importing ``source`` into ``bank`` would do (see the module docstring)."""
    lines = source.fetch_lines()
    prints = fingerprint_lines(account_key(bank), lines)
    return _preview(source, classify(bank, lines, prints))


# ---- commit (F-02-T09) --------------------------------------------------------------------------

#: Files with more lines than this are committed by the background job (progress in the tray).
ASYNC_THRESHOLD = 2000
INSERT_BATCH = 2000
Progress = Callable[[int, int], None]


def file_bytes(batch: StatementImport) -> bytes:
    """The uploaded file of an import (A-06 storage)."""
    from numo9.files import storage

    if batch.file is None:
        raise StatementError(errors.IMPORT_FILE_MISSING, name=batch.file_name)
    with storage.open_object(batch.file.file_key) as handle:
        data: bytes = handle.read()
    return data


def layout_of(batch: StatementImport) -> Layout | None:
    return Layout.from_dict(batch.mapping) if (batch.mapping or {}).get("columns") else None


def source_for(batch: StatementImport, layout: Layout | None = None) -> FileStatementSource:
    """The import's file as a statement source, read with ``layout`` (default: the batch's)."""
    return FileStatementSource(
        file_bytes(batch),
        batch.file_name,
        layout or layout_of(batch),
        last4=batch.bank_account.account_last4 or "",
    )


def _statement_line(bank: BankAccount, batch: StatementImport, item: PreviewLine) -> StatementLine:
    line = item.line
    assert line.date is not None and line.amount is not None  # noqa: S101 - new lines are readable
    return StatementLine(
        organisation_id=bank.organisation_id,
        bank_account=bank,
        statement_import=batch,
        date=line.date,
        amount=line.amount,
        description=line.description[:500],
        payee=line.payee[:255],
        reference=line.reference[:255],
        fitid=line.fitid[:255],
        fingerprint=item.fingerprint or "",
    )


def commit_import(
    batch: StatementImport,
    source: BankStatementSource,
    *,
    skip_errors: bool = False,
    mapping: StatementMapping | None = None,
    user: Any = None,
    progress: Progress | None = None,
) -> StatementImport:
    """Insert the new lines of ``source`` as ``batch`` — all of them or none.

    The file is read and fingerprinted first; then, in one transaction with the bank account row
    locked (two imports into one account never interleave), the lines are classified again
    against what the account holds now — exactly the preview's rule — and the new ones are
    inserted in batches of ``INSERT_BATCH``. Lines with errors refuse the import unless
    ``skip_errors``; the batch ends ``committed`` with its counts, its layout and saved mapping;
    the layout becomes the bank account's choice (``remember_mapping``)."""
    bank = BankAccount._base_manager.get(pk=batch.bank_account_id)
    lines = source.fetch_lines()
    prints = fingerprint_lines(account_key(bank), lines)
    steps = 2 * len(lines)
    if progress:
        progress(len(lines), steps)
    with transaction.atomic():
        bank = BankAccount._base_manager.select_for_update().get(pk=bank.pk)
        locked = StatementImport._base_manager.select_for_update().get(pk=batch.pk)
        if locked.status not in (StatementImportStatus.PENDING, StatementImportStatus.PROCESSING):
            raise StatementError(errors.IMPORT_NOT_PENDING, name=locked.file_name)
        preview = _preview(source, classify(bank, lines, prints))
        counts = preview.counts
        if counts["error"] and not skip_errors:
            raise StatementError(errors.IMPORT_HAS_ERRORS, count=counts["error"])
        rows = [_statement_line(bank, locked, item) for item in preview.of(LineStatus.NEW)]
        for start in range(0, len(rows), INSERT_BATCH):
            chunk = rows[start : start + INSERT_BATCH]
            StatementLine.objects.bulk_create(chunk)
            if progress:
                progress(len(lines) + start + len(chunk), steps)
        layout = source.layout if isinstance(source, FileStatementSource) else None
        locked.status = StatementImportStatus.COMMITTED
        locked.committed_at = timezone.now()
        locked.source_name = source.source_name
        locked.file_format = preview.format or locked.file_format
        locked.lines_total = counts["total"]
        locked.lines_new = counts["new"]
        locked.lines_duplicate = counts["duplicate"]
        locked.lines_error = counts["error"]
        if layout is not None:
            locked.mapping = layout.as_dict()
            headers = _headers(source, layout)
            locked.statement_mapping = remember_mapping(bank, layout, mapping, headers, user=user)
        locked.save()
    if progress:
        progress(steps, steps)
    batch.refresh_from_db()
    return batch


def _headers(source: BankStatementSource, layout: Layout) -> list[str]:
    parsed = source.parsed if isinstance(source, FileStatementSource) else None
    if parsed is None or parsed.table is None:
        return []
    header, _data = parsed.table.header_and_data(layout)
    return list(header.cells) if header is not None else []


def start_commit(
    batch: StatementImport,
    source: FileStatementSource,
    *,
    skip_errors: bool = False,
    mapping: StatementMapping | None = None,
    user: Any = None,
) -> tuple[StatementImport, JobRun | None]:
    """Commit now, or — over ``ASYNC_THRESHOLD`` lines — in the background job (the batch is
    ``processing`` until it ends; its run is returned for the job tray)."""
    total = batch.lines_total or len(source.fetch_lines())
    if total <= ASYNC_THRESHOLD:
        done = commit_import(batch, source, skip_errors=skip_errors, mapping=mapping, user=user)
        return done, None
    from ..tasks import commit_statement_import

    with transaction.atomic():
        locked = StatementImport._base_manager.select_for_update().get(pk=batch.pk)
        if locked.status != StatementImportStatus.PENDING:
            raise StatementError(errors.IMPORT_NOT_PENDING, name=locked.file_name)
        locked.status = StatementImportStatus.PROCESSING
        locked.mapping = source.layout.as_dict() if source.layout else {}
        locked.statement_mapping = mapping
        locked.save(update_fields=["status", "mapping", "statement_mapping", "updated_at"])
        person = user if getattr(user, "is_authenticated", False) else None
        run = start_job(
            commit_statement_import,
            organisation=locked.organisation,
            key=f"statement-import:{locked.public_id}",
            created_by=person,
            import_id=str(locked.public_id),
            skip_errors=skip_errors,
            user_id=person.pk if person else None,
        )
    return locked, run


# ---- undo (F-02-T10) ----------------------------------------------------------------------------


class ImportInUse(StatementError):
    """Undo refused: some of the import's lines are coded or matched (``lines``, date order)."""

    def __init__(self, lines: list[StatementLine]) -> None:
        super().__init__(errors.IMPORT_IN_USE, count=len(lines))
        self.lines = lines


def undo_import(batch: StatementImport, *, user: Any = None) -> StatementImport:
    """Remove every line of a committed import — only while none of them is coded or matched.

    The import's lines are locked first (a line being coded or matched at the same moment waits,
    then counts). Lines still uncoded or ignored are deleted — not soft-deleted: they were never
    postings, and the same file can then be imported again. The batch stays in the history as
    ``undone``."""
    with transaction.atomic():
        locked = StatementImport._base_manager.select_for_update().get(pk=batch.pk)
        if locked.status != StatementImportStatus.COMMITTED:
            raise StatementError(errors.IMPORT_NOT_COMMITTED, name=locked.file_name)
        lines = StatementLine.objects.select_for_update().filter(statement_import=locked)
        statuses = dict(lines.values_list("pk", "status"))
        in_use = [pk for pk, status in statuses.items() if status in IN_USE]
        if in_use:
            raise ImportInUse(
                list(StatementLine.objects.filter(pk__in=in_use).order_by("date", "pk"))
            )
        StatementLine.objects.filter(statement_import=locked).delete()
        locked.status = StatementImportStatus.UNDONE
        locked.undone_at = timezone.now()
        locked.save(update_fields=["status", "undone_at", "updated_at"])
    batch.refresh_from_db()
    return batch


IN_USE = frozenset({StatementLineStatus.CODED, StatementLineStatus.MATCHED})
