"""Period close and year-end (C-06-T02, T04, T05).

``close(organisation, module, period_end, user)`` (T02) — close a module up to the end of a month:
the module's lock dates move to ``period_end`` at both levels (everyone — advisers included —
and advisers only), the lock dates before are kept on the ``PeriodClose`` row to be restored on
reopen, and the close is audited (``ledger.period.closed``). Refused: a date that isn't a month
end (``ledger.close.not_month_end``), a period already locked (``ledger.close.already_locked``),
or an earlier period than one already closed — closes go forward in order
(``ledger.close.out_of_order``).

``close_year(organisation, fiscal_year_end, user)`` (T04) — the year-end roll, per book: the
year's revenue and expense balances in the **accounting** book (lines ``both`` + ``accounting``)
are zeroed by a closing journal (type Closing, posted by the ``year_end`` process) dated the
fiscal year end against **Retained earnings**; the same in the **tax** book (``both`` + ``tax``
lines; its own net income when the books differ). Then the general ledger is closed to the year
end (as ``close``, kind year-end). A December close already there is folded into the year-end.
At most one open year-end close per year end: no closing journal is created twice.

``reopen(period_close, user, reason, force=False)`` (T05) — **advisers only**, a reason is
required; only the latest open close of the module, unless ``force``. The lock dates go back
to what they were before (or to the latest close still open), a year-end's closing journals are
reversed (retained earnings restored), and the reopen is audited (``ledger.period.reopened``).

``year_end_check`` is registered with the posting engine (``periods.register_period_check``):
a posting dated in a fiscal year whose year-end close is open is refused as a closed period.
"""

from __future__ import annotations

import calendar
import datetime as dt
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.orgsettings.locks import is_adviser
from numo9.orgsettings.models import LockDate, LockLevel, LockModule
from numo9.tenancy.context import org_context

from .models import (
    Account,
    AccountType,
    Book,
    CloseKind,
    JournalCategory,
    JournalEntry,
    JournalLine,
    JournalType,
    LedgerError,
    PeriodClose,
)
from .periods import ClosedPeriod, register_period_check

ZERO = Decimal("0.00")
LEVELS = (LockLevel.ADVISERS_ONLY, LockLevel.EVERYONE)


class CloseRefused(LedgerError):
    """A close or reopen the rules refuse (``code`` names the rule)."""


def _person(user: Any) -> Any:
    if not getattr(user, "is_authenticated", False):
        raise CloseRefused(
            _("A person must close or reopen a period: it is recorded with their name."),
            code="ledger.close.no_actor",
        )
    return user


def is_month_end(day: dt.date) -> bool:
    return day.day == calendar.monthrange(day.year, day.month)[1]


def _locks(organisation: Any, module: str) -> dict[str, LockDate]:
    rows = LockDate.objects.filter(
        organisation=organisation, module=module, deleted_at__isnull=True
    )
    return {row.level: row for row in rows}


def lock_dates(organisation: Any, module: str) -> dict[str, str | None]:
    found = _locks(organisation, module)
    out: dict[str, str | None] = {}
    for level in LEVELS:
        row = found.get(level)
        out[level] = row.date.isoformat() if row is not None and row.date is not None else None
    return out


def _set_locks(organisation: Any, module: str, dates: dict[str, Any], reason: str) -> None:
    """Set both levels; raising: advisers-only first, lowering: everyone first (the everyone
    date is never later than the advisers-only date)."""
    found = _locks(organisation, module)
    target = {
        level: dt.date.fromisoformat(v) if isinstance(v, str) else v for level, v in dates.items()
    }
    current = {level: (found[level].date if level in found else None) for level in LEVELS}
    raising = (target.get(LockLevel.EVERYONE) or dt.date.min) >= (
        current.get(LockLevel.EVERYONE) or dt.date.min
    )
    order = LEVELS if raising else tuple(reversed(LEVELS))
    for level in order:
        if current.get(level) == target.get(level):
            continue
        row = found.get(level) or LockDate(organisation=organisation, module=module, level=level)
        row.set_lock(target.get(level), reason)
        row.save()


