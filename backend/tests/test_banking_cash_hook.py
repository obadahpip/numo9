"""F-07-T03 — the pre-post hook of the C-02 posting pipeline evaluates the negative-balance policy
for every bank/cash line of any source and raises ``NegativeBalanceWarning`` /
``NegativeBalanceBlocked``.

Acceptance: the hook fires for journal, spend, transfer, payment and payroll sources — one
integration test per source on this branch (payroll: the system journal type posted by its
process, the placeholder until the payroll module). With the defaults: Petty Cash (Cash) is
blocked for the owner (not an adviser); Chequing warns (posted with a reason, which is kept);
an adviser is warned on Cash; an ALLOW policy lets it through; money in, a funded account and
credit cards are never checked; a system job and a reversal aren't stopped.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.banking.models import BankTransactionKind, CashControlPolicy, TaxMode
from numo9.banking.services import attach_bank_account, create_bank_account
from numo9.banking.transactions import MoneyLine, MoneySpec, record_bank_transaction
from numo9.banking.transfers import record_transfer
from numo9.ledger import policy as ledger_policy
from numo9.ledger.models import (
    Account,
    JournalCategory,
    JournalEntry,
    JournalOverride,
    JournalType,
)
from numo9.ledger.policy import NegativeBalanceBlocked, NegativeBalanceWarning, NegativeCash
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.sales.models import CustomerCredit
from numo9.sales.receipts import receive_payment, refund_credit
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, sales_books

pytestmark = pytest.mark.django_db
D = Decimal
REASON = "Owner tops the float up on Monday."


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    org = books["org"]
    books.update(people(org))
    books["chequing"] = create_bank_account(org, type="chequing", display_name="TD Chequing")
    books["petty"] = create_bank_account(org, type="cash", display_name="Petty Cash")
    books["visa"] = create_bank_account(org, type="credit_card", display_name="TD Visa")
    with org_context(org):
        books["office"] = Account.objects.filter(subtype="operating_expense").order_by("code")[0]
        books["wages"] = Account.objects.filter(subtype="operating_expense").order_by("-code")[0]
    return books


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The source type of every posting the hook assessed (it wraps the registered policy)."""
    calls: list[str] = []
    (assess,) = ledger_policy.CASH_POLICY

    def spy(checked: Any, organisation: Any, person: Any, today: Any) -> Any:
        calls.append(checked.spec.source_type or checked.spec.type)
        return assess(checked, organisation, person, today)

    monkeypatch.setattr(ledger_policy, "CASH_POLICY", [spy])
    return calls


def _spend(books: dict[str, Any], bank: str, amount: str, **options: Any) -> Any:
    return record_bank_transaction(
        MoneySpec(
            kind=BankTransactionKind.SPEND,
            bank_account=books[bank],
            date=DAY,
            tax_mode=TaxMode.NO_TAX,
            lines=[MoneyLine(books["office"], D(amount))],
        ),
        **options,
    )


def _journal(books: dict[str, Any], bank: str, amount: str) -> JournalSpec:
    return JournalSpec(
        date=DAY,
        lines=(
            LineSpec(books["office"], debit=D(amount)),
            LineSpec(books[bank].gl_account, credit=D(amount)),
        ),
    )


def test_journal_source(books: dict[str, Any], seen: list[str]) -> None:
    with org_context(books["org"]):
        with pytest.raises(NegativeBalanceBlocked) as raised:
            post_journal(_journal(books, "petty", "417.22"), user=books["owner"])
        assert raised.value.messages[0].startswith("Petty Cash would be −417.22 on 15 Jun 2026")
        assert raised.value.projections[0].action == "block"
        with pytest.raises(NegativeBalanceWarning):  # an adviser on Cash: warned
            post_journal(_journal(books, "petty", "417.22"), user=books["adviser"])
        entry = post_journal(
            _journal(books, "petty", "417.22"), user=books["adviser"], override_reason=REASON
        )
        assert JournalOverride.objects.get(entry=entry).reason == REASON
    assert seen == ["manual"] * 3


def test_spend_source(books: dict[str, Any], seen: list[str]) -> None:
    with pytest.raises(NegativeBalanceBlocked):
        _spend(books, "petty", "50.00", user=books["owner"])
    with pytest.raises(NegativeBalanceWarning) as warned:  # chequing: WARN, owner may override
        _spend(books, "chequing", "50.00", user=books["owner"])
    assert warned.value.error_list[0].code == "ledger.journal.override_reason_required"
    assert warned.value.projections[0].as_dict()["account_type"] == "chequing"
    txn = _spend(books, "chequing", "50.00", user=books["owner"], override_reason=REASON)
    with org_context(books["org"]):
        assert JournalOverride.objects.get(entry=txn.journal_entry).user == books["owner"]
    assert set(seen) == {"banking.banktransaction"} and len(seen) == 3


