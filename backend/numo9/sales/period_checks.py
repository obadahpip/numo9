"""Lock and period checks at approve and void (D-03a-T04).

Before an invoice takes its number or a void posts its reversal, ``assert_postable(invoice,
lines, date, user, action)`` refuses — with a message naming the invoice, its date and what stops
it — a date that is:

- on or before the **Sales and accounts receivable** lock date (or the general ledger's): code
  ``sales.invoice.locked``, the lock (module, level, date) in the params — "INV-0007 can't be
  approved: it is dated 15 Mar 2026, on or before the Sales and accounts receivable lock date
  (31 Mar 2026, everyone). …";
- in a **filed GST/HST (or QST) period** when the journal carries tax (a tax code, or a line on
  a sales-tax control account): code ``sales.invoice.filed_period`` — "… it is dated 15 Mar 2026,
  in the GST/HST period 1 Jan 2026 – 31 Mar 2026, filed (confirmation GH-2026-0001). …"; on or
  before another Tax lock date: ``sales.invoice.tax_locked``. Inside ``late_adjustments()`` the
  document posts knowingly (its tax goes to the next open return, G-03-T08).

The posting engine applies the same rules again (C-02 lock dates, the Tax lock guard G-03-T07):
this check runs first so the refusal names the invoice and nothing — not even a number — is used.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.utils import translation
from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError
from numo9.orgsettings.locks import check_lock
from numo9.orgsettings.models import LockLevel, LockModule

ZERO = Decimal("0.00")

#: The registrations whose filed periods a document's tax can't land in.
TAX_ROLES = ("rt", "qst")


class PeriodRefused(LedgerError):
    """An approve or void dated where a lock or a filed tax period refuses it."""


def _label(document: Any) -> str:
    return document.number or str(document)


def _verb(action: str) -> str:
    if action == "revise":
        return _("revised")
    return _("approved") if action == "approve" else _("voided")


def _touches_tax(lines: list[Any]) -> bool:
    """Does the journal carry a tax code or post to a sales-tax control account? (What the Tax
    lock guard of the posting engine refuses, G-03-T07.)"""
    from numo9.tax.returns import TAX_ROLES as CONTROL_ROLES

    return any(
        getattr(line, "tax_code", "")
        or (getattr(line.account, "system_role", "") or "") in CONTROL_ROLES
        for line in lines
    )


def _late() -> bool:
    """Inside ``late_adjustments()``: the document is posted knowingly into a filed period."""
    from numo9.tax.returns import _late_flag

    return bool(_late_flag().get())


def assert_postable(
    document: Any, lines: Iterable[Any], date: dt.date, user: Any, action: str = "approve"
) -> None:
    """Refuse a date the AR lock or a filed tax period stops (module docstring)."""
    from numo9.documents.formatting import format_date
    from numo9.tax.returns import _filed_period

    organisation = document.organisation
    locale = (translation.get_language() or "en-ca").lower()

    def shown(value: dt.date) -> str:
        return format_date(value, locale)

    violation = check_lock(organisation, LockModule.AR, date, user)
    if violation is not None:
        raise PeriodRefused(
            _(
                "%(document)s can't be %(action)s: it is dated %(date)s, on or before the "
                "%(module)s lock date (%(lock)s, %(level)s). Date it after %(lock)s, or ask "
                "someone who manages lock dates."
            )
            % {
                "document": _label(document),
                "action": _verb(action),
                "date": shown(date),
                "module": LockModule(violation.module).label,
                "lock": shown(violation.date),
                "level": str(LockLevel(violation.level).label).lower(),
            },
            code="sales.invoice.locked",
            params={"lock": violation.as_dict()},
        )
    lines = list(lines)
    if not _touches_tax(lines) or _late():
        return
    tax_lock = check_lock(organisation, LockModule.TAX, date, user)
    if tax_lock is None:
        return
    for kind in TAX_ROLES:
        period = _filed_period(organisation, kind, date)
        if period is None:
            continue
        filed = period.returns.filter(status="filed").order_by("-version").first()
        raise PeriodRefused(
            _(
                "%(document)s can't be %(action)s: it is dated %(date)s, in the %(registration)s "
                "period %(start)s – %(end)s, filed (confirmation %(number)s). Date it in an open "
                "period: the tax of a filed period changes only by a late adjustment or an "
                "amended return."
            )
            % {
                "document": _label(document),
                "action": _verb(action),
                "date": shown(date),
                "registration": _("GST/HST") if kind == "rt" else _("QST"),
                "start": shown(period.start),
                "end": shown(period.end),
                "number": getattr(filed, "confirmation_no", "") or "—",
            },
            code="sales.invoice.filed_period",
            params={
                "period": {
                    "id": str(period.public_id),
                    "start": period.start.isoformat(),
                    "end": period.end.isoformat(),
                },
            },
        )
    raise PeriodRefused(
        _(
            "%(document)s can't be %(action)s: it is dated %(date)s, on or before the "
            "%(module)s lock date (%(lock)s, %(level)s). Date it after %(lock)s, or ask "
            "someone who manages lock dates."
        )
        % {
            "document": _label(document),
            "action": _verb(action),
            "date": shown(date),
            "module": LockModule(tax_lock.module).label,
            "lock": shown(tax_lock.date),
            "level": str(LockLevel(tax_lock.level).label).lower(),
        },
        code="sales.invoice.tax_locked",
        params={"lock": tax_lock.as_dict()},
    )
