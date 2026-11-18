"""B-02-T02 — ``ActivityEvent`` model and emitter API for modules.

Acceptance: events are ordered by time (newest first). ``emit`` records type, title, the record,
amount in the contact's currency, when and who; ``timeline`` filters by type and dates; a sent
statement appears through the ``statement_sent`` signal; unknown types are refused; a merged
contact's events move to the survivor.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest

from numo9.contacts.activity import emit, timeline
from numo9.contacts.merge import merge_contacts
from numo9.contacts.models import ActivityEvent, StatementSend
from numo9.contacts.statements import statement_sent
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db
UTC = dt.UTC


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def test_events_newest_first_and_filters(org: Organisation) -> None:
    maple = contact(org, "Maple Leaf Supply Ltd.")
    emit(
        maple,
        "invoice",
        "INV-0001",
        amount=Decimal("100.00"),
        occurred_at=dt.datetime(2026, 3, 1, tzinfo=UTC),
    )
    emit(
        maple,
        "payment",
        "Payment",
        amount=Decimal("-100.00"),
        occurred_at=dt.datetime(2026, 3, 9, tzinfo=UTC),
    )
    emit(maple, "note", "Called about the order", occurred_at=dt.datetime(2026, 3, 5, tzinfo=UTC))
    assert [e.title for e in timeline(maple)] == ["Payment", "Called about the order", "INV-0001"]
    assert [e.type for e in timeline(maple, types=["invoice", "payment"])] == ["payment", "invoice"]
    assert [
        e.title for e in timeline(maple, start=dt.date(2026, 3, 2), end=dt.date(2026, 3, 6))
    ] == ["Called about the order"]
    assert timeline(maple)[0].currency == "CAD"
    with pytest.raises(ValueError, match="Unknown activity type"):
        emit(maple, "telegram", "?")


def test_a_sent_statement_is_on_the_timeline(org: Organisation) -> None:
    maple = contact(org, "Maple Leaf Supply Ltd.")
    send = StatementSend.objects.create(
        organisation=org,
        contact=maple,
        kind="outstanding",
        as_at=dt.date(2026, 3, 31),
        amount_due=Decimal("250.00"),
        language="en-ca",
        recipients=["dana@m.ca"],
        subject="Statement",
        file_key="k",
        file_name="s.pdf",
    )
    statement_sent.send(sender=StatementSend, send=send)
    event = timeline(maple).get()
    assert (event.type, event.amount, event.ref_id) == (
        "statement",
        Decimal("250.00"),
        str(send.public_id),
    )
    assert "dana@m.ca" in event.title


def test_merged_contacts_events_move_to_the_survivor(org: Organisation) -> None:
    survivor, merged = contact(org, "Maple Leaf Supply Ltd."), contact(org, "Maple Suply")
    emit(merged, "note", "Old note")
    merge_contacts(survivor, merged)
    assert ActivityEvent.objects.get().contact == survivor
