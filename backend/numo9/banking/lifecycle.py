"""Delete, archive and restore bank accounts (F-01-T04).

- **Delete** — only while the account has **no transactions**: no journal entry (draft, waiting,
  posted or reversed) has a line on its ledger account. Otherwise ``BankAccountInUse``
  (``banking.account.has_transactions``, HTTP 409 in the API) names the count: "TD Chequing has 1
  transaction — archive it instead." Deleting removes the bank profile and its ledger account
  together (soft delete: records are kept for CRA retention).
- **Archive** — always allowed, with or without transactions or a balance: ``archived_at`` is set
  on the bank profile only. The ledger account and every posted line stay as they are, so the
  account **keeps showing in reports** (trial balance, balance sheet, its own history); it is
  **hidden from pickers** (``BankAccount.objects.pickable()``) so no new transaction chooses it.
- **Restore** — clears ``archived_at``; the account is pickable again.

Every change is audited (``AuditedModel``), attributed to the person making it.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import ngettext

from numo9.ledger.models import JournalEntry, LedgerError
from numo9.ledger.renumber import acting_as
from numo9.tenancy.context import org_context

from .models import BankAccount


class BankAccountInUse(LedgerError):
    """The bank account has transactions: archive it instead (409 in the API)."""

    status_code = 409


def transaction_count(bank: BankAccount) -> int:
    """Journal entries, in any state, with at least one line on the account's ledger account."""
    with org_context(bank.organisation):
        return (
            JournalEntry.objects.filter(lines__account_id=bank.gl_account_id)
            .values("pk")
            .distinct()
            .count()
        )


def _locked(bank: BankAccount) -> BankAccount:
    return BankAccount._base_manager.select_for_update().get(pk=bank.pk)


def delete_bank_account(bank: BankAccount, *, actor: Any = None) -> None:
    """Soft-delete the bank account and its ledger account; refused when it has transactions."""
    with org_context(bank.organisation), transaction.atomic():
        locked = _locked(bank)
        count = transaction_count(locked)
        if count:
            raise BankAccountInUse(
                ngettext(
                    "%(name)s has %(count)d transaction — archive it instead.",
                    "%(name)s has %(count)d transactions — archive it instead.",
                    count,
                ),
                code="banking.account.has_transactions",
                params={"name": locked.display_name, "count": count},
            )
        with acting_as(actor):
            locked.soft_delete()
            locked.gl_account.soft_delete()


def archive_bank_account(bank: BankAccount, *, actor: Any = None) -> BankAccount:
    """Hide the account from pickers, keep it in reports; a no-op if it already is archived."""
    with org_context(bank.organisation), transaction.atomic():
        locked = _locked(bank)
        if locked.archived_at is None:
            locked.archived_at = timezone.now()
            with acting_as(actor):
                locked.save()
        return locked


def restore_bank_account(bank: BankAccount, *, actor: Any = None) -> BankAccount:
    """Make an archived account pickable again; a no-op if it isn't archived."""
    with org_context(bank.organisation), transaction.atomic():
        locked = _locked(bank)
        if locked.archived_at is not None:
            locked.archived_at = None
            with acting_as(actor):
                locked.save()
        return locked
