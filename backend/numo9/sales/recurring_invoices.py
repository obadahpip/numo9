"""Recurring invoices (D-04) — the schedule (T02), placeholders (T03) and proration (T04).

**Schedule** — the recurring-journal engine (C-04-T05) reused as is: an RFC 5545 rule from the
template's start date, monthly and yearly rules on the 29th–31st clamped to the month's last day
(31 January → 28 February → 31 March; 29 February in a leap year), up to the end date.

- ``occurrences(template, …)`` — the dates; ``first_run(template)`` — the first;
- ``period_of(template, day)`` — the period an occurrence bills: from its date to the day before
  the schedule's next date (31 January → 27 February);
- ``due_for(template, day)`` — the due date of the invoice of that occurrence: the template's terms,
  else the contact's default sales terms, else the organisation's (D-01-T07).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from numo9.documents import due_dates
from numo9.ledger import recurring as engine


def validate_schedule(template: Any) -> None:
    """``ValidationError`` for a rule the engine can't read or an end before the start."""
    engine.parse_rule(template.rrule, template.start_date)
    if template.end_date is not None and template.end_date < template.start_date:
        raise ValidationError(
            {
                "end_date": ValidationError(
                    _("The end date is before the start date."),
                    code="sales.recurring.end_before_start",
                )
            }
        )


def occurrences(
    template: Any,
    *,
    after: dt.date | None = None,
    until: dt.date | None = None,
    limit: int | None = None,
) -> list[dt.date]:
    return engine.occurrences(
        template.rrule,
        template.start_date,
        template.end_date,
        after=after,
        until=until,
        limit=limit,
    )


def first_run(template: Any) -> dt.date | None:
    dates = occurrences(template, limit=1)
    return dates[0] if dates else None


def next_after(template: Any, day: dt.date) -> dt.date | None:
    """The schedule's next date after ``day`` — within the end date."""
    dates = occurrences(template, after=day, limit=1)
    return dates[0] if dates else None


def _open_rule(rule: str) -> str:
    """The rule without its own COUNT / UNTIL — the cadence only."""
    text = rule.strip()
    if text.upper().startswith("RRULE:"):
        text = text[6:]
    return ";".join(p for p in text.split(";") if not p.upper().startswith(("COUNT=", "UNTIL=")))


def period_of(template: Any, day: dt.date) -> tuple[dt.date, dt.date]:
    """The period the occurrence on ``day`` bills: to the day before the cadence's next date
    (neither the end date nor the rule's own COUNT / UNTIL cut it — proration does, T04)."""
    following = engine.occurrences(
        _open_rule(template.rrule), template.start_date, after=day, limit=1
    )
    return day, following[0] - dt.timedelta(days=1)


def terms_for(template: Any) -> Any:
    term = getattr(template, "terms", None)
    if term is not None:
        return due_dates.Terms(
            term.terms_type, term.days, term, term.discount_pct, term.discount_days
        )
    return due_dates.document_terms(due_dates.SALES, template.contact, template.organisation)


def due_for(template: Any, day: dt.date) -> dt.date:
    terms = terms_for(template)
    return due_dates.due_date(day, terms.terms_type, terms.days)