def _open_closes(organisation: Any, module: str) -> Any:
    return PeriodClose.objects.filter(
        organisation=organisation, module=module, reopened_at__isnull=True
    )


def _validate_close(organisation: Any, module: str, period_end: dt.date) -> None:
    if module not in LockModule.values:
        raise CloseRefused(_("Unknown module."), code="ledger.close.module")
    if not is_month_end(period_end):
        raise CloseRefused(
            _("Close a period at the end of a month (%(date)s isn't one).")
            % {"date": period_end.isoformat()},
            code="ledger.close.not_month_end",
        )
    later = _open_closes(organisation, module).filter(period_end__gt=period_end).first()
    if later is not None:
        raise CloseRefused(
            _("%(date)s is already closed: periods close in order.")
            % {"date": later.period_end.isoformat()},
            code="ledger.close.out_of_order",
        )
    everyone = _locks(organisation, module).get(LockLevel.EVERYONE)
    if everyone is not None and everyone.date is not None and everyone.date >= period_end:
        raise CloseRefused(
            _("The period up to %(date)s is already locked.") % {"date": everyone.date.isoformat()},
            code="ledger.close.already_locked",
        )


def _close_row(
    organisation: Any, module: str, period_end: dt.date, person: Any, kind: str, **fields: Any
) -> PeriodClose:
    from numo9.audit.service import record

    previous = lock_dates(organisation, module)
    advisers = previous.get(LockLevel.ADVISERS_ONLY)
    _set_locks(
        organisation,
        module,
        {
            LockLevel.ADVISERS_ONLY: max(period_end, dt.date.fromisoformat(advisers))
            if advisers
            else period_end,
            LockLevel.EVERYONE: period_end,
        },
        _("Period closed to %(date)s.") % {"date": period_end.isoformat()},
    )
    row = PeriodClose(
        organisation=organisation,
        module=module,
        period_end=period_end,
        kind=kind,
        closed_by=person,
        previous_lock=previous,
        **fields,
    )
    row.save()
    record(
        "ledger.period.closed",
        obj=row,
        actor=person,
        meta={
            "module": module,
            "period_end": period_end.isoformat(),
            "kind": kind,
            "previous_lock": previous,
        },
    )
    return row


def close(organisation: Any, module: str, period_end: dt.date, user: Any) -> PeriodClose:
    """Close ``module`` up to ``period_end`` (module docstring)."""
    person = _person(user)
    with org_context(organisation), transaction.atomic():
        _validate_close(organisation, module, period_end)
        return _close_row(organisation, module, period_end, person, CloseKind.MONTH)


# ---- year-end (T04) ----------------------------------------------------------------------------

PL_TYPES = (AccountType.REVENUE, AccountType.EXPENSE)


def fiscal_year_of(organisation: Any, day: dt.date) -> tuple[dt.date, dt.date]:
    from numo9.orgsettings.fiscal import fiscal_year
    from numo9.orgsettings.service import get_settings

    start, end = fiscal_year(get_settings(organisation), day)
    return start, end


def pl_balances(organisation: Any, book: str, start: dt.date, end: dt.date) -> dict[int, Decimal]:
    """Net debit balance (debit − credit) of each revenue / expense account in ``book`` over the
    posted lines dated ``start``…``end``."""
    from .models import LOCKED_STATUSES

    rows = (
        JournalLine.objects.filter(
            organisation=organisation,
            book__in=[Book.BOTH, book],
            entry__status__in=sorted(LOCKED_STATUSES),
            entry__date__gte=start,
            entry__date__lte=end,
            account__type__in=PL_TYPES,
        )
        .values("account_id")
        .annotate(debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO))
        .order_by("account_id")
    )
    return {r["account_id"]: r["debit"] - r["credit"] for r in rows if r["debit"] != r["credit"]}


