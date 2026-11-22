"""D-01-T06 — side validator: account type and tax code side per document type, and the
effective-date check.

Acceptance: a purchase code on a sales line is refused naming the line; an expired rate is
refused.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone

from numo9.documents.validation import (
    SIDES,
    DocumentInvalid,
    LineCheck,
    problems,
    side_of,
    validate_lines,
)
from numo9.ledger.models import Account, LedgerError
from numo9.ledger.template import load_template
from numo9.tax.models import TaxCode
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
D = dt.date(2026, 7, 15)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


def first(org: Organisation, **filters: object) -> Account:
    with org_context(org):
        found = Account.objects.filter(**filters).order_by("code").first()
    assert found is not None
    return found


def test_purchase_code_on_a_sales_line_names_the_line(org: Organisation) -> None:
    revenue = first(org, subtype="revenue")
    hst_sales = code_for("sales.ON.standard", "sales", D, org)
    hst_purchase = code_for("purchase.ON.standard", "purchase", D, org)
    with org_context(org), pytest.raises(DocumentInvalid) as caught:
        validate_lines(
            "invoice",
            D,
            [LineCheck(revenue, hst_sales), LineCheck(revenue, hst_purchase)],
        )
    error = caught.value
    assert error.code == "documents.lines.invalid"
    assert [(p.line, p.field, p.code) for p in error.problems] == [
        (2, "tax_code", "documents.line.tax_side")
    ]
    assert error.messages[0] == (
        "Line 2: HST 13 % (Ontario) on purchases is a purchase tax code: choose a sales tax code."
    )
    assert "purchase tax code" in error.problems[0].message


def test_expense_account_on_a_sales_line_and_revenue_on_a_bill(org: Organisation) -> None:
    revenue = first(org, subtype="revenue")
    expense = first(org, type="expense")
    with org_context(org):
        sales = problems("invoice", D, [LineCheck(expense)])
        purchase = problems("bill", D, [LineCheck(revenue)])
        assert problems("bill", D, [LineCheck(expense)]) == []
    assert [(p.line, p.code) for p in sales] == [(1, "documents.line.account_sales")]
    assert [(p.line, p.code) for p in purchase] == [(1, "documents.line.account_purchase")]


def test_engine_bank_archived_and_parent_accounts_are_refused(org: Organisation) -> None:
    ar = first(org, system_role="ar")
    bank = first(org, subtype="bank")
    with org_context(org):
        old = account(org, "4990", "Old sales", subtype="revenue")
        old.archived_at = timezone.now()
        old.status = "archived"
        old.save()
        parent = account(org, "4980", "Consulting", subtype="revenue")
        account(org, "4981", "Consulting — design", subtype="revenue", parent=parent)
        found = problems(
            "invoice", D, [LineCheck(ar), LineCheck(bank), LineCheck(old), LineCheck(parent)]
        )
    assert [(p.line, p.code) for p in found] == [
        (1, "documents.line.account_sales"),
        (2, "documents.line.account_sales"),
        (3, "documents.line.account_sales"),
        (4, "documents.line.account_parent"),
    ]


def test_expired_rate_is_refused(org: Organisation) -> None:
    """NS HST 15 % ended 31 Mar 2025: an old draft moved to 2026 must re-pick the code."""
    old_ns = code_for("sales.NS.standard", "sales", dt.date(2025, 3, 1), org)
    revenue = first(org, subtype="revenue")
    with org_context(org):
        assert problems("invoice", dt.date(2025, 3, 1), [LineCheck(revenue, old_ns)]) == []
        found = problems("invoice", D, [LineCheck(revenue, old_ns)])
    assert [(p.line, p.code) for p in found] == [(1, "tax.code.expired")]


def test_archived_code_is_refused(org: Organisation) -> None:
    code = code_for("sales.AB.standard", "sales", D, org)
    with org_context(org):
        TaxCode.objects.filter(pk=code.pk).update(archived_at=timezone.now())
        code.refresh_from_db()
        found = problems("invoice", D, [LineCheck(None, code)])
    assert [p.code for p in found] == ["tax.code.archived"]


def test_no_tax_documents_carry_no_tax_codes(org: Organisation) -> None:
    code = code_for("sales.ON.standard", "sales", D, org)
    with org_context(org):
        found = problems("invoice", D, [LineCheck(None, code)], tax_mode="no_tax")
        bad_mode = problems("invoice", D, [], tax_mode="sometimes")
    assert [p.code for p in found] == ["documents.line.tax_not_allowed"]
    assert [(p.line, p.code) for p in bad_mode] == [(0, "documents.tax_mode.unknown")]
    error = DocumentInvalid(bad_mode)
    assert error.messages == ["Choose tax exclusive, tax inclusive or no tax."]
    assert error.problems[0].as_dict()["field"] == "tax_mode"


def test_document_kinds() -> None:
    assert {SIDES[k] for k in ("quote", "invoice", "credit_note", "recurring_invoice")} == {"sales"}
    assert {SIDES[k] for k in ("bill", "purchase_order", "supplier_credit")} == {"purchase"}
    with pytest.raises(LedgerError):
        side_of("receipt")


def test_empty_lines_are_fine(org: Organisation) -> None:
    validate_lines("invoice", D, [LineCheck()])
