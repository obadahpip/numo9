"""Archive and restore accounts (C-01-T08).

An account leaves the chart by being **archived**, never deleted (CRA retention; reports keep
showing its history). Archiving is refused, with the reason named, when:

- it's a **system account** (the posting engine needs it; the error names the role, C-01-T06);
- its **balance isn't zero** in the accounting or the tax book (posted and reversed entries,
  ``book = both`` counting in both): move the balance first, e.g. with a journal;
- it has **sub-accounts that are still active**: archive them first.

An archived account accepts no new postings (C-02 validation refuses inactive accounts) and comes
back with ``restore_account``. Both changes are audited (the account's own audit trail, attributed
to the person making them) and bust the chart cache.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.context import org_context

from .cache import bust_now_and_on_commit
from .models import (
    LOCKED_STATUSES,
    Account,
    AccountStatus,
    Book,
    JournalLine,
    LedgerError,
    SystemRole,
)
from .renumber import acting_as

ZERO = Decimal("0.00")
BOOK_LABELS: dict[str, Any] = {Book.ACCOUNTING: _("accounting book"), Book.TAX: _("tax book")}


def balances(account: Account) -> dict[str, Decimal]:
    """Debit-minus-credit balance of ``account`` in the accounting and the tax book."""
    # In the account's organisation: journal lines have forced row-level security.
    with org_context(account.organisation):
        lines = JournalLine.objects.filter(
            account_id=account.pk, entry__status__in=sorted(LOCKED_STATUSES)
        )
        sums = {
            row["book"]: row["net"]
            for row in lines.values("book")
            .annotate(net=Coalesce(Sum("debit"), ZERO) - Coalesce(Sum("credit"), ZERO))
            .order_by()
        }
    both = sums.get(Book.BOTH, ZERO)
    return {
        Book.ACCOUNTING: both + sums.get(Book.ACCOUNTING, ZERO),
        Book.TAX: both + sums.get(Book.TAX, ZERO),
    }


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def check_archivable(account: Account) -> None:
    if account.system_role:
        raise LedgerError(
            _("%(account)s is the %(role)s account: system accounts can't be archived."),
            code="ledger.account.system_archive",
            params={"account": str(account), "role": SystemRole(account.system_role).label},
        )
    for book, balance in balances(account).items():
        if balance != ZERO:
            raise LedgerError(
                _(
                    "%(account)s has a balance of %(balance)s in the %(book)s. Move the balance "
                    "to another account first, then archive it."
                ),
                code="ledger.account.archive_balance",
                params={
                    "account": str(account),
                    "balance": _money(balance),
                    "book": BOOK_LABELS[book],
                },
            )
    child = (
        Account._base_manager.filter(parent_id=account.pk, status=AccountStatus.ACTIVE)
        .order_by("code")
        .first()
    )
    if child is not None:
        raise LedgerError(
            _("%(account)s has active sub-accounts, such as %(child)s: archive them first."),
            code="ledger.account.archive_children",
            params={"account": str(account), "child": str(child)},
        )


def archive_account(account: Account, *, actor: Any = None) -> Account:
    """Archive ``account`` (rules in the module docstring); a no-op if it already is."""
    with transaction.atomic():
        locked = Account._base_manager.select_for_update().get(pk=account.pk)
        if locked.status == AccountStatus.ARCHIVED:
            return locked
        check_archivable(locked)
        locked.status = AccountStatus.ARCHIVED
        with acting_as(actor):
            locked.save()
        bust_now_and_on_commit(locked.organisation_id)
    return locked


def restore_account(account: Account, *, actor: Any = None) -> Account:
    """Bring an archived account back to the chart."""
    with transaction.atomic():
        locked = Account._base_manager.select_for_update().get(pk=account.pk)
        if locked.status == AccountStatus.ACTIVE:
            return locked
        locked.status = AccountStatus.ACTIVE
        with acting_as(actor):
            locked.save()
        bust_now_and_on_commit(locked.organisation_id)
    return locked