def net_income(organisation: Any, book: str, start: dt.date, end: dt.date) -> Decimal:
    """Revenue − expenses of the year in ``book`` (a profit is positive)."""
    return -sum(pl_balances(organisation, book, start, end).values(), ZERO)


def _closing_entry(
    organisation: Any, book: str, start: dt.date, fye: dt.date, person: Any
) -> JournalEntry | None:
    from .services import post_journal
    from .validation import JournalSpec, LineSpec

    balances = pl_balances(organisation, book, start, fye)
    if not balances:
        return None
    retained = Account.objects.filter(system_role="retained_earnings").first()
    if retained is None:
        raise CloseRefused(
            _("The chart has no Retained earnings account to close the year to."),
            code="ledger.close.no_retained_earnings",
        )
    lines = []
    for account_id, balance in sorted(balances.items()):
        lines.append(
            LineSpec(
                account=account_id,
                debit=-balance if balance < 0 else ZERO,
                credit=balance if balance > 0 else ZERO,
                book=book,
                description=_("Year-end close"),
            )
        )
    profit = -sum(balances.values(), ZERO)
    lines.append(
        LineSpec(
            account=retained,
            debit=-profit if profit < 0 else ZERO,
            credit=profit if profit > 0 else ZERO,
            book=book,
            description=_("Net income to retained earnings"),
        )
    )
    label = Book(book).label
    return post_journal(
        JournalSpec(
            date=fye,
            lines=lines,
            type=JournalType.ADJUSTMENT,
            journal_type=JournalCategory.CLOSING,
            narration=_("Year-end close %(year)s — %(book)s")
            % {"year": fye.isoformat(), "book": label},
            source_type="ledger.periodclose",
        ),
        organisation=organisation,
        user=person,
        caller="year_end",
    )


def close_year(organisation: Any, fiscal_year_end: dt.date, user: Any) -> PeriodClose:
    """The year-end roll and close (module docstring)."""
    person = _person(user)
    with org_context(organisation), transaction.atomic():
        start, end = fiscal_year_of(organisation, fiscal_year_end)
        if end != fiscal_year_end:
            raise CloseRefused(
                _("%(date)s isn't a fiscal year end (the year ends on %(end)s).")
                % {"date": fiscal_year_end.isoformat(), "end": end.isoformat()},
                code="ledger.close.not_year_end",
            )
        if (
            _open_closes(organisation, LockModule.GL)
            .filter(kind=CloseKind.YEAR_END, period_end=end)
            .exists()
        ):
            raise CloseRefused(
                _("The year ending %(date)s is already closed.") % {"date": end.isoformat()},
                code="ledger.close.year_closed",
            )
        # A December (year-end month) close is folded into the year-end close.
        month = _open_closes(organisation, LockModule.GL).filter(period_end=end).first()
        if month is not None:
            _set_locks(organisation, LockModule.GL, month.previous_lock, _("Year-end close."))
            month.reopened_by, month.reopened_at = person, timezone.now()
            month.reason = _("Replaced by the year-end close.")
            month.save()
        _validate_close(organisation, LockModule.GL, end)
        accounting = _closing_entry(organisation, Book.ACCOUNTING, start, end, person)
        tax = _closing_entry(organisation, Book.TAX, start, end, person)
        row = _close_row(
            organisation,
            LockModule.GL,
            end,
            person,
            CloseKind.YEAR_END,
            accounting_entry=accounting,
            tax_entry=tax,
        )
        if month is not None:
            row.previous_lock = month.previous_lock
            row.save(update_fields=["previous_lock"])
        return row


