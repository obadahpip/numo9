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

import calendar
import datetime as dt
import re
from collections.abc import Iterator
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


# ---- occurrences (C-04-T05) ------------------------------------------------------------------


def _clamped(parsed: rrule, start: dt.date) -> bool:
    """Monthly / yearly rules without their own day rules land on the start's day, clamped."""
    return (
        frequency(parsed) in (MONTHLY, YEARLY)
        and not re.search(r"BY(MONTH)?DAY|BYSETPOS|BYYEARDAY|BYWEEKNO", str(parsed).upper())
        and start.day > 28
    )


def occurrences(
    rule: str,
    start: dt.date,
    end: dt.date | None = None,
    *,
    after: dt.date | None = None,
    until: dt.date | None = None,
    limit: int | None = None,
) -> list[dt.date]:
    """The schedule's dates from ``start`` to ``end`` (inclusive), those after ``after`` and up
    to ``until`` only, at most ``limit`` (and ``MAX_OCCURRENCES``)."""
    parsed = parse_rule(rule, start)
    cap = min(limit or MAX_OCCURRENCES, MAX_OCCURRENCES)
    last = min(d for d in (end, until) if d is not None) if (end or until) else None
    out: list[dt.date] = []
    for day in _dates(parsed, start):
        if last is not None and day > last:
            break
        if after is not None and day <= after:
            continue
        out.append(day)
        if len(out) >= cap:
            break
    return out


def _dates(parsed: rrule, start: dt.date) -> Iterator[dt.date]:
    if not _clamped(parsed, start):
        for moment in parsed:
            yield moment.date()
        return
    # Step month by month from the first of the start's month, then clamp to the start's day.
    first = parsed.replace(dtstart=dt.datetime(start.year, start.month, 1))
    until = getattr(parsed, "_until", None)  # the rule's own UNTIL applies to the clamped day
    for moment in first:
        last_day = calendar.monthrange(moment.year, moment.month)[1]
        day = moment.date().replace(day=min(start.day, last_day))
        if until is not None and day > until.date():
            return
        if day >= start:
            yield day


# ---- generation (C-04-T06) -------------------------------------------------------------------

JOB = "numo9.ledger.recurring_journals"
SOURCE_TYPE = "ledger.recurringjournal"


def first_run(template: RecurringJournalTemplate) -> dt.date | None:
    """The schedule's first occurrence (``next_run`` of a new or edited template)."""
    dates = occurrences(template.rrule, template.start_date, template.end_date, limit=1)
    return dates[0] if dates else None


def spec_for(template: RecurringJournalTemplate, day: dt.date) -> Any:
    """The journal of the occurrence on ``day``, its lines resolved by public id now — an
    account archived or a contact removed since the template was saved is refused then."""
    from numo9.contacts.models import Contact

    from .models import Account
    from .validation import JournalSpec, LineSpec

    lines = template.lines
    accounts = {
        str(a.public_id): a
        for a in Account.objects.filter(public_id__in=[line["account"] for line in lines])
    }
    contacts = {
        str(c.public_id): c
        for c in Contact.objects.filter(
            public_id__in=[line["contact"] for line in lines if line.get("contact")],
            deleted_at__isnull=True,
        )
    }
    missing = [line["account"] for line in lines if line["account"] not in accounts]
    missing += [
        line["contact"] for line in lines if line.get("contact") and line["contact"] not in contacts
    ]
    if missing:
        from .models import LedgerError

        raise LedgerError(
            _("The recurring journal refers to a record that no longer exists (%(id)s)."),
            code="ledger.recurring.reference_missing",
            params={"id": missing[0]},
        )
    return JournalSpec(
        date=day,
        journal_type=template.journal_type,
        narration=template.narration or template.name,
        source_type=SOURCE_TYPE,
        source_id=str(template.public_id),
        lines=tuple(
            LineSpec(
                account=accounts[line["account"]],
                debit=Decimal(line["debit"]),
                credit=Decimal(line["credit"]),
                book=line["book"],
                contact=contacts.get(line["contact"]) if line.get("contact") else None,
                description=line.get("description") or "",
            )
            for line in lines
        ),
    )


def _reason(error: Exception) -> tuple[str, str]:
    """A refusal's code and message (ledger errors, lock / closed-period 409s)."""
    detail = getattr(error, "detail", None)
    if isinstance(detail, dict):
        return str(detail.get("code") or "invalid"), str(detail.get("detail") or error)
    messages = getattr(error, "messages", None) or [str(error)]
    code = getattr(error, "code", None) or (
        getattr(error, "error_list", [None])[0] and getattr(error.error_list[0], "code", None)  # type: ignore[attr-defined]
    )
    return str(code or "invalid"), " ".join(str(m) for m in messages)


