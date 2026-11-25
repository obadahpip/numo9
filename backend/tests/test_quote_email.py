"""D-02-T15 — quote emails: sending a quote queues one email per recipient with the PDF and the
public link (and moves it to Sent); accepting or declining notifies whoever sent it once (an
accept twice notifies once)."""

from __future__ import annotations

import datetime as dt
from typing import Any
from unittest import mock

import pytest

from numo9.contacts.models import ContactPerson
from numo9.notifications import mail as outgoing
from numo9.notifications.models import EmailMessage, Notification
from numo9.sales import quotes as q
from numo9.sales.quote_email import send_quote
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
TODAY = dt.date.today()


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books("Maple Leaf Supply Ltd.")
    books["owner"] = people(books["org"])["owner"]
    with org_context(books["org"]):
        for name, email in (("Ana", "ap@oncustomer.ca"), ("Bo", "bo@oncustomer.ca")):
            ContactPerson.objects.create(
                organisation=books["org"],
                contact=books["customers"]["ON"],
                first_name=name,
                email=email,
                include_in_emails=True,
            )
    return books


@pytest.fixture
def captured() -> Any:
    sent: list[Any] = []
    with mock.patch.object(
        outgoing.send_email, "apply_async", lambda args=None, **kw: sent.append(args)
    ):
        yield sent


def test_send_one_email_per_recipient(
    books: dict[str, Any], s3: str, captured: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    item = quote(
        books,
        [("1", "100", "sales.ON.standard")],
        date=TODAY,
        expiry=TODAY + dt.timedelta(days=30),
        title="Shelving",
    )
    with django_capture_on_commit_callbacks(execute=True):
        messages = send_quote(item, books["owner"], message="As discussed.")
    assert len(messages) == 2 and len(captured) == 2
    rows = list(EmailMessage.platform_messages.filter(kind="sales.quote").order_by("to_email"))
    assert [r.to_email for r in rows] == ["ap@oncustomer.ca", "bo@oncustomer.ca"]
    assert rows[0].subject == "Quote QU-0001 from Maple Leaf Supply Ltd."
    assert "Total: $113.00" in rows[0].text_body and "/q/" in rows[0].text_body
    item.refresh_from_db()
    assert item.status == "sent"


def test_accepted_and_declined_notify_once(
    books: dict[str, Any], s3: str, captured: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    accepted = quote(books, [("1", "100", "")], date=TODAY, expiry=TODAY + dt.timedelta(days=30))
    declined = quote(books, [("1", "50", "")], date=TODAY, expiry=TODAY + dt.timedelta(days=30))
    with django_capture_on_commit_callbacks(execute=True):
        q.send(accepted, books["owner"])
        q.send(declined, books["owner"])
        q.accept(accepted)
        q.accept(accepted)  # twice: one notification
        q.decline(declined, "Found a cheaper supplier")
    with org_context(books["org"]):
        events = list(
            Notification.objects.filter(recipient=books["owner"]).values_list(
                "title_key", flat=True
            )
        )
    assert sorted(events) == [
        "notifications.sales.quote.accepted",
        "notifications.sales.quote.declined",
    ]
