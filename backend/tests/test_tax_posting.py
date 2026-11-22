"""G-01-T07 — posting mapper: tax to the right control accounts, non-claimable tax on the line.

Acceptance (integration with the C-02 posting service): a 50 % ITC purchase posts half the tax to
the expense and half to GST/HST receivable; BC PST goes to the expense, GST to the ITC account;
QC purchases post GST to the ITC and QST to the ITR account; sales post to the payable controls
(PST payable for BC); a component's own control account wins; a missing control account is
refused naming it; every journal balances.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.ledger.models import Account, JournalLine
from numo9.ledger.services import post_journal
from numo9.ledger.template import load_template
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tax.calculator import calculate
from numo9.tax.models import TaxCode, TaxError
from numo9.tax.posting import TaxedLine, journal_lines, map_tax
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
P = Decimal
DAY = dt.date(2026, 6, 15)


def _code(code: str) -> TaxCode:
    found: TaxCode = TaxCode.objects.filter(code=code).order_by("-version").first()  # type: ignore[assignment]
    return found


def _post(org: Organisation, lines: list[LineSpec]) -> list[tuple[str, Decimal, Decimal]]:
    entry = post_journal(JournalSpec(date=DAY, lines=lines), organisation=org, user=None)
    rows = JournalLine.objects.filter(entry=entry).order_by("line_no")
    return [(r.account.code, r.debit, r.credit) for r in rows]


@pytest.fixture
def on_org() -> Organisation:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    return org


def test_50_percent_itc_posts_half_to_expense_half_to_itc(on_org: Organisation) -> None:
    with org_context(on_org):
        meals, bank = Account.objects.get(code="6010"), Account.objects.get(code="1010")
        itc = Account.objects.get(system_role="itc_receivable")
        tax = calculate(_code("purchase.ON.standard"), P("113.00"), inclusive=True, account=meals)
        mapped = map_tax(tax)
        assert (mapped.to_line, [(p.account, p.amount) for p in mapped.postings]) == (
            P("6.50"),
            [(itc, P("6.50"))],
        )
        posted = _post(
            on_org, journal_lines([TaxedLine(meals, tax)], side="purchase", counter=bank)
        )
    assert posted == [
        ("6010", P("106.50"), P("0.00")),
        (itc.code, P("6.50"), P("0.00")),
        ("1010", P("0.00"), P("113.00")),
    ]


def test_bc_pst_on_the_cost_and_sales_to_payables(on_org: Organisation) -> None:
    with org_context(on_org):
        office, bank = Account.objects.get(code="6080"), Account.objects.get(code="1010")
        sales = Account.objects.get(code="4000")
        pst_payable = account(on_org, "2111", "PST payable (BC)", subtype="sales_tax_control")
        itc = Account.objects.get(system_role="itc_receivable")
        hst_payable = Account.objects.get(system_role="gst_hst_payable")
        purchase = calculate(_code("purchase.BC.standard"), P("100.00"), account=office)
        assert _post(
            on_org, journal_lines([TaxedLine(office, purchase)], side="purchase", counter=bank)
        ) == [
            ("6080", P("107.00"), P("0.00")),
            (itc.code, P("5.00"), P("0.00")),
            ("1010", P("0.00"), P("112.00")),
        ]
        bc_sales = _code("sales.BC.standard")
        pst = bc_sales.components.get(position=2).component
        pst.control_account_sales = pst_payable  # the component's own account wins
        pst.save()
        sale = calculate(bc_sales, P("200.00"))
        assert _post(
            on_org, journal_lines([TaxedLine(sales, sale)], side="sales", counter=bank)
        ) == [
            ("4000", P("0.00"), P("200.00")),
            (hst_payable.code, P("0.00"), P("10.00")),
            ("2111", P("0.00"), P("14.00")),
            ("1010", P("224.00"), P("0.00")),
        ]


def test_qc_purchase_gst_to_itc_qst_to_itr() -> None:
    org = Organisation.objects.create(name="Québec inc.")
    load_template(org, "QC")
    with org_context(org):
        office, bank = Account.objects.get(code="6080"), Account.objects.get(code="1010")
        itc = Account.objects.get(system_role="itc_receivable")
        itr = Account.objects.get(system_role="qst_itr")
        tax = calculate(_code("purchase.QC.standard"), P("100.00"), account=office)
        posted = _post(org, journal_lines([TaxedLine(office, tax)], side="purchase", counter=bank))
    assert posted == [
        ("6080", P("100.00"), P("0.00")),
        (itc.code, P("5.00"), P("0.00")),
        (itr.code, P("9.98"), P("0.00")),
        (
            "1010",
            P("0.00"),
            P("114.98"),
        ),
    ]


def test_several_lines_sum_per_control_and_credit_notes_flip(on_org: Organisation) -> None:
    with org_context(on_org):
        office, rent = Account.objects.get(code="6080"), Account.objects.get(code="6130")
        bank = Account.objects.get(code="1010")
        code = _code("purchase.ON.standard")
        lines = journal_lines(
            [
                TaxedLine(office, calculate(code, P("10"))),
                TaxedLine(rent, calculate(code, P("20"))),
            ],
            side="purchase",
            counter=bank,
        )
        posted = _post(on_org, lines)
        itc = Account.objects.get(system_role="itc_receivable").code
        assert [row for row in posted if row[0] == itc] == [(itc, P("3.90"), P("0.00"))]
        credit = journal_lines(
            [TaxedLine(office, calculate(code, P("-10")))], side="purchase", counter=bank
        )
        assert _post(on_org, credit) == [
            ("6080", P("0.00"), P("10.00")),
            (itc, P("0.00"), P("1.30")),
            ("1010", P("11.30"), P("0.00")),
        ]


def test_missing_control_account_is_refused() -> None:
    bare = Organisation.objects.create(name="No chart")
    from numo9.tax.seed import install_tax_table

    install_tax_table(bare)
    with org_context(bare):
        rent = account(bare, "5400", "Rent")
        tax = calculate(_code("purchase.ON.standard"), P("100"), account=rent)
        with pytest.raises(TaxError) as caught:
            map_tax(tax)
    assert caught.value.code == "tax.posting.control_missing"
