"""E-04-T05 — expense claim workflow: submit (numbered EXP-0001, mileage priced, total), approve
or reject; the claimant / submitter can never approve their own claim; approval limits (A-03);
receipt required above the organisation's threshold; audit events."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.ledger.models import Account
from numo9.orgsettings.service import get_settings
from numo9.purchases import expense_claims as flow
from numo9.purchases.models import ExpenseClaimStatus
from numo9.rbac.approvals import ApprovalLimitExceeded
from numo9.rbac.models import ApprovalLimit
from numo9.tenancy.context import org_context
from tests.expense_helpers import add_line, add_trip, expense_org, make_claim

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def setup() -> dict[str, Any]:
    org, who = expense_org()
    with org_context(org):
        office = Account.objects.filter(type="expense").order_by("code")[0]
        ApprovalLimit.objects.create(
            user=who["adviser"], doc_type="expense_claim", max_amount=D("500")
        )
    claim = make_claim(org, who["owner"], created_by=who["owner"])
    add_line(claim, merchant="Staples", account=office, amount=D("56.50"))
    add_trip(claim, "100", dt.date(2026, 6, 2))
    return {"org": org, "claim": claim, "office": office, **who}


def test_submit_numbers_prices_and_totals(setup: dict[str, Any]) -> None:
    claim = flow.submit(setup["claim"], setup["owner"])
    assert (claim.status, claim.number) == (ExpenseClaimStatus.SUBMITTED, "EXP-0001")
    assert claim.total == D("56.50") + D("73.00")
    assert claim.submitted_by == setup["owner"] and claim.submitted_at is not None
    with org_context(setup["org"]):
        assert AuditEvent.objects.filter(action="purchases.expenseclaim.submitted").count() == 1


def test_submitter_cannot_approve_own_claim(setup: dict[str, Any]) -> None:
    claim = flow.submit(setup["claim"], setup["owner"])
    with org_context(setup["org"]):
        ApprovalLimit.objects.create(
            user=setup["owner"], doc_type="expense_claim", max_amount=D("9999")
        )
    with pytest.raises(flow.ExpenseClaimRefused) as err:
        flow.approve(claim, setup["owner"])
    assert err.value.code == "purchases.expense.self_approval"
    with pytest.raises(flow.ExpenseClaimRefused):
        flow.reject(claim, setup["owner"], "no")


def test_someone_else_submitting_for_the_claimant_cannot_approve(setup: dict[str, Any]) -> None:
    claim = flow.submit(setup["claim"], setup["adviser"])  # entered on the owner's behalf
    with pytest.raises(flow.ExpenseClaimRefused) as err:
        flow.approve(claim, setup["adviser"])
    assert err.value.code == "purchases.expense.self_approval"


def test_approve_within_limit(setup: dict[str, Any]) -> None:
    claim = flow.approve(flow.submit(setup["claim"], setup["owner"]), setup["adviser"])
    assert claim.status == ExpenseClaimStatus.APPROVED and claim.decided_by == setup["adviser"]
    with pytest.raises(flow.ExpenseClaimRefused):  # only once
        flow.approve(claim, setup["adviser"])


def test_approval_limit_exceeded(setup: dict[str, Any]) -> None:
    add_line(setup["claim"], merchant="Hotel", account=setup["office"], amount=D("600"))
    claim = flow.submit(setup["claim"], setup["owner"])
    with pytest.raises(ApprovalLimitExceeded):
        flow.approve(claim, setup["adviser"])
    claim.refresh_from_db()
    assert claim.status == ExpenseClaimStatus.SUBMITTED


def test_reject_needs_a_reason_then_resubmit_keeps_number(setup: dict[str, Any]) -> None:
    claim = flow.submit(setup["claim"], setup["owner"])
    with pytest.raises(flow.ExpenseClaimRefused) as err:
        flow.reject(claim, setup["adviser"], "  ")
    assert err.value.code == "purchases.expense.reason_required"
    claim = flow.reject(claim, setup["adviser"], "Missing the hotel folio")
    assert (claim.status, claim.rejection_reason) == (
        ExpenseClaimStatus.REJECTED,
        "Missing the hotel folio",
    )
    again = flow.submit(claim, setup["owner"])
    assert (again.status, again.number, again.rejection_reason) == ("submitted", "EXP-0001", "")


def test_submit_rules(setup: dict[str, Any]) -> None:
    org = setup["org"]
    empty = make_claim(org, setup["owner"])
    with pytest.raises(flow.ExpenseClaimRefused) as err:
        flow.submit(empty, setup["owner"])
    assert err.value.code == "purchases.expense.empty"
    no_category = make_claim(org, setup["owner"])
    add_line(no_category, merchant="Taxi", amount=D("20"))
    with pytest.raises(flow.ExpenseClaimRefused) as err:
        flow.submit(no_category, setup["owner"])
    assert err.value.code == "purchases.expense.category_missing"
    with org_context(org):
        row = get_settings(org)
        row.expense_receipt_required_above = D("50.00")
        row.save()
    with pytest.raises(flow.ExpenseClaimRefused) as err:
        flow.submit(setup["claim"], setup["owner"])  # 56.50 receipt without the image
    assert err.value.code == "purchases.expense.receipt_required"
    with org_context(org):
        row.expense_receipt_required_above = D("100.00")
        row.save()
    claim = flow.submit(setup["claim"], setup["owner"])
    assert claim.number == "EXP-0001"  # the refused submits took no number
    with pytest.raises(flow.ExpenseClaimRefused) as err:
        flow.submit(setup["claim"], setup["owner"])
    assert err.value.code == "purchases.expense.not_draft"
