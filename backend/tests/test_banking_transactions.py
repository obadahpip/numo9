"""F-01-T05 — spend money / receive money post one balanced journal through C-02.

Acceptance: spend 113.00 including HST posts Dr expense 100.00 / Dr ITC 13.00 / Cr bank 113.00;
the journal links back to the transaction (source type and id); receive money is the mirror with
tax collected on the payable control; non-recoverable tax (BC PST, restricted ITC) goes to the
expense line; archived accounts, empty or mis-taxed lines are refused with nothing written;
property: every recorded transaction posts a balanced journal whose bank line equals the total.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.banking.lifecycle import archive_bank_account
from numo9.banking.models import BankTransaction, BankTransactionKind, TaxMode
from numo9.banking.services import create_bank_account
from numo9.banking.transactions import (
    SOURCE_TYPE,
    MoneyLine,
    MoneySpec,
    TaxPortion,
    record_bank_transaction,
)
from numo9.ledger.models import Account, JournalLine, LedgerError, SystemRole
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
D = Decimal
DAY = dt.date(2026, 6, 15)
R = SystemRole


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


@pytest.fixture
def setup(org: Organisation) -> dict[str, Any]:
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    with org_context(org):
        office = Account.objects.filter(subtype="operating_expense").order_by("code").first()
        sales = Account.objects.filter(subtype="revenue").order_by("code").first()
        roles = {a.system_role: a for a in Account.objects.exclude(system_role="")}
    return {"bank": bank, "office": office, "sales": sales, "roles": roles}


def _lines(org: Organisation, txn: BankTransaction) -> list[tuple[str, D, D]]:
    with org_context(org):
        rows = JournalLine.objects.filter(entry=txn.journal_entry).order_by("line_no")
        return [(row.account.code, row.debit, row.credit) for row in rows]


def test_spend_113_inclusive_hst(org: Organisation, setup: dict[str, Any]) -> None:
    bank, office, roles = setup["bank"], setup["office"], setup["roles"]
    txn = record_bank_transaction(
        MoneySpec(
            kind=BankTransactionKind.SPEND,
            bank_account=bank,
            date=DAY,
            reference="Staples #448",
            tax_mode=TaxMode.INCLUSIVE,
            lines=[
                MoneyLine(
                    office,
                    D("113.00"),
                    description="Printer paper",
                    tax_code="purchase.ON.standard",
                    taxes=[TaxPortion(R.ITC_RECEIVABLE, D("13.00"))],
                )
            ],
        ),
        user=None,
    )
    assert (txn.subtotal, txn.tax_total, txn.total) == (D("100.00"), D("13.00"), D("113.00"))
    assert _lines(org, txn) == [
        (office.code, D("100.00"), D("0.00")),
        (roles[R.ITC_RECEIVABLE].code, D("13.00"), D("0.00")),
        (bank.gl_account.code, D("0.00"), D("113.00")),
    ]
    entry = txn.journal_entry
    assert entry is not None
    assert (entry.type, entry.source_type, entry.source_id) == (
        "bank",
        SOURCE_TYPE,
        str(txn.public_id),
    )
    assert entry.status == "posted" and "Staples #448" in entry.narration
    with org_context(org):
        line = txn.lines.get()
    assert (line.amount, line.net, line.tax_amount, line.tax_code) == (
        D("113.00"),
        D("100.00"),
        D("13.00"),
        "purchase.ON.standard",
    )


def test_receive_is_the_mirror(org: Organisation, setup: dict[str, Any]) -> None:
    bank, sales, roles = setup["bank"], setup["sales"], setup["roles"]
    txn = record_bank_transaction(
        MoneySpec(
            kind=BankTransactionKind.RECEIVE,
            bank_account=bank,
            date=DAY,
            lines=[
                MoneyLine(sales, D("200.00"), taxes=[TaxPortion(R.GST_HST_PAYABLE, D("26.00"))])
            ],
        ),
        user=None,
    )
    assert txn.total == D("226.00")
    assert _lines(org, txn) == [
        (sales.code, D("0.00"), D("200.00")),
        (roles[R.GST_HST_PAYABLE].code, D("0.00"), D("26.00")),
        (bank.gl_account.code, D("226.00"), D("0.00")),
    ]


def test_non_recoverable_tax_goes_to_the_expense(org: Organisation, setup: dict[str, Any]) -> None:
    bank, office, roles = setup["bank"], setup["office"], setup["roles"]
    txn = record_bank_transaction(
        MoneySpec(
            kind=BankTransactionKind.SPEND,
            bank_account=bank,
            date=DAY,
            lines=[
                MoneyLine(
                    office,
                    D("100.00"),
                    taxes=[
                        TaxPortion(R.ITC_RECEIVABLE, D("5.00")),
                        TaxPortion(R.PST_PAYABLE, D("7.00"), recoverable=False),
                    ],
                )
            ],
        ),
        user=None,
    )
    assert _lines(org, txn) == [
        (office.code, D("107.00"), D("0.00")),
        (roles[R.ITC_RECEIVABLE].code, D("5.00"), D("0.00")),
        (bank.gl_account.code, D("0.00"), D("112.00")),
    ]


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"lines": []}, "banking.lines_required"),
        ({"amount": D("0")}, "banking.line.amount_positive"),
        ({"amount": D("1.005")}, "banking.amount.precision"),
        ({"tax_mode": TaxMode.NO_TAX}, "banking.line.tax_not_allowed"),
        ({"tax": D("50.00"), "tax_mode": TaxMode.INCLUSIVE}, "banking.line.tax_exceeds_amount"),
        ({"role": "ar"}, "banking.line.tax_invalid"),
        ({"kind": "transfer"}, "banking.kind_invalid"),
    ],
)
def test_refusals_write_nothing(
    org: Organisation, setup: dict[str, Any], change: dict[str, Any], code: str
) -> None:
    taxes = [TaxPortion(change.get("role", R.ITC_RECEIVABLE), change.get("tax", D("1.30")))]
    lines = change.get(
        "lines", [MoneyLine(setup["office"], change.get("amount", D("10.00")), taxes=taxes)]
    )
    spec = MoneySpec(
        kind=change.get("kind", BankTransactionKind.SPEND),
        bank_account=setup["bank"],
        date=DAY,
        lines=lines,
        tax_mode=change.get("tax_mode", TaxMode.EXCLUSIVE),
    )
    with pytest.raises(LedgerError) as caught:
        record_bank_transaction(spec, user=None)
    assert caught.value.code == code
    with org_context(org):
        assert not BankTransaction.objects.exists()


def test_archived_account_refused(org: Organisation, setup: dict[str, Any]) -> None:
    bank = archive_bank_account(setup["bank"])
    with pytest.raises(LedgerError) as caught:
        record_bank_transaction(
            MoneySpec(BankTransactionKind.SPEND, bank, DAY, [MoneyLine(setup["office"], D("5"))]),
            user=None,
        )
    assert caught.value.code == "banking.account.archived"


def test_missing_control_account_named(setup: dict[str, Any]) -> None:
    other = Organisation.objects.create(name="Bare Ltd.")
    bank = create_bank_account(other, type="chequing", display_name="Cash box")
    with org_context(other):
        from tests.ledger_helpers import account

        rent = account(other, "5400", "Rent")
    with pytest.raises(LedgerError) as caught:
        record_bank_transaction(
            MoneySpec(
                BankTransactionKind.SPEND,
                bank,
                DAY,
                [MoneyLine(rent, D("10"), taxes=[TaxPortion(R.ITC_RECEIVABLE, D("1.30"))])],
            ),
            user=None,
        )
    assert caught.value.code == "banking.tax.control_missing"


amounts = st.decimals(min_value=D("0.01"), max_value=D("99999.99"), places=2)


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    rows=st.lists(st.tuples(amounts, st.integers(0, 15), st.booleans()), min_size=1, max_size=5),
    spend=st.booleans(),
    inclusive=st.booleans(),
)
def test_property_balanced(
    org: Organisation, setup: dict[str, Any], rows: list[Any], spend: bool, inclusive: bool
) -> None:
    lines = []
    for amount, rate, recoverable in rows:
        tax = (amount * rate / 100).quantize(D("0.01"))
        if inclusive and tax > amount:
            tax = amount
        lines.append(
            MoneyLine(
                setup["office"] if spend else setup["sales"],
                amount,
                taxes=[
                    TaxPortion(R.ITC_RECEIVABLE if spend else R.GST_HST_PAYABLE, tax, recoverable)
                ],
            )
        )
    txn = record_bank_transaction(
        MoneySpec(
            BankTransactionKind.SPEND if spend else BankTransactionKind.RECEIVE,
            setup["bank"],
            DAY,
            lines,
            tax_mode=TaxMode.INCLUSIVE if inclusive else TaxMode.EXCLUSIVE,
        ),
        user=None,
    )
    posted = _lines(org, txn)
    assert sum(d for _, d, _ in posted) == sum(c for _, _, c in posted)
    bank_code = setup["bank"].gl_account.code
    bank_side = [d - c for code, d, c in posted if code == bank_code]
    assert bank_side == [-txn.total if spend else txn.total]
    assert txn.total == txn.subtotal + txn.tax_total
