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
        # A bank rule's fixed contact is a setting: it follows the surviving contact (F-04-T02).
        register_reference("banking.BankRule", "contact", "move", _("bank rules"))

        from .search import register_banking_search

        register_banking_search()  # bank accounts and transactions in the global search (F-01-T13)

        from numo9.audit.presenter import ACTION_LABELS

        # Statement imports in the audit log (F-02-T15).
        ACTION_LABELS.setdefault("banking.statementimport.committed", _("Statement imported"))
        ACTION_LABELS.setdefault("banking.statementimport.undone", _("Statement import undone"))
        from .statements import errors as _statement_errors  # noqa: F401 - catalogue entries

        SWEEP_FACTORIES["banking.BankAccount"] = _sweep_bank_account
        SWEEP_FACTORIES["banking.BankTransaction"] = _sweep_bank_transaction
        SWEEP_FACTORIES["banking.StatementImport"] = _sweep_statement_import
        SWEEP_FACTORIES["banking.BankRule"] = _sweep_bank_rule  # F-04-T09
        SWEEP_FACTORIES.setdefault("banking.StatementLine", _sweep_statement_line)
        SWEEP_FACTORIES["banking.BankTransfer"] = _sweep_bank_transfer

        # Every new organisation starts with the default negative-balance policies (F-07-T01).
        from django.db.models.signals import post_save

        from numo9.tenancy.models import Organisation

        post_save.connect(
            _seed_new_organisation, sender=Organisation, dispatch_uid="banking_seed_cash_policies"
        )


def _seed_new_organisation(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    if created and not kwargs.get("raw"):
        from .cash_controls import seed_cash_policies

        seed_cash_policies(instance)


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


def _sweep_bank_rule(organisation: Any) -> Any:
    import uuid

    from numo9.tenancy.context import org_context

    from .rules.conditions import Condition
    from .rules.service import RuleDefinition, save_rule

    with org_context(organisation):
        return save_rule(
            RuleDefinition(
                type="transfer",
                name=f"Sweep {uuid.uuid4().hex[:8]}",
                conditions=[Condition("description", "contains", "sweep")],
                transfer_account=_sweep_bank_account(organisation),
            )
        )


def _sweep_statement_line(organisation: Any) -> Any:
    import datetime as dt
    import uuid
    from decimal import Decimal

    from numo9.tenancy.context import org_context

    from .models import BankAccount, StatementLine

    with org_context(organisation):
        bank = BankAccount.objects.pickable().first() or _sweep_bank_account(organisation)
        return StatementLine.objects.create(
            organisation=organisation,
            bank_account=bank,
            date=dt.date.today(),
            amount=Decimal("-10.00"),
            description="Sweep",
            fingerprint=uuid.uuid4().hex,
        )


def _sweep_bank_transfer(organisation: Any) -> Any:
    import datetime as dt
    import uuid

    from .services import create_bank_account
    from .transfers import record_transfer

    source = _sweep_bank_account(organisation)
    target = create_bank_account(
        organisation, type="cash", display_name=f"Sweep cash {uuid.uuid4().hex[:8]}"
    )
    return record_transfer(source, target, date=dt.date.today(), amount="10.00", user=None)