def year_end_check(organisation: Any, date: dt.date) -> ClosedPeriod | None:
    row = (
        PeriodClose._base_manager.filter(
            organisation=organisation,
            kind=CloseKind.YEAR_END,
            reopened_at__isnull=True,
            period_end__gte=date,
        )
        .order_by("period_end")
        .first()
    )
    if row is None:
        return None
    start, end = fiscal_year_of(organisation, row.period_end)
    if not start <= date <= end:
        return None
    return ClosedPeriod(start, end, _("Fiscal year ending %(date)s") % {"date": end.isoformat()})


register_period_check(year_end_check)


# ---- reopen (T05) ------------------------------------------------------------------------------


def reopen(
    period_close: PeriodClose, user: Any, reason: str, *, force: bool = False
) -> PeriodClose:
    """Reopen a close (module docstring)."""
    from numo9.audit.service import record

    from .services import reverse

    person = _person(user)
    organisation = period_close.organisation
    reason = (reason or "").strip()
    with org_context(organisation), transaction.atomic():
        row: PeriodClose = PeriodClose.objects.select_for_update().get(pk=period_close.pk)
        if not is_adviser(person, organisation):
            raise CloseRefused(
                _("Only an adviser (the organisation's accountant) can reopen a closed period."),
                code="ledger.close.adviser_only",
            )
        if not reason:
            raise CloseRefused(
                _("Say why the period is reopened."), code="ledger.close.reason_required"
            )
        if not row.is_open:
            raise CloseRefused(_("This period is already open."), code="ledger.close.not_closed")
        others = _open_closes(organisation, row.module).exclude(pk=row.pk)
        later = others.filter(period_end__gt=row.period_end).order_by("-period_end").first()
        if later is not None and not force:
            raise CloseRefused(
                _("Reopen %(date)s first: the latest close is reopened first.")
                % {"date": later.period_end.isoformat()},
                code="ledger.close.not_latest",
            )
        row.reopened_by, row.reopened_at, row.reason = person, timezone.now(), reason
        row.save()
        remaining = others.order_by("-period_end").first()
        if later is not None and remaining is not None:
            target = dict.fromkeys(LEVELS, remaining.period_end)
        else:
            target = dict(row.previous_lock or {})
            for level in LEVELS:
                target.setdefault(level, None)
        _set_locks(organisation, row.module, target, reason)
        reversed_ids = []
        for entry in (row.accounting_entry, row.tax_entry):
            if entry is not None:
                undone = reverse(
                    entry,
                    narration=_("Year-end close reopened: %(reason)s") % {"reason": reason},
                    user=person,
                )
                reversed_ids.append(str(undone.public_id))
        record(
            "ledger.period.reopened",
            obj=row,
            actor=person,
            meta={
                "module": row.module,
                "period_end": row.period_end.isoformat(),
                "reason": reason,
                "forced": bool(later is not None and force),
                "reversals": reversed_ids,
            },
        )
        return row


# ---- checklist (T03) ---------------------------------------------------------------------------


def _month_start(period_end: dt.date) -> dt.date:
    return period_end.replace(day=1)


