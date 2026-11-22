from typing import Any

from django.apps import AppConfig


class BankingConfig(AppConfig):
    """Banking (F): bank, credit-card, loan, cash and clearing accounts that work the moment they
    exist — no feed, import, reconciliation or plan upgrade (F-01)."""

    name = "numo9.banking"
    label = "banking"
    verbose_name = "Banking"

    def ready(self) -> None:
        from numo9.ledger.services import ENTRY_WRITTEN

        from .balances import entry_written

        if entry_written not in ENTRY_WRITTEN:
            ENTRY_WRITTEN.append(entry_written)  # bust cached balances on every post (F-01-T06)

        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["banking.BankAccount"] = _sweep_bank_account
        SWEEP_FACTORIES["banking.BankTransaction"] = _sweep_bank_transaction


def _sweep_bank_account(organisation: Any) -> Any:
    import uuid

    from .services import create_bank_account

    return create_bank_account(
        organisation, type="chequing", display_name=f"Sweep {uuid.uuid4().hex[:8]}"
    )


def _sweep_bank_transaction(organisation: Any) -> Any:
    import uuid
    from decimal import Decimal

    from numo9.ledger.models import SUBTYPE_TYPE, Account
    from numo9.tenancy.context import org_context

    from .models import BankAccount, BankTransactionKind
    from .transactions import MoneyLine, MoneySpec, record_bank_transaction

    with org_context(organisation):
        bank = BankAccount.objects.pickable().first()
        if bank is None:
            bank = _sweep_bank_account(organisation)
        income = Account(
            organisation=organisation,
            code=f"S{uuid.uuid4().hex[:8]}",
            name_i18n={"en-ca": "Sweep income"},
            type=SUBTYPE_TYPE["revenue"],
            subtype="revenue",
        )
        income.save()
    import datetime as dt

    return record_bank_transaction(
        MoneySpec(
            BankTransactionKind.RECEIVE,
            bank,
            dt.date.today(),
            [MoneyLine(income, Decimal("10.00"))],
        ),
        user=None,
    )
