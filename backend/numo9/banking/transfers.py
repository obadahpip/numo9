"""Transfers between bank accounts (F-06).

**Rules** (F-06-T02) — ``check_transfer(from_account, to_account, amount)`` raises a
``LedgerError`` with a stable code, the first broken rule:

=====================================  ==========================================================
code                                   when
=====================================  ==========================================================
``banking.transfer.account_required``  the from or the to account is missing
``banking.transfer.same_account``      from and to are the same account
``banking.transfer.amount_positive``   the amount is 0.00 or less (or has more than 2 decimals:
                                       ``banking.amount.precision``)
``banking.account.archived``           either account is archived or deleted
``banking.transfer.cross_currency``    the accounts hold different currencies — deferred to
                                       multi-currency (R-02), said so in the message
=====================================  ==========================================================

Any two bank-account types may be paired: chequing → petty cash (fund the float), chequing →
credit card (pay the card), loan → chequing (a draw)…

**Posting** (F-06-T03) — ``record_transfer(...)`` writes the ``BankTransfer`` and posts, in the
same transaction, **one** journal through the posting service (C-02): type ``transfer``, lock
module Bank, ``source_type`` ``banking.banktransfer`` / ``source_id`` the transfer's public id,
two lines:

=====================================  ===========
Dr the to-account's ledger account     amount
Cr the from-account's ledger account   amount
=====================================  ===========

so the movement across both accounts nets to zero. The cash rules apply as on any posting (the
from-account going below zero: C-03, F-07). ``void_transfer`` reverses the journal (both sides,
``reverse``) and marks the transfer Voided; voiding twice is refused.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.ledger.models import JournalType, LedgerError
from numo9.ledger.services import ACTING, post_journal, reverse
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import org_context

from .models import BankAccount, BankTransfer, BankTransferStatus

SOURCE_TYPE = "banking.banktransfer"

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def transfer_amount(value: Any) -> Decimal:
    """The amount as a 2-decimal ``Decimal`` above zero, or ``LedgerError``."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        amount = ZERO
    if amount != amount.quantize(CENT):
        raise LedgerError(
            _("Amounts have at most 2 decimals: %(amount)s."),
            code="banking.amount.precision",
            params={"amount": str(value)},
        )
    if amount <= ZERO:
        raise LedgerError(
            _("The amount to transfer must be more than 0.00."),
            code="banking.transfer.amount_positive",
        )
    return amount.quantize(CENT)


def _active(bank: BankAccount) -> None:
    if bank.archived_at is not None or bank.deleted_at is not None:
        raise LedgerError(
            _("%(name)s is archived: restore it or choose another account."),
            code="banking.account.archived",
            params={"name": bank.display_name},
        )


def check_transfer(
    from_account: BankAccount | None, to_account: BankAccount | None, amount: Any
) -> Decimal:
    """Every rule of a transfer (module docstring); returns the amount, quantised."""
    if from_account is None or to_account is None:
        raise LedgerError(
            _("Choose the account the money leaves and the account it goes to."),
            code="banking.transfer.account_required",
        )
    if from_account.pk == to_account.pk:
        raise LedgerError(
            _("Choose two different accounts: money can't be transferred to the same account."),
            code="banking.transfer.same_account",
        )
    value = transfer_amount(amount)
    _active(from_account)
    _active(to_account)
    if from_account.currency.upper() != to_account.currency.upper():
        raise LedgerError(
            _(
                "%(from)s is in %(from_currency)s and %(to)s in %(to_currency)s: transfers "
                "between currencies arrive with multi-currency (R-02). For now, record them as "
                "a spend from one account and a receipt into the other."
            ),
            code="banking.transfer.cross_currency",
            params={
                "from": from_account.display_name,
                "from_currency": from_account.currency.upper(),
                "to": to_account.display_name,
                "to_currency": to_account.currency.upper(),
            },
        )
    return value


def transfer_lines(transfer: BankTransfer) -> list[LineSpec]:
    """Dr to / Cr from, the amount (module docstring)."""
    reference = transfer.reference
    return [
        LineSpec(transfer.to_account.gl_account, debit=transfer.amount, description=reference),
        LineSpec(transfer.from_account.gl_account, credit=transfer.amount, description=reference),
    ]


def _narration(transfer: BankTransfer) -> str:
    text = _("Transfer from %(from)s to %(to)s") % {
        "from": transfer.from_account.display_name,
        "to": transfer.to_account.display_name,
    }
    return f"{text}: {transfer.reference}" if transfer.reference else text


def record_transfer(
    from_account: BankAccount,
    to_account: BankAccount,
    *,
    date: dt.date,
    amount: Any,
    reference: str = "",
    user: Any = ACTING,
    override_reason: str = "",
) -> BankTransfer:
    """Write and post a transfer (module docstring) — all or nothing."""
    organisation = from_account.organisation
    if to_account.organisation_id != from_account.organisation_id:
        raise LedgerError(
            _("Both accounts must belong to the organisation."),
            code="banking.transfer.account_required",
        )
    with org_context(organisation), transaction.atomic():
        value = check_transfer(from_account, to_account, amount)
        person = None if user is ACTING else user
        by = person if getattr(person, "is_authenticated", False) else None
        transfer = BankTransfer(
            organisation=organisation,
            from_account=from_account,
            to_account=to_account,
            date=date,
            amount=value,
            currency=from_account.currency.upper(),
            reference=" ".join((reference or "").split())[:255],
            created_by=by,
        )
        transfer.save()
        entry = post_journal(
            JournalSpec(
                date=date,
                lines=transfer_lines(transfer),
                type=JournalType.TRANSFER,
                narration=_narration(transfer),
                source_type=SOURCE_TYPE,
                source_id=str(transfer.public_id),
            ),
            organisation=organisation,
            user=user,
            module=LockModule.BANK,
            override_reason=override_reason,
        )
        transfer.journal_entry = entry
        transfer.save(update_fields=["journal_entry", "updated_at"])
        return transfer


def void_transfer(
    transfer: BankTransfer, *, date: dt.date | None = None, user: Any = ACTING
) -> BankTransfer:
    """Void: reverse the journal (both sides at once) and mark the transfer Voided."""
    with org_context(transfer.organisation), transaction.atomic():
        locked = BankTransfer._base_manager.select_for_update().get(pk=transfer.pk)
        if locked.status == BankTransferStatus.VOIDED:
            raise LedgerError(_("This transfer is already voided."), code="banking.transfer.voided")
        if locked.journal_entry is not None:
            reverse(
                locked.journal_entry,
                date=date or locked.date,
                narration=_("Void: %(label)s") % {"label": _narration(locked)},
                user=user,
                module=LockModule.BANK,
            )
        locked.status = BankTransferStatus.VOIDED
        locked.voided_at = timezone.now()
        locked.save(update_fields=["status", "voided_at", "updated_at"])
        return locked