def checklist(
    organisation: Any, period_end: dt.date, start: dt.date | None = None
) -> list[dict[str, Any]]:
    """What is still open in ``start``…``period_end`` (the month by default) before closing it
    (C-06-T03): each item ``{key, label, count, link, blocking}`` —

    - ``drafts`` — journals, invoices, credit notes, bills, supplier credits and expense claims
      still in draft, dated in the period;
    - ``awaiting_approval`` — journals, invoices, credit notes, bills awaiting approval and
      expense claims submitted, dated in the period;
    - ``unfiled_tax`` — GST/HST and QST filing periods ended by the period end and not filed;
    - ``exceptions`` — recurring journals skipped and automatic reversals not posted, dated in
      the period (a locked or closed date, an approval missing…).

    Counts are information: the close isn't refused because of them (the screen links each to
    the list that fixes it).
    """
    from numo9.purchases.models import Bill, ExpenseClaim, SupplierCredit
    from numo9.sales.models import CreditNote, Invoice
    from numo9.tax.models import LOCKED_PERIOD_STATUSES, FilingPeriod

    from .models import JournalStatus, RecurringJournalRun, RecurringRunStatus

    start = start or _month_start(period_end)
    base = f"/o/{organisation.public_id}"
    span = f"from={start.isoformat()}&to={period_end.isoformat()}"
    dated = Q(date__gte=start, date__lte=period_end)
    live = Q(deleted_at__isnull=True)

    def count(model: Any, *filters: Q) -> int:
        query = model.objects.filter(organisation=organisation)
        for f in filters:
            query = query.filter(f)
        return int(query.count())

    claims_dated = Q(lines__date__gte=start, lines__date__lte=period_end)
    drafts = {
        "journals": count(JournalEntry, dated, Q(status=JournalStatus.DRAFT)),
        "invoices": count(Invoice, dated, live, Q(status="draft")),
        "credit_notes": count(CreditNote, dated, live, Q(status="draft")),
        "bills": count(Bill, dated, live, Q(status="draft")),
        "supplier_credits": count(SupplierCredit, dated, live, Q(status="draft")),
        "expense_claims": ExpenseClaim.objects.filter(
            organisation=organisation, status="draft", deleted_at__isnull=True
        )
        .filter(claims_dated)
        .distinct()
        .count(),
    }
    waiting = {
        "journals": count(JournalEntry, dated, Q(status=JournalStatus.AWAITING_APPROVAL)),
        "invoices": count(Invoice, dated, live, Q(status="awaiting_approval")),
        "credit_notes": count(CreditNote, dated, live, Q(status="awaiting_approval")),
        "bills": count(Bill, dated, live, Q(status="awaiting_approval")),
        "expense_claims": ExpenseClaim.objects.filter(
            organisation=organisation, status="submitted", deleted_at__isnull=True
        )
        .filter(claims_dated)
        .distinct()
        .count(),
    }
    unfiled = list(
        FilingPeriod.objects.filter(organisation=organisation, end__lte=period_end)
        .exclude(status__in=LOCKED_PERIOD_STATUSES)
        .select_related("registration")
        .order_by("end")
    )
    skipped = RecurringJournalRun.objects.filter(
        organisation=organisation,
        status=RecurringRunStatus.SKIPPED,
        occurrence_date__gte=start,
        occurrence_date__lte=period_end,
    ).count()
    stuck = JournalEntry.objects.filter(
        organisation=organisation,
        status=JournalStatus.POSTED,
        auto_reverse_on__gte=start,
        auto_reverse_on__lte=period_end,
        auto_reverse_on__lt=timezone.localdate(),
    ).count()
    tax_link = (
        f"{base}/settings/tax/registrations/{unfiled[0].registration.public_id}/filing"
        if unfiled
        else f"{base}/settings/tax"
    )
    return [
        {
            "key": "drafts",
            "label": _("Drafts dated in the period"),
            "count": sum(drafts.values()),
            "detail": drafts,
            "link": f"{base}/accounting/journals?status=draft&{span}",
        },
        {
            "key": "awaiting_approval",
            "label": _("Waiting for approval"),
            "count": sum(waiting.values()),
            "detail": waiting,
            "link": f"{base}/approvals",
        },
        {
            "key": "unfiled_tax",
            "label": _("Tax periods ended and not filed"),
            "count": len(unfiled),
            "detail": {
                "periods": [
                    {
                        "registration": str(p.registration),
                        "start": p.start.isoformat(),
                        "end": p.end.isoformat(),
                    }
                    for p in unfiled
                ]
            },
            "link": tax_link,
        },
        {
            "key": "exceptions",
            "label": _("Recurring journals skipped and automatic reversals not posted"),
            "count": skipped + stuck,
            "detail": {"recurring_skipped": skipped, "reversals_pending": stuck},
            "link": f"{base}/accounting/journals/recurring",
        },
    ]
