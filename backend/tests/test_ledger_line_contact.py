"""C-03-T02 — a contact on each journal line (organisation-scoped), indexed (organisation, contact).

Acceptance: a line saves with a contact of the same organisation; another organisation's contact
(or a deleted one, or a made-up id) is refused naming the line; the contact index exists; the
tenant sweep passes.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from numo9.ledger.models import JournalLine
from numo9.ledger.services import post_journal, save_draft
from numo9.ledger.validation import JournalInvalid, JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


def accounts(org: Organisation) -> tuple[object, object]:
    return (
        account(org, "1200", "Accounts receivable", subtype="current_asset"),
        account(org, "4000", "Sales", subtype="revenue"),
    )


def journal(ar: object, sales: object, customer: object) -> JournalSpec:
    return JournalSpec(
        date=dt.date(2026, 6, 15),
        lines=(
            LineSpec(ar, debit=Decimal("113.00"), contact=customer),  # type: ignore[arg-type]
            LineSpec(sales, credit=Decimal("113.00")),  # type: ignore[arg-type]
        ),
    )


def test_line_keeps_a_contact_of_the_same_organisation() -> None:
    maple = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(maple):
        cedar = contact(maple, "Cedar Roofing Co.")
        entry = post_journal(journal(*accounts(maple), cedar))
        line = JournalLine.objects.get(entry=entry, line_no=1)
        assert line.contact_id == cedar.pk
        assert JournalLine.objects.filter(contact=cedar).count() == 1


@pytest.mark.parametrize("which", ["other_org", "deleted", "made_up"])
def test_other_organisations_or_missing_contact_is_refused(which: str) -> None:
    maple = Organisation.objects.create(name="Maple Bakery Inc.")
    birch = Organisation.objects.create(name="Birch Garage Inc.")
    with org_context(birch):
        theirs = contact(birch, "Birchwood Lumber")
    with org_context(maple):
        mine = contact(maple, "Cedar Roofing Co.")
        if which == "deleted":
            type(mine)._base_manager.filter(pk=mine.pk).update(deleted_at=timezone.now())
        value = {"other_org": theirs, "deleted": mine, "made_up": 987654}[which]
        ar, sales = accounts(maple)
        for write in (post_journal, save_draft):
            with pytest.raises(JournalInvalid) as raised:
                write(journal(ar, sales, value))
            assert [e.code for e in raised.value.error_list] == ["ledger.journal.contact_missing"]
            assert "Line 1" in raised.value.messages[0]


def test_contact_index_and_sweep() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'ledger_line_contact_idx'"
        )
        (definition,) = cursor.fetchone()
    assert "(organisation_id, contact_id)" in definition
    call_command("tenant_sweep", stdout=StringIO())  # raises on any leak
