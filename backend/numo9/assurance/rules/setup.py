"""Set-up rules (K-09-T14): GIFI mapping, Business Number, lock date, conversion balances.

These are organisation-level checks (no incremental runs): nightly and on demand.

**UNBALANCED_CONVERSION** reads the conversion through ``conversion_state(organisation)``: the
first registered ``CONVERSION_PROBES`` answer wins — the C-05-T14 "opening equity missing" hook
registers there when it lands — else the state is computed from ``numo9.conversion``'s models
(the session and its lines: totals, difference, equity lines).
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from numo9.ledger.models import Account, AccountStatus, AccountType, JournalLine

from ..models import Severity
from .base import Context, Hit, Param, Rule, register
from .common import LEDGER_STATUSES, ZERO

ORG = "tenancy.Organisation"


def _org_hit(ctx: Context, amount: Decimal | None = None, **details: Any) -> Hit:
    organisation = ctx.organisation
    return Hit(ORG, str(organisation.public_id), organisation.name, amount, details)


@register
class UnmappedGifi(Rule):
    code = "UNMAPPED_GIFI"
    name = gettext_lazy("Accounts not mapped to GIFI")
    description = gettext_lazy(
        "Active accounts without a GIFI code: the T2 financial statements can't be prepared "
        "from the ledger as it is."
    )
    explanation = gettext_lazy(
        "%(unmapped)s of %(total)s active accounts have no GIFI code (%(sample)s…). Map them in "
        "the chart of accounts so the T2 schedules 100 and 125 can be prepared."
    )
    default_severity = Severity.WARNING
    params = {"only_with_activity": Param("bool", False, gettext_lazy("Only accounts used"))}

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        active = Account.objects.filter(status=AccountStatus.ACTIVE, deleted_at__isnull=True)
        unmapped = active.filter(gifi__isnull=True)
        if ctx.params["only_with_activity"]:
            used = JournalLine.objects.filter(entry__status__in=LEDGER_STATUSES).values(
                "account_id"
            )
            unmapped = unmapped.filter(pk__in=used)
        codes = list(unmapped.order_by("code").values_list("code", flat=True))
        if not codes:
            return
        yield _org_hit(
            ctx,
            None,
            unmapped=len(codes),
            total=active.count(),
            accounts=codes[:200],
            sample=", ".join(codes[:5]),
        )


@register
class MissingBn(Rule):
    code = "MISSING_BN"
    name = gettext_lazy("Registered without a Business Number")
    description = gettext_lazy(
        "The organisation has a CRA or Revenu Québec registration but no Business Number on file."
    )
    explanation = gettext_lazy(
        "The organisation is registered (%(registrations)s) but has no Business Number (BN). "
        "Add it under Tax registrations: it is printed on invoices and needed for every return."
    )
    default_severity = Severity.CRITICAL

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        from numo9.orgsettings.models import RegistrationStatus, RegistrationType, TaxRegistration

        rows = TaxRegistration.objects.exclude(status=RegistrationStatus.CLOSED)
        types = set(rows.values_list("type", flat=True))
        programs = types & {
            RegistrationType.RT,
            RegistrationType.QST,
            RegistrationType.RP,
            RegistrationType.RC,
        }
        if not programs or RegistrationType.BN in types:
            return
        labels = sorted(str(RegistrationType(t).label) for t in programs)
        yield _org_hit(ctx, None, registrations=", ".join(labels), types=sorted(programs))


def month_end(day: dt.date) -> dt.date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def closed_period_end(today: dt.date, days: int) -> dt.date:
    """The last month-end at least ``days`` days ago."""
    cutoff = today - dt.timedelta(days=days)
    end = month_end(cutoff)
    return end if end <= cutoff else cutoff.replace(day=1) - dt.timedelta(days=1)


@register
class MissingLockDate(Rule):
    code = "MISSING_LOCK_DATE"
    name = gettext_lazy("No lock date")
    description = gettext_lazy(
        "Periods that ended long ago are still open: anyone can still change them."
    )
    explanation = gettext_lazy(
        "The books have activity up to %(period_end)s, a period that ended more than %(days)s "
        "days ago, and the general ledger lock date is %(lock)s. Set the lock date to "
        "%(period_end)s so reported periods can't change."
    )
    default_severity = Severity.WARNING
    date_keys = ("period_end",)
    params = {"days": Param("int", 30, gettext_lazy("Days"), minimum=1, maximum=365)}

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        from numo9.ledger.models import JournalEntry
        from numo9.orgsettings.models import LockDate, LockModule

        period_end = closed_period_end(ctx.today, ctx.params["days"])
        dates = LockDate.objects.filter(
            module=LockModule.GL, deleted_at__isnull=True, date__isnull=False
        ).values_list("date", flat=True)
        lock = max(dates, default=None)
        if lock is not None and lock >= period_end:
            return
        if not JournalEntry.objects.filter(
            status__in=LEDGER_STATUSES, date__lte=period_end
        ).exists():
            return
        yield _org_hit(
            ctx,
            None,
            period_end=period_end.isoformat(),
            days=ctx.params["days"],
            lock=lock.isoformat() if lock else "",
        )

    def display(self, details: Any) -> dict[str, Any]:
        from numo9.ledger.cash_guard import format_day

        shown = super().display(details)
        lock = details.get("lock")
        shown["lock"] = format_day(dt.date.fromisoformat(lock)) if lock else _("not set")
        return shown


# ---- conversion balances (C-05) ------------------------------------------------------------


@dataclass(frozen=True)
class ConversionState:
    """What the engine needs to know about the organisation's conversion."""

    session_id: str
    conversion_date: dt.date
    lines: int
    debit: Decimal
    credit: Decimal
    has_equity: bool

    @property
    def difference(self) -> Decimal:
        return self.debit - self.credit


