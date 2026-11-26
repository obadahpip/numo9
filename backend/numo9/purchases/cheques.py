"""Cheque numbering per bank account and the cheque register (E-06-T06).

**Numbering.** Each bank account has its own cheque stock and so its own sequence
(``ChequeSequence``): ``allocate_number(bank_account)`` locks the sequence row
(``SELECT … FOR UPDATE``), skips any number already in the register (a cheque entered by hand)
and moves the sequence on, in the caller's transaction — unique (the database's unique
constraint per bank account backs it) and gap-free when the caller rolls back.
``set_next_number(bank_account, n)`` starts a new cheque book at ``n``; a number already used is
refused (``purchases.cheque.number_used``).

**Issue.** ``issue(bank_account, payee, amount, date, payments=…, batch=…)`` numbers a cheque for
a payee and links the bill payments it pays (their ``reference`` becomes the cheque number).

**Register statuses** (``ChequeStatus``) and the moves ``change_status`` allows:

- Issued → Printed (the print run, E-06-T07) → Cleared (``cleared_on``: the bank paid it);
- Issued / Printed → Stale-dated (not cleared after the organisation's days, default 180; the
  job is E-06-T09) → Cleared (a late deposit) or Void;
- Issued / Printed / Stale-dated → **Void** — a reason is required and audited. A cheque whose
  bill payments are already **posted** is voided by the void-and-reverse flow (E-06-T08), which
  reverses them; here it is refused (``purchases.cheque.void_posted``) so a void never leaves a
  payment standing.

Every change is audited (``purchases.cheque.<status>``).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError
from numo9.tenancy.context import org_context

from .models import BillPayment, BillPaymentStatus, Cheque, ChequeSequence, ChequeStatus

S = ChequeStatus
#: status → the statuses a cheque in it may move to.
MOVES: dict[str, frozenset[str]] = {
    S.ISSUED: frozenset({S.PRINTED, S.VOID, S.STALE}),
    S.PRINTED: frozenset({S.CLEARED, S.VOID, S.STALE}),
    S.STALE: frozenset({S.CLEARED, S.VOID}),
    S.CLEARED: frozenset(),
    S.VOID: frozenset(),
}
DEFAULT_STALE_DAYS = 180


class ChequeRefused(LedgerError):
    """A cheque action the rules refuse (``code`` names the rule)."""


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _sequence(bank_account: Any) -> ChequeSequence:
    found = ChequeSequence._base_manager.select_for_update().filter(bank_account=bank_account)
    row = found.first()
    if row is None:
        ChequeSequence._base_manager.get_or_create(
            organisation=bank_account.organisation, bank_account=bank_account
        )
        row = found.get()
    return row


def next_number(bank_account: Any) -> int:
    """The number the next cheque of ``bank_account`` will get (nothing is taken)."""
    row = ChequeSequence._base_manager.filter(bank_account=bank_account).first()
    start = row.next_number if row else 1
    used = set(
        Cheque._base_manager.filter(bank_account=bank_account, number__gte=start).values_list(
            "number", flat=True
        )
    )
    while start in used:
        start += 1
    return start


def allocate_number(bank_account: Any) -> int:
    """Take the next cheque number of ``bank_account`` (module docstring)."""
    with transaction.atomic():
        row = _sequence(bank_account)
        number = row.next_number
        used = set(
            Cheque._base_manager.filter(bank_account=bank_account, number__gte=number).values_list(
                "number", flat=True
            )
        )
        while number in used:
            number += 1
        ChequeSequence._base_manager.filter(pk=row.pk).update(next_number=number + 1)
        return number


def set_next_number(bank_account: Any, number: int, user: Any = None) -> ChequeSequence:
    """Start the next cheque book of ``bank_account`` at ``number`` (refused if already used)."""
    from numo9.audit import service as audit

    if not 1 <= int(number) <= 99999999:
        raise ChequeRefused(
            _("A cheque number is from 1 to 99999999."), code="purchases.cheque.number_range"
        )
    with org_context(bank_account.organisation), transaction.atomic():
        if Cheque._base_manager.filter(bank_account=bank_account, number=number).exists():
            raise ChequeRefused(
                _("Cheque %(number)s was already used on %(account)s."),
                code="purchases.cheque.number_used",
                params={"number": f"{number:06d}", "account": str(bank_account)},
            )
        row = _sequence(bank_account)
        before = row.next_number
        row.next_number = int(number)
        row.save(update_fields=["next_number"])
        audit.record(
            "purchases.cheque.numbering_changed",
            obj=bank_account,
            changes={"next_cheque_number": [before, row.next_number]},
            actor=_person(user),
        )
        return row


def highest_number(bank_account: Any) -> int | None:
    value = Cheque._base_manager.filter(bank_account=bank_account).aggregate(n=Max("number"))["n"]
    return int(value) if value is not None else None


def issue(
    bank_account: Any,
    payee: Any,
    amount: Decimal,
    date: dt.date,
    *,
    payments: Iterable[BillPayment] = (),
    batch: Any = None,
    memo: str = "",
    user: Any = None,
    reissue_of: Cheque | None = None,
) -> Cheque:
    """Number and record a cheque to ``payee``; ``payments`` (of that payee, not void) are linked
    and take the cheque number as their reference."""
    from numo9.audit import service as audit

    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= 0:
        raise ChequeRefused(
            _("A cheque is for more than zero."), code="purchases.cheque.amount_positive"
        )
    rows = list(payments)
    for row in rows:
        if row.contact_id != payee.pk or row.status == BillPaymentStatus.VOID:
            raise ChequeRefused(
                _("A cheque pays bills of its payee only."), code="purchases.cheque.payee_mismatch"
            )
    with org_context(bank_account.organisation), transaction.atomic():
        cheque = Cheque(
            organisation=bank_account.organisation,
            bank_account=bank_account,
            number=allocate_number(bank_account),
            batch=batch,
            payee=payee,
            payee_name=(payee.legal_name or payee.display_name)[:200],
            date=date,
            amount=amount,
            currency=getattr(bank_account, "currency", "CAD") or "CAD",
            memo=memo[:200],
            reissue_of=reissue_of,
            created_by=_person(user),
        )
        cheque.save()
        for row in rows:
            BillPayment._base_manager.filter(pk=row.pk).update(cheque=cheque, reference=str(cheque))
        audit.record(
            "purchases.cheque.issued",
            obj=cheque,
            meta={"number": str(cheque), "amount": f"{amount:.2f}", "payee": cheque.payee_name},
            actor=_person(user),
        )
        return cheque


def change_status(
    cheque: Cheque,
    status: str,
    user: Any = None,
    *,
    reason: str = "",
    cleared_on: dt.date | None = None,
) -> Cheque:
    """Move a cheque in the register (module docstring); refused moves name the rule."""
    from numo9.audit import service as audit

    reason = " ".join((reason or "").split())
    with org_context(cheque.organisation), transaction.atomic():
        locked = Cheque._base_manager.select_for_update().get(pk=cheque.pk)
        if status not in MOVES.get(locked.status, frozenset()):
            raise ChequeRefused(
                _("Cheque %(number)s is %(status)s: it can't become %(target)s."),
                code="purchases.cheque.bad_move",
                params={
                    "number": str(locked),
                    "status": str(ChequeStatus(locked.status).label).lower(),
                    "target": str(ChequeStatus(status).label).lower(),
                },
            )
        now = timezone.now()
        if status == S.VOID:
            if not reason:
                raise ChequeRefused(
                    _("Say why the cheque is voided."), code="purchases.cheque.reason_required"
                )
            if locked.payments.filter(status=BillPaymentStatus.POSTED).exists():
                raise ChequeRefused(
                    _(
                        "Cheque %(number)s pays posted bill payments: void it with its payments "
                        "so they are reversed."
                    ),
                    code="purchases.cheque.void_posted",
                    params={"number": str(locked)},
                )
            locked.voided_at, locked.void_reason = now, reason[:500]
            BillPayment._base_manager.filter(cheque=locked).update(cheque=None, reference="")
        elif status == S.PRINTED:
            locked.printed_at = now
        elif status == S.CLEARED:
            locked.cleared_on = cleared_on or timezone.localdate()
        elif status == S.STALE:
            locked.stale_at = now
        previous = locked.status
        locked.status = status
        locked.save()
        audit.record(
            f"purchases.cheque.{status}",
            obj=locked,
            changes={"status": [previous, status]},
            meta={"number": str(locked), "reason": reason} if reason else {"number": str(locked)},
            actor=_person(user),
        )
        return locked


def is_stale(cheque: Cheque, today: dt.date, days: int = DEFAULT_STALE_DAYS) -> bool:
    """Issued or printed and still not cleared ``days`` after its date (the E-06-T09 rule)."""
    return cheque.status in (S.ISSUED, S.PRINTED) and (today - cheque.date).days > days
