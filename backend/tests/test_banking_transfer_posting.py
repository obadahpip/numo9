"""F-06-T03 — a transfer posts one journal, Dr to / Cr from, source TRANSFER; void reverses it.

Acceptance: the GL net movement across both accounts is 0 (unit), and stays 0 for any sequence
of transfers and voids between chequing, petty cash and a credit card (Hypothesis property).
Also: the journal links back to the transfer (type ``transfer``, source type and id); a refused
transfer writes nothing; voiding twice is refused; the balances of both accounts move.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.banking.balances import ledger_balance
from numo9.banking.models import BankAccount, BankTransfer, BankTransferStatus
from numo9.banking.services import create_bank_account
from numo9.banking.transfers import SOURCE_TYPE, record_transfer, void_transfer
from numo9.ledger.models import JournalEntry, JournalLine, JournalStatus, LedgerError
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
D = Decimal
DAY = dt.date(2026, 6, 3)


def _banks(org: Organisation) -> dict[str, BankAccount]:
    return {
        "chequing": create_bank_account(org, type="chequing", display_name="TD Chequing"),
        "petty": create_bank_account(org, type="cash", display_name="Petty Cash"),
        "visa": create_bank_account(org, type="credit_card", display_name="TD Visa"),
    }


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def _net(org: Organisation, *banks: BankAccount) -> D:
    with org_context(org):
        totals = JournalLine.objects.filter(
            account__in=[b.gl_account for b in banks],
            entry__status__in=[JournalStatus.POSTED, JournalStatus.REVERSED],
        ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    return (totals["debit"] or D(0)) - (totals["credit"] or D(0))


def test_fund_petty_cash_posts_one_journal_dr_to_cr_from(org: Organisation) -> None:
    banks = _banks(org)
    transfer = record_transfer(
        banks["chequing"], banks["petty"], date=DAY, amount="1000.00", reference="Float"
    )
    with org_context(org):
        entry = JournalEntry.objects.get()
        assert transfer.journal_entry_id == entry.pk
        assert (entry.type, entry.source_type, entry.source_id) == (
            "transfer",
            SOURCE_TYPE,
            str(transfer.public_id),
        )
        assert entry.narration == "Transfer from TD Chequing to Petty Cash: Float"
        lines = [
            (line.account_id, line.debit, line.credit) for line in entry.lines.order_by("line_no")
        ]
    assert lines == [
        (banks["petty"].gl_account_id, D("1000.00"), D("0.00")),
        (banks["chequing"].gl_account_id, D("0.00"), D("1000.00")),
    ]
    assert _net(org, banks["chequing"], banks["petty"]) == 0
    assert ledger_balance(banks["petty"]) == D("1000.00")
    assert ledger_balance(banks["chequing"]) == D("-1000.00")


def test_void_reverses_both_sides(org: Organisation) -> None:
    banks = _banks(org)
    transfer = record_transfer(banks["chequing"], banks["visa"], date=DAY, amount="250.00")
    voided = void_transfer(transfer)
    assert voided.status == BankTransferStatus.VOIDED and voided.voided_at is not None
    with org_context(org):
        original = JournalEntry.objects.get(pk=transfer.journal_entry_id)
        assert original.status == JournalStatus.REVERSED
        reversal = JournalEntry.objects.get(reversal_of=original)
        assert reversal.source_type == SOURCE_TYPE
    assert ledger_balance(banks["chequing"]) == 0
    assert ledger_balance(banks["visa"]) == 0
    with pytest.raises(LedgerError) as raised:
        void_transfer(voided)
    assert raised.value.error_list[0].code == "banking.transfer.voided"


def test_refused_transfer_writes_nothing(org: Organisation) -> None:
    banks = _banks(org)
    with pytest.raises(LedgerError):
        record_transfer(banks["petty"], banks["petty"], date=DAY, amount="5.00")
    with org_context(org):
        assert not BankTransfer.objects.exists()
        assert not JournalEntry.objects.exists()


MOVES = st.lists(
    st.tuples(
        st.sampled_from(["chequing", "petty", "visa"]),
        st.sampled_from(["chequing", "petty", "visa"]),
        st.decimals(min_value=D("0.01"), max_value=D("99999.99"), places=2),
        st.booleans(),
    ).filter(lambda move: move[0] != move[1]),
    min_size=1,
    max_size=6,
)


@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(moves=MOVES)
def test_property_net_movement_across_both_is_zero(moves: list[Any]) -> None:
    org = Organisation.objects.create(name="Property Co.")
    banks = _banks(org)
    expected = {name: D("0.00") for name in banks}
    for source, target, amount, void in moves:
        transfer = record_transfer(banks[source], banks[target], date=DAY, amount=amount)
        with org_context(org):
            lines = list(JournalLine.objects.filter(entry=transfer.journal_entry))
        # each journal: two lines, on the pair only, netting to zero
        assert {line.account_id for line in lines} == {
            banks[source].gl_account_id,
            banks[target].gl_account_id,
        }
        assert len(lines) == 2 and sum(line.debit - line.credit for line in lines) == 0
        if void:
            void_transfer(transfer)
        else:
            expected[source] -= amount
            expected[target] += amount
    assert _net(org, *banks.values()) == 0
    for name, bank in banks.items():
        assert ledger_balance(bank) == expected[name]
