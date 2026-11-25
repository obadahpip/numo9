"""Report header (K-01-T06): what every report prints above its figures.

``report_header(organisation, period=…, as_of=…, today=…, basis=…, book=…, language=…)`` →
``ReportHeader``:

- ``display_name`` and ``legal_name`` — from the organisation settings (A-05); the legal name
  falls back to the display name when it isn't set yet, and is left out when it is the same;
- ``period_label`` — "1 Apr 2026 to 31 Mar 2027" for a period, "As at 30 Jun 2026" for a balance
  date;
- ``status_label`` — "Year to date — unaudited" when the period (or balance date) ends **after
  today**: the figures can still change; empty otherwise;
- ``basis_label`` — G-06 via K-01-T03: "Basis: Cash (organisation default)" or "(this report)";
- ``book_label`` — "Accounting book" or "Tax book".

Labels are in the report's language (the person's, or the document language of an export).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass
from typing import Any

from django.utils import translation
from django.utils.translation import gettext as _

from numo9.documents.formatting import format_date

from .parameters import DateRange, resolve_basis


@dataclass(frozen=True)
class ReportHeader:
    title: str
    display_name: str
    legal_name: str
    period_label: str
    status_label: str
    basis_label: str
    book_label: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def report_header(
    organisation: Any,
    *,
    title: str,
    today: dt.date,
    period: DateRange | None = None,
    as_of: dt.date | None = None,
    basis: str | None = None,
    book: str = "accounting",
    language: str | None = None,
) -> ReportHeader:
    from numo9.orgsettings.service import get_settings
    from numo9.tenancy.context import org_context

    if (period is None) == (as_of is None):
        raise ValueError("A header is for a period or for a balance date.")
    locale = (language or translation.get_language() or "en-ca").lower()
    with org_context(organisation):
        settings = get_settings(organisation)
        display = settings.display_name or organisation.name
        legal = settings.legal_name or display
        with translation.override(locale):
            if period is not None:
                label = _("%(start)s to %(end)s") % {
                    "start": format_date(period.start, locale),
                    "end": format_date(period.end, locale),
                }
                end = period.end
            else:
                assert as_of is not None  # noqa: S101 — checked above
                label = _("As at %(date)s") % {"date": format_date(as_of, locale)}
                end = as_of
            status = _("Year to date — unaudited") if end > today else ""
            book_label = _("Tax book") if book == "tax" else _("Accounting book")
            basis_label = resolve_basis(organisation, basis).label
    return ReportHeader(
        title=title,
        display_name=display,
        legal_name="" if legal == display else legal,
        period_label=label,
        status_label=status,
        basis_label=basis_label,
        book_label=book_label,
    )


def header_for(
    organisation: Any,
    report: Any,
    params: dict[str, Any],
    *,
    today: dt.date,
    language: str | None = None,
) -> ReportHeader:
    """The header of a run of ``report`` with its cleaned ``params``: a period when the report
    takes ``date_from``/``date_to``, a balance date (``as_of``, today when empty) otherwise."""
    book = params.get("book") or "accounting"
    basis = params.get("basis")
    if params.get("date_from") and params.get("date_to"):
        return report_header(
            organisation,
            title=str(report.name),
            today=today,
            period=DateRange(params["date_from"], params["date_to"]),
            basis=basis,
            book=book,
            language=language,
        )
    return report_header(
        organisation,
        title=str(report.name),
        today=today,
        as_of=params.get("as_of") or today,
        basis=basis,
        book=book,
        language=language,
    )
