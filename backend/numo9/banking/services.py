"""Bank account creation (F-01-T03): the type decides the ledger account.

``create_bank_account(organisation, type=…, display_name=…)`` creates, in one transaction, the
ledger account and its ``BankAccount`` profile — usable straight away:

==================  ==========================  ============  ========
type                ledger type / sub-type      code range    bank
==================  ==========================  ============  ========
Chequing, Savings,  asset / Bank                1000–1099     yes
Cash, Clearing      (current assets)
Credit card,        liability / Current         2100–2199     yes
Line of credit      liability
Loan                liability / Non-current     2700–2799     yes
                    liability (``loan_current``
                    → Current liability, 21xx)
==================  ==========================  ============  ========

The ledger account takes the lowest free 4-digit code of the range (codes of every account,
archived ones too, are taken) and the bank account's name; a full range raises
``ledger.bank.no_free_code``, a name already used ``banking.account.name_taken``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from numo9.ledger.models import SUBTYPE_TYPE, Account, AccountSubtype, LedgerError
from numo9.orgsettings.locks import acting_user
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import BankAccount, BankAccountType

T = BankAccountType


@dataclass(frozen=True)
class LedgerPlace:
    subtype: str
    first: int
    last: int


ASSET = LedgerPlace(AccountSubtype.BANK, 1000, 1099)
CURRENT_LIABILITY = LedgerPlace(AccountSubtype.CURRENT_LIABILITY, 2100, 2199)
LONG_TERM_LIABILITY = LedgerPlace(AccountSubtype.NON_CURRENT_LIABILITY, 2700, 2799)

PLACES: dict[str, LedgerPlace] = {
    T.CHEQUING: ASSET,
    T.SAVINGS: ASSET,
    T.CASH: ASSET,
    T.CLEARING: ASSET,
    T.CREDIT_CARD: CURRENT_LIABILITY,
    T.LINE_OF_CREDIT: CURRENT_LIABILITY,
    T.LOAN: LONG_TERM_LIABILITY,
}


def ledger_place(kind: str, *, loan_current: bool = False) -> LedgerPlace:
    """Where an account of ``kind`` lives in the chart of accounts."""
    if kind == T.LOAN and loan_current:
        return CURRENT_LIABILITY
    try:
        return PLACES[kind]
    except KeyError:
        raise LedgerError(
            _("“%(type)s” isn't a bank account type."),
            code="banking.account.type_invalid",
            params={"type": kind},
        ) from None


def next_free_code(organisation: Organisation, place: LedgerPlace) -> str:
    taken = {
        code.lower()
        for code in Account._base_manager.filter(organisation=organisation).values_list(
            "code", flat=True
        )
    }
    for number in range(place.first, place.last + 1):
        if str(number) not in taken:
            return str(number)
    raise LedgerError(
        _(
            "Every code from %(first)d to %(last)d is used: renumber or archive an account in "
            "that range, then try again."
        ),
        code="ledger.bank.no_free_code",
        params={"first": place.first, "last": place.last},
    )


def create_bank_account(
    organisation: Organisation,
    *,
    type: str,  # noqa: A002 - the field's name
    display_name: str,
    institution: str = "",
    currency: str = "CAD",
    account_last4: str = "",
    loan_current: bool = False,
    user: Any = None,
) -> BankAccount:
    """The ledger account and its bank profile, in one transaction (module docstring)."""
    name = " ".join((display_name or "").split())
    if not name:
        raise LedgerError(_("Give the account a name."), code="banking.account.name_required")
    place = ledger_place(type, loan_current=loan_current)
    person = user if user is not None else acting_user()
    by = person if getattr(person, "is_authenticated", False) else None
    with org_context(organisation), transaction.atomic():
        if BankAccount.objects.filter(display_name__iexact=name, deleted_at__isnull=True).exists():
            raise LedgerError(
                _("There's already an account called “%(name)s”. Choose another name."),
                code="banking.account.name_taken",
                params={"name": name},
            )
        ledger = Account(
            organisation=organisation,
            code=next_free_code(organisation, place),
            name_i18n={"en-ca": name},
            type=SUBTYPE_TYPE[place.subtype],
            subtype=place.subtype,
            is_bank=True,
            created_by=by,
        )
        ledger.save()
        bank = BankAccount(
            organisation=organisation,
            gl_account=ledger,
            type=type,
            display_name=name,
            institution=institution.strip(),
            currency=(currency or "CAD").upper(),
            account_last4=account_last4.strip(),
            created_by=by,
        )
        bank.save()
        return bank
