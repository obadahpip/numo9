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

        from django.utils.translation import gettext_lazy as _

        from numo9.contacts.merge import register_reference
        from numo9.tenancy.sweep import SWEEP_FACTORIES

        from . import demo_seed  # noqa: F401 — registers the banking demo seeder (F-01-T15)

        # A posted spend / receive keeps its contact, like its journal lines (C-02-T04).
        register_reference("banking.BankTransaction", "contact", "keep", _("bank transactions"))

        from .search import register_banking_search

        register_banking_search()  # bank accounts and transactions in the global search (F-01-T13)

        SWEEP_FACTORIES["banking.BankAccount"] = _sweep_bank_account
        SWEEP_FACTORIES["banking.BankTransaction"] = _sweep_bank_transaction
        SWEEP_FACTORIES["banking.StatementImport"] = _sweep_statement_import


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


def _sweep_statement_import(organisation: Any) -> Any:
    from numo9.tenancy.context import org_context

    from .models import StatementImport

    bank = _sweep_bank_account(organisation)
    with org_context(organisation):
        return StatementImport.objects.create(
            organisation=organisation, bank_account=bank, file_name="sweep.csv"
        )
