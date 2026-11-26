"""E-04-T06 — reimbursement bill on approval: approving a claim creates a bill to the employee's
contact (created from the user with the employee role, then reused), tax inclusive, one line per
claim line, posted at once — Dr categories (net + non-claimable tax), Dr ITC, Cr Unpaid expense
claims (not AP) — awaiting payment; the claim links the bill; a locked AP period refuses the
approval as a whole."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.contacts.models import ContactPerson
from numo9.ledger.models import Account, JournalLine, SystemRole
from numo9.orgsettings.models import LockDate, TaxRegistration
from numo9.purchases import expense_claims as flow
from numo9.purchases.models import Bill, BillStatus, ExpenseClaim, ExpenseClaimStatus
from numo9.rbac.models import ApprovalLimit
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from tests.expense_helpers import DAY, add_line, add_trip, expense_org, make_claim

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def setup() -> dict[str, Any]:
    org, who = expense_org()
    with org_context(org):
        TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
        ApprovalLimit.objects.create(
            user=who["adviser"], doc_type="expense_claim", max_amount=D("5000")
        )
        office = Account.objects.get(code="6080")
        meals = Account.objects.get(itc_restriction_pct=D("50"))
    hst = code_for("purchase.ON.standard", "purchase", DAY, org)
    claim = make_claim(org, who["owner"], created_by=who["owner"])
    add_line(claim, merchant="Staples", account=office, tax_code=hst, amount=D("56.50"))
    add_line(claim, merchant="Bistro", account=meals, tax_code=hst, amount=D("113.00"))
    add_trip(claim, "100", dt.date(2026, 6, 2))
    return {"org": org, "claim": claim, "office": office, "meals": meals, "hst": hst, **who}


def posted(entry: Any) -> dict[str, tuple[Decimal, Decimal]]:
    out: dict[str, tuple[Decimal, Decimal]] = {}
    for line in JournalLine.objects.filter(entry=entry).select_related("account"):
        key = line.account.system_role or line.account.code
        debit, credit = out.get(key, (D("0"), D("0")))
        out[key] = (debit + line.debit, credit + line.credit)
    return out


def approved(setup: dict[str, Any], claim: ExpenseClaim | None = None) -> ExpenseClaim:
    submitted = flow.submit(claim or setup["claim"], setup["owner"])
    return flow.approve(submitted, setup["adviser"])


def test_approval_creates_and_posts_the_reimbursement_bill(setup: dict[str, Any]) -> None:
    claim = approved(setup)
    assert claim.status == ExpenseClaimStatus.APPROVED
    with org_context(setup["org"]):
        bill = Bill.objects.get(pk=claim.bill_id)
        assert (bill.status, bill.number) == (BillStatus.AWAITING_PAYMENT, "BILL-0001")
        assert bill.supplier_invoice_no == claim.number == "EXP-0001"
        assert bill.contact == claim.contact
        assert bill.total == D("56.50") + D("113.00") + D("73.00") == claim.total
        assert bill.amount_due == claim.total
        assert bill.date == timezone.localdate()
        assert bill.lines.count() == 3
        lines = posted(bill.journal_entry)
        assert lines["6080"] == (D("50.00"), D("0"))
        assert lines[setup["meals"].code] == (D("106.50"), D("0"))  # 100 + half the HST
        assert lines["6210"] == (D("73.00"), D("0"))  # mileage → Vehicle expenses, no tax
        assert lines[SystemRole.ITC_RECEIVABLE] == (D("13.00"), D("0"))  # 6.50 + 6.50
        assert lines[SystemRole.UNPAID_EXPENSE_CLAIMS] == (D("0"), claim.total)
        assert SystemRole.AP not in lines
        assert sum(d for d, _c in lines.values()) == sum(c for _d, c in lines.values())
        control = JournalLine.objects.get(
            entry=bill.journal_entry, account__system_role=SystemRole.UNPAID_EXPENSE_CLAIMS
        )
        assert control.contact_id == bill.contact_id
        assert AuditEvent.objects.filter(action="purchases.bill.reimbursement_posted").count() == 1


def test_employee_contact_created_once_then_reused(setup: dict[str, Any]) -> None:
    first = approved(setup)
    with org_context(setup["org"]):
        contact = first.contact
        assert contact is not None
        assert contact.roles == ["employee"]
        assert contact.display_name == "Dana Lee"
        person = ContactPerson.objects.get(contact=contact)
        assert (person.email, person.first_name, person.last_name) == (
            "dana@refined.ca",
            "Dana",
            "Lee",
        )
    again = make_claim(setup["org"], setup["owner"], created_by=setup["owner"], title="Taxis")
    add_line(again, merchant="Taxi", account=setup["office"], amount=D("20.00"))
    second = approved(setup, again)
    assert second.contact_id == contact.pk
    with org_context(setup["org"]):
        assert Bill.objects.get(pk=second.bill_id).number == "BILL-0002"


def test_existing_employee_contact_found_by_email(setup: dict[str, Any]) -> None:
    from tests.contact_helpers import contact

    with org_context(setup["org"]):
        known = contact(setup["org"], "Dana Lee (staff)", roles=["employee"])
        ContactPerson(organisation=setup["org"], contact=known, email="DANA@refined.ca").save()
    assert approved(setup).contact_id == known.pk


def test_locked_ap_period_refuses_the_approval_as_a_whole(setup: dict[str, Any]) -> None:
    from numo9.orgsettings.locks import LockedPeriod

    submitted = flow.submit(setup["claim"], setup["owner"])
    with org_context(setup["org"]):
        LockDate(
            organisation=setup["org"], module="ap", level="everyone", date=timezone.localdate()
        ).save()
    with pytest.raises(LockedPeriod):
        flow.approve(submitted, setup["adviser"])
    with org_context(setup["org"]):
        again = ExpenseClaim.objects.get(pk=submitted.pk)
        assert (again.status, again.bill_id) == (ExpenseClaimStatus.SUBMITTED, None)
        assert not Bill.objects.exists()


def test_unregistered_organisation_books_all_tax_as_cost(setup: dict[str, Any]) -> None:
    with org_context(setup["org"]):
        TaxRegistration.objects.all().delete()
    claim = approved(setup)
    with org_context(setup["org"]):
        lines = posted(Bill.objects.get(pk=claim.bill_id).journal_entry)
    assert SystemRole.ITC_RECEIVABLE not in lines
    assert lines["6080"] == (D("56.50"), D("0"))
