"""Import runs: the stored dry run and import of a file (B-03-T07, T08).

``create_run(entity, data, filename)`` parses the file once and keeps its cells;
``dry_run(run, columns, options)`` maps, runs the entity's importer in dry-run mode and stores the
report (``ImportRunRow`` per data row — action, changes, errors; **no record is written**);
``apply_run(run)`` imports for real with the same cells, mapping and options and stores the
outcome. Importers register per entity (``register_runner``): contacts and people (B-03).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import ImportRun, ImportRunRow, ImportRunStatus
from .parser import Row, Sheet, parse_file
from .report import ImportReport

Runner = Callable[..., ImportReport]
_runners: dict[str, Runner] = {}


def register_runner(entity: str, runner: Runner) -> None:
    _runners[entity] = runner


def runner(entity: str) -> Runner:
    return _runners[entity]


def create_run(entity: str, data: bytes, filename: str, *, actor: Any = None) -> ImportRun:
    from numo9.tenancy.context import current_org

    sheet = parse_file(data, filename).sheet
    run = ImportRun(
        organisation=current_org(),
        entity=entity,
        filename=filename,
        sheet=sheet.name,
        headers=list(sheet.headers),
        cells=[[row.number, list(row.cells)] for row in sheet.rows],
    )
    run.created_by_id = getattr(actor, "pk", None)
    run.save()
    return run


def sheet_of(run: ImportRun) -> Sheet:
    return Sheet(
        name=run.sheet,
        headers=tuple(run.headers),
        header_row=1,
        rows=tuple(Row(number=number, cells=tuple(cells)) for number, cells in run.cells),
    )


def store_report(run: ImportRun, report: ImportReport) -> None:
    with transaction.atomic():
        ImportRunRow.objects.filter(run=run).delete()
        ImportRunRow.objects.bulk_create(
            ImportRunRow(
                organisation_id=run.organisation_id,
                run=run,
                row=result.row,
                key=result.key[:255],
                label=result.label[:300],
                action=result.action.value,
                changes=result.changes,
                errors=[
                    {"field": e.field, "code": e.code, "message": e.message} for e in result.errors
                ],
            )
            for result in report.rows
        )
        run.counts = report.counts
        if report.applied:
            run.status = ImportRunStatus.APPLIED
            run.applied_at = timezone.now()
        else:
            run.status = ImportRunStatus.REVIEWED
        run.save(update_fields=["counts", "status", "applied_at", "updated_at"])


def dry_run(
    run: ImportRun, columns: Mapping[str, str], options: Mapping[str, Any] | None = None
) -> ImportReport:
    run.columns = dict(columns)
    run.options = dict(options or {})
    run.save(update_fields=["columns", "options", "updated_at"])
    report = runner(run.entity)(
        sheet_of(run), run.columns, apply=False, filename=run.filename, **run.options
    )
    store_report(run, report)
    return report


def apply_run(run: ImportRun, *, actor: Any = None) -> ImportReport:
    report = runner(run.entity)(
        sheet_of(run), run.columns, apply=True, actor=actor, filename=run.filename, **run.options
    )
    store_report(run, report)
    return report
