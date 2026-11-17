"""Files of a bulk job (V-03-T06, T07): the export action's list and every job's results.

- ``export_file(job)`` — the export action: one line per organisation exported, in CSV or XLSX
  (the job's ``format``), columns name, Business Number, status, groups, tags, assigned staff;
- ``results_csv(job)`` — every job: one line per selected organisation with its outcome, reason
  and message, and the before/after values — the downloadable result of V-03 ("never a silent
  partial failure").
"""

from __future__ import annotations

import csv
import io
import json

from django.utils.translation import gettext as _

from .actions import EXPORT_COLUMNS
from .models import BulkJob, RowOutcome


def _headers() -> list[str]:
    return [
        _("Organisation"),
        _("Business Number"),
        _("Status"),
        _("Groups"),
        _("Tags"),
        _("Assigned staff"),
    ]


def export_rows(job: BulkJob) -> list[list[str]]:
    rows = job.rows.filter(outcome=RowOutcome.SUCCEEDED).order_by("position")
    return [[str(row.after.get(column, "")) for column in EXPORT_COLUMNS] for row in rows]


def export_file(job: BulkJob) -> tuple[bytes, str, str]:
    """``(content, content type, file name)`` of the export action's list."""
    fmt = job.params.get("format", "csv")
    stamp = job.created_at.strftime("%Y-%m-%d")
    if fmt == "xlsx":
        from openpyxl import Workbook

        book = Workbook()
        sheet = book.active
        sheet.title = _("Organisations")[:31]
        sheet.append(_headers())
        for line in export_rows(job):
            sheet.append(line)
        out = io.BytesIO()
        book.save(out)
        return (
            out.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"organisations-{stamp}.xlsx",
        )
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(_headers())
    writer.writerows(export_rows(job))
    return ("﻿" + text.getvalue()).encode(), "text/csv", f"organisations-{stamp}.csv"


def results_csv(job: BulkJob) -> bytes:
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(
        [_("Organisation"), _("Outcome"), _("Reason"), _("Message"), _("Before"), _("After")]
    )
    for row in job.rows.select_related("organisation").order_by("position"):
        writer.writerow(
            [
                row.organisation.name,
                RowOutcome(row.outcome).label,
                row.reason,
                row.message,
                json.dumps(row.before, ensure_ascii=False, sort_keys=True) if row.before else "",
                json.dumps(row.after, ensure_ascii=False, sort_keys=True) if row.after else "",
            ]
        )
    return ("﻿" + text.getvalue()).encode()
