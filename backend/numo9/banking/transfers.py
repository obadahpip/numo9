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
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError

from .models import BankAccount

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