def test_transfer_source(books: dict[str, Any], seen: list[str]) -> None:
    with pytest.raises(NegativeBalanceBlocked) as raised:
        record_transfer(
            books["petty"], books["chequing"], date=DAY, amount="20.00", user=books["owner"]
        )
    assert isinstance(raised.value, NegativeCash)  # the journals API's 409 shape
    # the card is a liability: paying it from a funded chequing account is never checked
    record_transfer(
        books["visa"], books["chequing"], date=DAY, amount="500.00", user=books["owner"]
    )
    record_transfer(
        books["chequing"], books["petty"], date=DAY, amount="100.00", user=books["owner"]
    )
    assert seen == ["banking.banktransfer"] * 3


def test_payment_source(books: dict[str, Any], seen: list[str]) -> None:
    receive_payment(books["customers"]["ON"], books["chequing"], DAY, D("113.00"), books["owner"])
    with org_context(books["org"]):
        credit = CustomerCredit.objects.get()
    with pytest.raises(NegativeBalanceBlocked):  # refunded in cash from an empty float
        refund_credit(credit, books["petty"], DAY, D("40.00"), books["owner"])
    refund_credit(credit, books["chequing"], DAY, D("40.00"), books["owner"])  # funded
    assert seen == ["sales.payment", "sales.credit_refund", "sales.credit_refund"]


def test_payroll_source(books: dict[str, Any], seen: list[str]) -> None:
    spec = JournalSpec(
        date=DAY,
        type=JournalType.PAYROLL,
        journal_type=JournalCategory.PAYROLL,
        source_type="payroll.payrun",
        source_id="run-1",
        lines=tuple(
            line
            for _n in range(3)
            for line in (
                LineSpec(books["wages"], debit=D("1000.00")),
                LineSpec(books["chequing"].gl_account, credit=D("1000.00")),
            )
        ),
    )
    with org_context(books["org"]):
        with pytest.raises(NegativeBalanceWarning) as warned:
            post_journal(spec, user=books["owner"], caller="payroll")
        assert warned.value.projections[0].lowest == D("-3000.00")  # 3 payments, one check
        post_journal(spec, user=books["owner"], caller="payroll", override_reason=REASON)
    assert seen == ["payroll.payrun"] * 2


def test_allow_policy_system_jobs_and_reversals(books: dict[str, Any], seen: list[str]) -> None:
    org = books["org"]
    with org_context(org):
        CashControlPolicy.objects.filter(account_type="cash").update(standard_action="allow")
        posted = post_journal(_journal(books, "petty", "10.00"), user=books["owner"])
        CashControlPolicy.objects.filter(account_type="cash").update(standard_action="block")
        assert post_journal(_journal(books, "petty", "10.00"), user=None).number  # system job
        money_in = post_journal(
            JournalSpec(
                date=DAY,
                lines=(
                    LineSpec(books["petty"].gl_account, debit=D("5.00")),
                    LineSpec(books["office"], credit=D("5.00")),
                ),
            ),
            user=books["owner"],
        )
        from numo9.ledger.services import reverse

        assert reverse(money_in, user=books["owner"]).number  # a reversal isn't stopped
        assert JournalEntry.objects.filter(pk=posted.pk).exists()


def test_unprofiled_ledger_bank_account_is_treated_as_cash(books: dict[str, Any]) -> None:
    from tests.ledger_helpers import account

    with org_context(books["org"]):
        loose = account(books["org"], "1090", "Old float", subtype="bank")
        with pytest.raises(NegativeBalanceBlocked):
            post_journal(
                JournalSpec(
                    date=DAY,
                    lines=(
                        LineSpec(books["office"], debit=D("1.00")),
                        LineSpec(loose, credit=D("1.00")),
                    ),
                ),
                user=books["owner"],
            )
        attach_bank_account(loose, type="chequing", display_name="Old float")
        with pytest.raises(NegativeBalanceWarning):
            post_journal(
                JournalSpec(
                    date=dt.date(2026, 6, 15),
                    lines=(
                        LineSpec(books["office"], debit=D("1.00")),
                        LineSpec(loose, credit=D("1.00")),
                    ),
                ),
                user=books["owner"],
            )
