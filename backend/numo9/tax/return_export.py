"""GST/HST return exports (G-03-T13): the worksheet's lines as a PDF (Letter, 1-inch margins,
the A-10 document baseline) and a CSV of line values to key into CRA My Business Account or
NETFILE — the same lines, labels and amounts as the screen.

``render_csv(tax_return, locale)`` → ``line,label,amount`` rows (cents, a dot as the decimal
mark: what NETFILE takes); ``render_pdf(tax_return, locale)`` → the printable worksheet with the
registration, the period, the method, the status (and the confirmation number once filed).
"""

from __future__ import annotations

import csv
import io
from typing import Any

from django.utils import translation
from django.utils.translation import gettext as _

from numo9.documents.formatting import format_date, format_money

from .return_lines import LINES, line_labels

#: The lines shown as totals (bold, ruled above) — as on the worksheet screen.
TOTAL_LINES = frozenset({"105", "108", "109", "112", "113A", "113C"})


def rows(tax_return: Any, locale: str = "en-ca") -> list[tuple[str, str, str]]:
    values = tax_return.lines or {}
    with translation.override(locale):
        labels = line_labels()
    return [(line, labels[line], str(values.get(line, "0.00"))) for line in LINES]


def render_csv(tax_return: Any, locale: str = "en-ca") -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    with translation.override(locale):
        writer.writerow([_("Line"), _("Description"), _("Amount")])
    for row in rows(tax_return, locale):
        writer.writerow(row)
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def render_pdf(tax_return: Any, locale: str = "en-ca") -> bytes:
    from numo9.documents.pdf import render_pdf as to_pdf

    period = tax_return.period
    registration = tax_return.registration
    with translation.override(locale):
        context = {
            "issuer": {"legal_name": tax_return.organisation.name},
            "number": registration.number,
            "start": format_date(period.start, locale),
            "end": format_date(period.end, locale),
            "due": format_date(period.due_date, locale),
            "method": tax_return.get_method_display(),
            "status": tax_return.get_status_display(),
            "version": tax_return.version,
            "confirmation_no": tax_return.confirmation_no,
            "filed_on": format_date(tax_return.filed_on, locale) if tax_return.filed_on else "",
            "lines": [
                {
                    "line": line,
                    "label": label,
                    "amount": format_money(amount, locale),
                    "total": line in TOTAL_LINES,
                }
                for line, label, amount in rows(tax_return, locale)
            ],
        }
        return to_pdf("tax/return.html", context, locale=locale)


def filename(tax_return: Any, fmt: str) -> str:
    period = tax_return.period
    span = f"{period.start:%Y-%m-%d}-{period.end:%Y-%m-%d}"
    return f"gst-hst-return-{span}-v{tax_return.version}.{fmt}"
