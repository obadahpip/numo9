"""U-07-T06 — reset service: wipe the demo's data FK-safely, re-clone the seed.

Acceptance (data validation): after the visitor changed and added data — contacts edited and
added, a journal posted, activity — a reset gives the pristine hash of the template;
journal numbering starts again at 2 after the opening journal; members are kept; a real
organisation can't be reset; the ledger stays append-only for real organisations.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from numo9.accounts.models import User
from numo9.contacts.activity import emit
from numo9.contacts.models import Contact
from numo9.demo.cloning import CloneError, create_demo, pristine_hash, template_for
from numo9.demo.reset import reset_demo
from numo9.ledger.models import Account, JournalEntry
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = [pytest.mark.django_db, pytest.mark.data_validation]


def _scribble(demo: Organisation) -> None:
    with org_context(demo):
        first = Contact.objects.order_by("pk").first()
        assert first is not None
        first.display_name = "Renamed by the visitor"
        first.save()
        Contact(organisation=demo, display_name="Visitor Co.", roles=["customer"]).save()
        bank, sales = Account.objects.get(code="1010"), Account.objects.get(code="4000")
        post_journal(
            JournalSpec(
                date=dt.date(2026, 2, 1),
                narration="Cash sale",
                lines=[
                    LineSpec(account=bank, debit=Decimal("100")),
                    LineSpec(account=sales, credit=Decimal("100")),
                ],
            ),
            organisation=demo,
            user=None,
        )
        emit(first, "note", title="Called the customer")


def test_reset_restores_the_pristine_seed() -> None:
    template = template_for()
    demo = create_demo()
    user = User.objects.create_user("visitor@demo.example", password=None)
    OrganisationMember.objects.create(organisation=demo, user=user, role="owner")
    _scribble(demo)
    assert pristine_hash(demo) != template.pristine_hash
    steps: list[str] = []
    assert reset_demo(demo, progress=lambda _p, label: steps.append(label)) == (
        template.pristine_hash
    )
    assert steps == ["template", "wipe", "clone", "verify", "done"]
    with org_context(demo):
        assert Contact.objects.count() == 25
        assert not Contact.objects.filter(display_name="Visitor Co.").exists()
        # The opening balances (1) and the banking sample transactions (F-01-T15).
        assert sorted(JournalEntry.objects.values_list("number", flat=True)) == list(range(1, 8))
        bank, sales = Account.objects.get(code="1010"), Account.objects.get(code="4000")
        entry = post_journal(
            JournalSpec(
                date=dt.date(2026, 2, 1),
                lines=[
                    LineSpec(account=bank, debit=Decimal("5")),
                    LineSpec(account=sales, credit=Decimal("5")),
                ],
            ),
            organisation=demo,
            user=None,
        )
        assert entry.number == 8  # after the 7 seeded journals: the sequence was cloned too
    assert OrganisationMember.objects.filter(organisation=demo, user=user).exists()


def test_reset_twice_is_still_pristine() -> None:
    template = template_for()
    demo = create_demo()
    reset_demo(demo)
    assert reset_demo(demo) == template.pristine_hash


def test_real_organisations_stay_append_only() -> None:
    real = Organisation.objects.create(name="Real Ltd.")
    with pytest.raises(CloneError):
        reset_demo(real)
    with org_context(real):
        from tests.ledger_helpers import account

        cash = account(real, "1000", "Cash", subtype="current_asset")
        sales = account(real, "4000", "Sales", subtype="revenue")
        post_journal(
            JournalSpec(
                date=dt.date(2026, 2, 1),
                lines=[
                    LineSpec(account=cash, debit=Decimal("5")),
                    LineSpec(account=sales, credit=Decimal("5")),
                ],
            ),
            organisation=real,
            user=None,
        )
    # Even naming the real organisation in the setting does not unlock its books.
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT set_config('numo9.demo_wipe', %s, true)", [str(real.pk)])
        cursor.execute("DELETE FROM ledger_journalentry WHERE organisation_id = %s", [real.pk])
    with org_context(real):
        assert JournalEntry.objects.count() == 1
