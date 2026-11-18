"""C-01-T08 — archive service (balance must be 0, not a system account).

Acceptance: archiving an account with a non-zero balance is refused. The balance is checked in
both books (a ``tax``-only line counts in the tax book, ``both`` in both); a system account or an
account with active sub-accounts is refused with the reason named; a zero-balance account (moved
to zero by a later journal) archives, is audited, accepts no posting, and is restored.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest

from numo9.audit.models import AuditEvent
from numo9.ledger.archive import archive_account, balances, restore_account
from numo9.ledger.models import Account, AccountStatus, LedgerError
from numo9.ledger.validation import JournalInvalid, JournalSpec, LineSpec, validate_journal
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account, post_for_test

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


@pytest.fixture
def chart(org: Organisation) -> dict[str, Account]:
    return {
        "bank": account(org, "1000", "Chequing", subtype="bank", gifi_id="1001"),
        "sales": account(org, "4000", "Sales", subtype="revenue", gifi_id="8000"),
        "supplies": account(org, "6100", "Office supplies", gifi_id="8811"),
    }


def _post(debit: Account, credit: Account, amount: str, book: str = "both") -> None:
    post_for_test(
        JournalSpec(
            date=dt.date(2026, 3, 31),
            lines=[
                LineSpec(account=debit, debit=D(amount), book=book),
                LineSpec(account=credit, credit=D(amount), book=book),
            ],
        )
    )


def test_non_zero_balance_is_refused(chart: dict[str, Account]) -> None:
    _post(chart["supplies"], chart["bank"], "125.00")
    with pytest.raises(LedgerError) as caught:
        archive_account(chart["supplies"])
    assert caught.value.code == "ledger.account.archive_balance"
    assert "125.00 in the accounting book" in str(caught.value)
    assert Account.objects.get(pk=chart["supplies"].pk).status == AccountStatus.ACTIVE


def test_a_balance_in_the_tax_book_only_is_refused(chart: dict[str, Account]) -> None:
    _post(chart["supplies"], chart["bank"], "40.00", book="tax")
    assert balances(chart["supplies"]) == {"accounting": D("0.00"), "tax": D("40.00")}
    with pytest.raises(LedgerError, match="in the tax book"):
        archive_account(chart["supplies"])


def test_zero_balance_archives_audited_then_restores(chart: dict[str, Account]) -> None:
    _post(chart["supplies"], chart["bank"], "125.00")
    _post(chart["bank"], chart["supplies"], "125.00")  # moved back to zero
    archived = archive_account(chart["supplies"])
    assert archived.status == AccountStatus.ARCHIVED
    assert archived.archived_at is not None
    event = AuditEvent.objects.filter(object_id=str(archived.public_id)).order_by("-id").first()
    assert event is not None and event.changes["status"] == ["active", "archived"]
    with pytest.raises(JournalInvalid):  # an archived account takes no new postings
        validate_journal(
            JournalSpec(
                date=dt.date(2026, 4, 1),
                lines=[
                    LineSpec(account=archived, debit=D("1.00")),
                    LineSpec(account=chart["bank"], credit=D("1.00")),
                ],
            ),
            archived.organisation,
        )
    assert restore_account(archived).status == AccountStatus.ACTIVE


def test_system_account_is_refused_naming_the_role(org: Organisation) -> None:
    ar = account(org, "1100", "Accounts receivable", subtype="current_asset", system_role="ar")
    with pytest.raises(LedgerError) as caught:
        archive_account(ar)
    assert caught.value.code == "ledger.account.system_archive"
    assert "Accounts receivable" in str(caught.value)


def test_parent_with_active_sub_accounts_is_refused(org: Organisation) -> None:
    parent = account(org, "6000", "Office", gifi_id="8811")
    child = account(org, "6010", "Stationery", gifi_id="8811", parent=parent)
    with pytest.raises(LedgerError, match="active sub-accounts, such as 6010"):
        archive_account(parent)
    archive_account(child)
    assert archive_account(parent).status == AccountStatus.ARCHIVED


def test_archiving_twice_is_harmless(chart: dict[str, Account]) -> None:
    first = archive_account(chart["sales"])
    assert archive_account(first).status == AccountStatus.ARCHIVED
