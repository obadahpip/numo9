"""E-04-T01 — ``ExpenseClaim`` and ``ExpenseClaimLine``: receipt and mileage lines, a draft has
no number, a submitted claim has one (unique per organisation), the fields match the line type,
the total is the lines' sum."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.purchases.models import (
    ExpenseClaim,
    ExpenseClaimLine,
    ExpenseClaimStatus,
    ExpenseLineKind,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db
DAY = dt.date(2026, 6, 15)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


@pytest.fixture
def claim(org: Organisation) -> ExpenseClaim:
    owner = people(org)["owner"]
    with org_context(org):
        item = ExpenseClaim(organisation=org, claimant=owner, title="Client visit, June")
        item.save()
    return item


def line(claim: ExpenseClaim, **fields: Any) -> ExpenseClaimLine:
    with org_context(claim.organisation):
        item = ExpenseClaimLine(organisation=claim.organisation, claim=claim, date=DAY, **fields)
        item.save()
    return item


def refused(make: Any) -> bool:
    try:
        with transaction.atomic():
            make()
    except IntegrityError:
        return True
    return False


def test_receipt_and_mileage_lines_and_the_total(claim: ExpenseClaim, org: Organisation) -> None:
    with org_context(org):
        meals = Account.objects.filter(type="expense").order_by("code")[0]
    receipt = line(claim, merchant="Bistro 21", account=meals, amount=Decimal("56.50"), position=1)
    trip = line(
        claim,
        kind=ExpenseLineKind.MILEAGE,
        from_place="Office",
        to_place="Client site, Kingston",
        distance_km=Decimal("262.4"),
        amount=Decimal("188.93"),
        rate_detail=[{"km": "262.4", "rate": "0.72"}],
        position=2,
    )
    assert (receipt.kind, str(receipt)) == ("receipt", "Bistro 21 56.50")
    assert str(trip) == "262.4 km Office → Client site, Kingston"
    with org_context(org):
        assert [row.position for row in claim.lines.all()] == [1, 2]
        assert claim.recalculate() == Decimal("245.43")
        claim.save()
        stored = ExpenseClaim.objects.get(pk=claim.pk)
    assert (stored.total, stored.status, stored.number) == (Decimal("245.43"), "draft", "")
    assert str(stored) == "Draft expense claim" and stored.currency == "CAD"


def test_fields_must_match_the_line_type(claim: ExpenseClaim) -> None:
    mileage = {"kind": ExpenseLineKind.MILEAGE}
    assert refused(lambda: line(claim, **mileage))  # mileage without kilometres
    assert refused(lambda: line(claim, **mileage, distance_km=Decimal("0")))
    assert refused(lambda: line(claim, **mileage, distance_km=Decimal("10"), merchant="Shell"))
    assert refused(lambda: line(claim, merchant="Shell", distance_km=Decimal("10")))  # a receipt
    assert refused(lambda: line(claim, kind="per_diem"))
    assert refused(lambda: line(claim, amount=Decimal("-1.00")))


def test_a_submitted_claim_is_numbered_once(claim: ExpenseClaim, org: Organisation) -> None:
    owner = claim.claimant

    def submit(item: ExpenseClaim, number: str) -> None:
        with org_context(org):
            item.status = ExpenseClaimStatus.SUBMITTED
            item.number = number
            item.submitted_by = owner
            item.submitted_at = timezone.now() if number else None
            item.save()

    assert refused(lambda: submit(claim, ""))  # submitted without a number
    claim.refresh_from_db()
    submit(claim, "EXP-0001")
    assert str(claim) == "EXP-0001" and claim.audit_label() == "EXP-0001 — Client visit, June"
    with org_context(org):
        other = ExpenseClaim(organisation=org, claimant=owner, title="July")
        other.save()
    assert refused(lambda: submit(other, "EXP-0001"))  # the same number twice
    other.refresh_from_db()
    with org_context(org):
        second_draft = ExpenseClaim(organisation=org, claimant=owner, title="August")
        second_draft.save()  # several drafts without a number are fine
        assert ExpenseClaim.objects.filter(number="").count() == 2
    elsewhere = Organisation.objects.create(name="Other Ltd.")
    with org_context(elsewhere):
        twin = ExpenseClaim(
            organisation=elsewhere,
            claimant=owner,
            title="Theirs",
            status=ExpenseClaimStatus.SUBMITTED,
            number="EXP-0001",
            submitted_at=timezone.now(),
        )
        twin.save()  # numbers are per organisation
    with org_context(org):
        assert not ExpenseClaim.objects.filter(title="Theirs").exists()  # tenant-scoped
