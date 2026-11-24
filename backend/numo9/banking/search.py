"""Banking in the global search (F-01-T13, A-09): bank accounts and spend / receive money.

- A **bank account** is found by its name, institution, type and its ledger account's code
  ("petty" finds Petty Cash) and opens the account's page; archived accounts stay findable (they
  are kept in reports) and say so.
- A **bank transaction** is found by its reference, contact, bank account, kind, amount and date
  and opens its bank account's register.
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext as _

from numo9.search.registry import Doc

VIEW = "accounting.banking.view"
READ = "accounting.banking.read"


def _org(instance: Any) -> str:
    return str(instance.organisation.public_id)


def bank_account_document(account: Any) -> Doc | None:
    gl = account.gl_account
    state = _("Archived") if account.archived_at is not None else ""
    return Doc(
        title=account.display_name,
        subtitle=" · ".join(
            str(x) for x in (account.get_type_display(), account.institution, state) if x
        ),
        code=gl.code if gl is not None else "",
        body=" ".join(x for x in (account.institution, account.currency) if x),
        url=f"/o/{_org(account)}/banking/{account.public_id}",
        permission_key=VIEW,
        feature_key=READ,
    )


def bank_transaction_document(txn: Any) -> Doc | None:
    contact = txn.contact.display_name if txn.contact_id and txn.contact is not None else ""
    kind = str(txn.get_kind_display())
    state = _("Voided") if txn.status == "voided" else ""
    return Doc(
        title=" — ".join(x for x in (kind, contact or txn.reference) if x),
        subtitle=" · ".join(x for x in (txn.bank_account.display_name, txn.reference, state) if x),
        code=txn.reference,
        body=" ".join(line.description for line in txn.lines.all() if line.description)
        if txn.pk
        else "",
        amount=txn.total,
        date=txn.date,
        url=f"/o/{_org(txn)}/banking/{txn.bank_account.public_id}",
        permission_key=VIEW,
        feature_key=READ,
    )


def register_banking_search() -> None:
    from numo9.search.registry import register_dependent, register_provider

    from .models import BankAccount, BankTransaction, BankTransactionLine

    register_provider(BankAccount, bank_account_document)
    register_provider(BankTransaction, bank_transaction_document)
    register_dependent(BankTransactionLine, lambda line: line.transaction)
