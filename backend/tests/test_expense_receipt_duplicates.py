"""E-04-T07 — the same receipt image twice (same SHA-256) → a warning naming the claim where it
was used, across claimants; never a block; no warning for distinct images or lines without one."""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.ledger.models import Account
from numo9.purchases import expense_claims as flow
from numo9.purchases.receipt_duplicates import claim_warnings, duplicates_of
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.expense_helpers import add_line, expense_org, make_claim
from tests.journal_helpers import document

pytestmark = pytest.mark.django_db
SHA = "ab" * 32


def test_same_image_twice_warns() -> None:
    org, who = expense_org()
    with org_context(org):
        office = Account.objects.filter(type="expense").order_by("code")[0]
        first = document(org, "IMG_0001.jpg", sha256=SHA)
        again = document(org, "IMG_0001 (1).jpg", sha256=SHA)
        other = document(org, "IMG_0002.jpg", sha256="cd" * 32)
    earlier = make_claim(org, who["adviser"], title="May")
    used = add_line(earlier, merchant="Bistro", account=office, amount=Decimal("40"), receipt=first)
    claim = make_claim(org, who["owner"], title="June")
    dup = add_line(claim, merchant="Bistro", account=office, amount=Decimal("40"), receipt=again)
    add_line(claim, merchant="Taxi", account=office, amount=Decimal("15"), receipt=other)
    add_line(claim, merchant="Parking", account=office, amount=Decimal("5"))
    with org_context(org):
        assert list(duplicates_of(dup)) == [used]
        warnings = claim_warnings(claim)
    assert len(warnings) == 1
    assert warnings[0]["code"] == "purchases.expense.duplicate_receipt"
    assert warnings[0]["line"] == str(dup.public_id)
    assert "Sam Patel" in warnings[0]["message"]
    assert warnings[0]["claims"] == [str(earlier.public_id)]
    # a warning only: the claim can still be submitted
    assert flow.submit(claim, who["owner"]).status == "submitted"


def test_other_organisation_not_compared() -> None:
    org, who = expense_org()
    other_org = Organisation.objects.create(name="Other Ltd.")
    with org_context(other_org):
        doc = document(other_org, "a.jpg", sha256=SHA)
    add_line(make_claim(other_org, who["owner"]), merchant="X", amount=Decimal("1"), receipt=doc)
    with org_context(org):
        mine = document(org, "a.jpg", sha256=SHA)
    claim = make_claim(org, who["owner"])
    line = add_line(claim, merchant="X", amount=Decimal("1"), receipt=mine)
    with org_context(org):
        assert not duplicates_of(line).exists()
        assert claim_warnings(claim) == []