def run_occurrence(template: RecurringJournalTemplate, day: dt.date) -> Any:
    """Generate the occurrence on ``day`` once: the template row is locked and the run row is
    unique per (template, date), so a second tick (two workers, a restart) finds it and does
    nothing (``None``). A refused journal is recorded as a skipped run with the reason — never
    posted on another date. Above the approval threshold a "post" template's journal waits for
    approval (submitted for its author) instead of being refused."""
    from django.db import IntegrityError, transaction
    from rest_framework.exceptions import APIException

    from numo9.audit import service as audit
    from numo9.orgsettings.models import LockModule

    from .approvals import ApprovalRequired, submit_for_approval
    from .models import (
        LedgerError,
        RecurringJournalRun,
        RecurringMode,
        RecurringRunStatus,
    )
    from .periods import assert_can_post
    from .services import post_journal, save_draft

    organisation = template.organisation
    with transaction.atomic():
        locked = RecurringJournalTemplate.objects.select_for_update().get(pk=template.pk)
        if RecurringJournalRun.objects.filter(template=locked, occurrence_date=day).exists():
            return None
        entry = None
        code = message = ""
        try:
            with transaction.atomic():
                spec = spec_for(locked, day)
                # A locked or closed date is skipped for drafts too (never dated elsewhere).
                assert_can_post(organisation, day, None, LockModule.GL)
                if locked.mode == RecurringMode.POST:
                    try:
                        with transaction.atomic():
                            entry = post_journal(spec, organisation=organisation, user=None)
                    except ApprovalRequired:
                        draft = save_draft(spec, organisation=organisation, user=None)
                        entry = submit_for_approval(draft, locked.created_by)
                        code = "ledger.recurring.awaiting_approval"
                else:
                    entry = save_draft(spec, organisation=organisation, user=None)
        except (LedgerError, ValidationError, APIException) as error:
            entry = None
            code, message = _reason(error)
        try:
            with transaction.atomic():
                run = RecurringJournalRun.objects.create(
                    organisation=organisation,
                    template=locked,
                    occurrence_date=day,
                    template_version=locked.version,
                    status=RecurringRunStatus.CREATED if entry else RecurringRunStatus.SKIPPED,
                    entry=entry,
                    code=code,
                    message=message,
                )
        except IntegrityError:  # another worker won the insert: its journal stands
            transaction.set_rollback(True)
            return None
        if entry is None:
            audit.record(
                "ledger.recurringjournaltemplate.skipped",
                obj=locked,
                changes={},
                meta={"date": day.isoformat(), "code": code, "reason": message, "job": JOB},
                actor=None,
            )
        return run


def generate_due(organisation: Any, today: dt.date) -> list[Any]:
    """Every due occurrence (``next_run`` ≤ ``today``) of the organisation's active templates,
    oldest first; ``next_run`` moves to the first occurrence after ``today`` (``None`` when the
    schedule is over)."""
    from numo9.tenancy.context import org_context

    runs: list[Any] = []
    with org_context(organisation):
        due = RecurringJournalTemplate.objects.filter(
            paused=False, deleted_at__isnull=True, next_run__isnull=False, next_run__lte=today
        ).order_by("next_run", "pk")
        for template in due:
            dates = occurrences(
                template.rrule,
                template.start_date,
                template.end_date,
                until=today,
                after=template.next_run - dt.timedelta(days=1) if template.next_run else None,
            )
            for day in dates:
                run = run_occurrence(template, day)
                if run is not None:
                    runs.append(run)
            following = occurrences(
                template.rrule, template.start_date, template.end_date, after=today, limit=1
            )
            RecurringJournalTemplate.objects.filter(pk=template.pk).update(
                next_run=following[0] if following else None
            )
    return runs


def generate_all(now: dt.datetime | None = None) -> int:
    """The hourly job: every organisation, on its own date. The number of runs recorded."""
    from django.utils import timezone

    from numo9.orgsettings.locks import local_date
    from numo9.tenancy.models import Organisation

    now = now or timezone.now()
    count = 0
    for organisation in Organisation.objects.order_by("pk").iterator():
        count += len(generate_due(organisation, local_date(organisation, now)))
    return count
