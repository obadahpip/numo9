"""D-01-T08 — posting preview: the journal a document will post, with the tax control accounts;
posting the preview gives exactly the previewed lines (what D-03a will post)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.documents.posting import PreviewLine, preview
from numo9.documents.validation import DocumentInvalid
from numo9.ledger.models import Account, JournalLine
from numo9.ledger.services import post_journal
from numo9.ledger.template import load_template
from numo9.orgsettings.models import LockModule
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db
D = dt.date(2026, 7, 15)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    people(organisation)
    return organisation


def acct(org: Organisation, **filters: object) -> Account:
    with org_context(org):
        found = Account.objects.filter(**filters).order_by("code").first()
    assert found is not None
    return found


def rows(lines: object) -> list[tuple[str, Decimal, Decimal]]:
    return sorted(
        (line.account.code, Decimal(line.debit), Decimal(line.credit))
        for line in lines  # type: ignore[attr-defined]
    )


def test_invoice_preview_and_posting_match(org: Organisation) -> None:
    revenue = acct(org, subtype="revenue")
    hst = code_for("sales.ON.standard", "sales", D, org)
    gst = code_for("sales.AB.standard", "sales", D, org)
    with org_context(org):
        customer = contact(org, "Maple Café")
        result = preview(
            "invoice",
            D,
            [
                PreviewLine(
                    revenue, Decimal("2"), Decimal("50.00"), tax_code=hst, description="Design"
                ),
                PreviewLine(revenue, Decimal("1"), Decimal("100.00"), tax_code=gst),
            ],
            discount_type="percent",
            discount_value=Decimal("10"),
            contact=customer,
        )
        assert result.complete
        assert (result.result.discount_total, result.result.total) == (
            Decimal("20.00"),
            Decimal("196.20"),
        )
        previewed = result.as_dict()
        assert previewed["debits"] == previewed["credits"] == "196.20"
        ar = acct(org, system_role="ar")
        gst_hst = acct(org, system_role="gst_hst_payable")
        assert rows(result.lines) == sorted(
            [
                (revenue.code, Decimal("0"), Decimal("90.00")),
                (revenue.code, Decimal("0"), Decimal("90.00")),
                (gst_hst.code, Decimal("0"), Decimal("16.20")),  # HST 11.70 + GST 4.50
                (ar.code, Decimal("196.20"), Decimal("0")),
            ]
        )
        entry = post_journal(result.spec(source_type="test.invoice"), module=LockModule.AR)
        posted = JournalLine.objects.filter(entry=entry).select_related("account")
        assert rows(posted) == rows(result.lines)


def test_bill_preview_books_non_claimable_tax_on_the_expense(org: Organisation) -> None:
    meals = acct(org, code="6010")
    bc = code_for("purchase.BC.standard", "purchase", D, org)
    on_meals = code_for("purchase.ON.standard.itc50", "purchase", D, org)
    office = acct(org, type="expense", default_tax_key="purchase.ON.standard")
    with org_context(org):
        supplier = contact(org, "Vancouver Props", roles=["supplier"])
        result = preview(
            "bill",
            D,
            [
                PreviewLine(office, Decimal("1"), Decimal("100.00"), tax_code=bc),
                PreviewLine(meals, Decimal("1"), Decimal("100.00"), tax_code=on_meals),
            ],
            contact=supplier,
        )
        itc = acct(org, system_role="itc_receivable")
        ap = acct(org, system_role="ap")
        lines = {code: (debit, credit) for code, debit, credit in rows(result.lines)}
        # BC: GST 5.00 claimable, PST 7.00 on the cost; meals: HST 13.00, half claimable.
        assert lines[office.code] == (Decimal("107.00"), Decimal("0"))
        assert lines[meals.code] == (Decimal("106.50"), Decimal("0"))
        assert lines[itc.code] == (Decimal("11.50"), Decimal("0"))
        assert lines[ap.code] == (Decimal("0"), Decimal("225.00"))
        entry = post_journal(result.spec(), module=LockModule.AP)
        posted = JournalLine.objects.filter(entry=entry).select_related("account")
        assert rows(posted) == rows(result.lines)


def test_credit_note_is_the_mirror(org: Organisation) -> None:
    revenue = acct(org, subtype="revenue")
    hst = code_for("sales.ON.standard", "sales", D, org)
    with org_context(org):
        customer = contact(org, "Maple Café")
        result = preview(
            "credit_note",
            D,
            [PreviewLine(revenue, Decimal("1"), Decimal("100.00"), tax_code=hst)],
            contact=customer,
        )
        ar = acct(org, system_role="ar")
        lines = {code: (debit, credit) for code, debit, credit in rows(result.lines)}
        assert lines[revenue.code] == (Decimal("100.00"), Decimal("0"))
        assert lines[ar.code] == (Decimal("0"), Decimal("113.00"))


def test_inclusive_and_incomplete_drafts(org: Organisation) -> None:
    revenue = acct(org, subtype="revenue")
    hst = code_for("sales.ON.standard", "sales", D, org)
    with org_context(org):
        result = preview(
            "invoice",
            D,
            [
                PreviewLine(revenue, Decimal("1"), Decimal("113.00"), tax_code=hst),
                PreviewLine(None, Decimal("1"), Decimal("50.00")),
            ],
            tax_mode="inclusive",
            contact=contact(org, "Maple Café"),
        )
        assert result.complete is False
        lines = {code: (debit, credit) for code, debit, credit in rows(result.lines)}
        assert lines[revenue.code] == (Decimal("0"), Decimal("100.00"))
        assert result.result.total == Decimal("163.00")


def test_invalid_lines_are_refused(org: Organisation) -> None:
    expense = acct(org, type="expense")
    with org_context(org), pytest.raises(DocumentInvalid):
        preview("invoice", D, [PreviewLine(expense, Decimal("1"), Decimal("10.00"))])


def test_no_tax_documents(org: Organisation) -> None:
    revenue = acct(org, subtype="revenue")
    with org_context(org):
        result = preview(
            "invoice",
            D,
            [PreviewLine(revenue, Decimal("3"), Decimal("10.00"))],
            tax_mode="no_tax",
            contact=contact(org, "Maple Café"),
        )
        assert result.as_dict()["debits"] == "30.00"
