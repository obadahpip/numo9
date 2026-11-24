"""Recurring journals (C-04-T04…T06).

**Template** (``RecurringJournalTemplate``, T04) — ``validate_template(template)`` refuses, with a
stable code per field:

- ``ledger.recurring.rrule_invalid`` — the schedule isn't an RFC 5545 rule (``FREQ=MONTHLY;…``)
  of a supported frequency (daily, weekly, monthly, yearly), or carries its own ``DTSTART``
  (the start date is a field of its own);
- ``ledger.recurring.lines_invalid`` — fewer than two lines, a line that isn't
  ``{account, debit, credit, book, contact, description}``, an amount that isn't a positive
  number with two decimals, a line with both or neither side, an unknown book;
- ``ledger.recurring.unbalanced`` — debits ≠ credits;
- ``ledger.recurring.account_unknown`` / ``contact_unknown`` — an id that isn't this
  organisation's;
- ``ledger.recurring.type_invalid`` — a system journal type (Closing, Payroll, Depreciation);
- ``ledger.recurring.end_before_start``.

"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

from dateutil.rrule import DAILY, MONTHLY, WEEKLY, YEARLY, rrule, rrulestr
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from .models import SELECTABLE_CATEGORIES, Book, RecurringJournalTemplate

SUPPORTED_FREQUENCIES = {DAILY, WEEKLY, MONTHLY, YEARLY}
LINE_KEYS = {"account", "debit", "credit", "book", "contact", "description"}
CENT = Decimal("0.01")
#: A ceiling on the dates a schedule is asked for at once (preview, catch-up after downtime).
MAX_OCCURRENCES = 1000


def frequency(parsed: rrule) -> int:
    """The rule's FREQ (dateutil keeps it private)."""
    return int(getattr(parsed, "_freq"))  # noqa: B009


def _error(field: str, message: str, code: str, **params: Any) -> ValidationError:
    return ValidationError({field: ValidationError(message, code=code, params=params or None)})


def parse_rule(rule: str, start: dt.date) -> rrule:
    """The rule as ``dateutil`` reads it, from ``start`` — or ``ValidationError`` (``rrule``)."""
    text = (rule or "").strip()
    if text.upper().startswith("RRULE:"):
        text = text[6:]
    if not text or "DTSTART" in text.upper() or "\n" in text:
        raise _error(
            "rrule",
            _("Give the schedule as a recurrence rule, e.g. FREQ=MONTHLY;INTERVAL=1."),
            "ledger.recurring.rrule_invalid",
        )
    try:
        parsed = rrulestr(text, dtstart=dt.datetime.combine(start, dt.time()))
    except (ValueError, TypeError) as error:
        raise _error(
            "rrule",
            _("The schedule isn't a valid recurrence rule: %(reason)s"),
            "ledger.recurring.rrule_invalid",
            reason=str(error),
        ) from error
    if not isinstance(parsed, rrule) or frequency(parsed) not in SUPPORTED_FREQUENCIES:
        raise _error(
            "rrule",
            _("A journal can repeat daily, weekly, monthly or yearly."),
            "ledger.recurring.rrule_invalid",
        )
    return parsed


def _amount(value: Any) -> Decimal | None:
    if value in (None, "", 0, "0"):
        return Decimal("0")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if amount < 0 or amount != amount.quantize(CENT) or amount >= Decimal("1e16"):
        return None
    return amount


def clean_lines(lines: Any) -> list[dict[str, Any]]:
    """The template's lines checked for shape and balance, amounts as two-decimal strings."""
    if not isinstance(lines, list) or len(lines) < 2:
        raise _error(
            "lines",
            _("A recurring journal needs at least two lines."),
            "ledger.recurring.lines_invalid",
        )
    cleaned: list[dict[str, Any]] = []
    debits = credits = Decimal("0")
    for number, line in enumerate(lines, start=1):
        if not isinstance(line, dict) or not line.get("account") or set(line) - LINE_KEYS:
            raise _error(
                "lines",
                _("Line %(line)s isn't a journal line (account, debit, credit, book…)."),
                "ledger.recurring.lines_invalid",
                line=number,
            )
        debit, credit = _amount(line.get("debit")), _amount(line.get("credit"))
        if debit is None or credit is None or (debit > 0) == (credit > 0):
            raise _error(
                "lines",
                _("Line %(line)s needs a debit or a credit: a positive amount, two decimals."),
                "ledger.recurring.lines_invalid",
                line=number,
            )
        book = line.get("book") or Book.BOTH
        if book not in Book.values:
            raise _error(
                "lines",
                _("Line %(line)s: “%(book)s” isn't a book."),
                "ledger.recurring.lines_invalid",
                line=number,
                book=book,
            )
        debits += debit
        credits += credit
        cleaned.append(
            {
                "account": str(line["account"]),
                "debit": f"{debit:.2f}",
                "credit": f"{credit:.2f}",
                "book": book,
                "contact": str(line["contact"]) if line.get("contact") else None,
                "description": str(line.get("description") or ""),
            }
        )
    if debits != credits:
        raise _error(
            "lines",
            _("Debits (%(debits)s) and credits (%(credits)s) differ by %(difference)s."),
            "ledger.recurring.unbalanced",
            debits=f"{debits:.2f}",
            credits=f"{credits:.2f}",
            difference=f"{abs(debits - credits):.2f}",
        )
    return cleaned


def _references(lines: list[dict[str, Any]]) -> None:
    from numo9.contacts.models import Contact

    from .models import Account

    accounts = {line["account"] for line in lines}
    try:
        known = {
            str(i)
            for i in Account.objects.filter(public_id__in=accounts).values_list(
                "public_id", flat=True
            )
        }
    except ValidationError as error:  # not a UUID
        raise _error(
            "lines", _("An account id isn't valid."), "ledger.recurring.account_unknown"
        ) from error
    if accounts - known:
        raise _error(
            "lines",
            _("There's no account with id %(id)s in this organisation."),
            "ledger.recurring.account_unknown",
            id=sorted(accounts - known)[0],
        )
    contacts = {line["contact"] for line in lines if line["contact"]}
    if contacts:
        try:
            found = {
                str(i)
                for i in Contact.objects.filter(
                    public_id__in=contacts, deleted_at__isnull=True
                ).values_list("public_id", flat=True)
            }
        except ValidationError as error:
            raise _error(
                "lines", _("A contact id isn't valid."), "ledger.recurring.contact_unknown"
            ) from error
        if contacts - found:
            raise _error(
                "lines",
                _("There's no contact with id %(id)s in this organisation."),
                "ledger.recurring.contact_unknown",
                id=sorted(contacts - found)[0],
            )


def validate_template(template: RecurringJournalTemplate) -> None:
    """Every rule of the module docstring; normalises ``lines`` in place."""
    if template.journal_type not in SELECTABLE_CATEGORIES:
        raise _error(
            "journal_type",
            _("A recurring journal can't be of a system type."),
            "ledger.recurring.type_invalid",
        )
    if template.end_date is not None and template.end_date < template.start_date:
        raise _error(
            "end_date",
            _("The end date is before the start date."),
            "ledger.recurring.end_before_start",
        )
    parse_rule(template.rrule, template.start_date)
    template.lines = clean_lines(template.lines)
    _references(template.lines)