#: ``probe(organisation) -> ConversionState | None``; the C-05-T14 hook registers here.
CONVERSION_PROBES: list[Callable[[Any], ConversionState | None]] = []


def _from_models(organisation: Any) -> ConversionState | None:
    from numo9.conversion.models import ConversionLine, ConversionSession

    session = ConversionSession.objects.filter(deleted_at__isnull=True).first()
    if session is None:
        return None
    lines = ConversionLine.objects.filter(session=session, deleted_at__isnull=True)
    totals = lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    return ConversionState(
        str(session.public_id),
        session.conversion_date,
        lines.count(),
        totals["debit"] or ZERO,
        totals["credit"] or ZERO,
        lines.filter(account__type=AccountType.EQUITY).exists(),
    )


def conversion_state(organisation: Any) -> ConversionState | None:
    for probe in CONVERSION_PROBES:
        found = probe(organisation)
        if found is not None:
            return found
    return _from_models(organisation)


@register
class UnbalancedConversion(Rule):
    code = "UNBALANCED_CONVERSION"
    name = gettext_lazy("Conversion balances incomplete or unbalanced")
    description = gettext_lazy(
        "The opening balances brought over from the previous system are empty, don't balance or "
        "have no equity."
    )
    explanation = gettext_lazy(
        "The conversion at %(conversion_date)s: %(problem)s. Opening balances are where the "
        "balance sheet starts — debits %(debit)s, credits %(credit)s."
    )
    default_severity = Severity.CRITICAL
    money_keys = ("debit", "credit", "difference")
    date_keys = ("conversion_date",)

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        state = conversion_state(ctx.organisation)
        if state is None:
            return
        problems: list[str] = []
        if state.lines == 0:
            problems.append("empty")
        if state.difference != 0:
            problems.append("unbalanced")
        if not state.has_equity:
            problems.append("no_equity")
        if not problems:
            return
        yield Hit(
            "conversion.ConversionSession",
            state.session_id,
            str(_("Conversion at %(date)s") % {"date": state.conversion_date.isoformat()}),
            state.difference,
            {
                "conversion_date": state.conversion_date.isoformat(),
                "problems": problems,
                "lines": state.lines,
                "debit": f"{state.debit:.2f}",
                "credit": f"{state.credit:.2f}",
                "difference": f"{state.difference:.2f}",
            },
        )

    def display(self, details: Any) -> dict[str, Any]:
        shown = super().display(details)
        texts = {
            "empty": _("no opening balances were entered"),
            "unbalanced": _("debits and credits differ by %(difference)s")
            % {"difference": shown.get("difference", "")},
            "no_equity": _(
                "there is no equity (share capital, shareholder loan, retained earnings)"
            ),
        }
        shown["problem"] = "; ".join(texts[p] for p in details.get("problems", []) if p in texts)
        return shown
