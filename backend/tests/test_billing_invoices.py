"""U-04-T08 — Invoice events → ``PlatformInvoice`` mirror + receipt.

Acceptance: the local rows equal the Stripe invoices.

Covers: finalized then paid then a re-delivered paid → one row per Stripe invoice with Stripe's
number, status, amounts (subtotal, tax, total, paid, due), period, issue/payment times, links and
attempts; several invoices → as many rows; the owner gets one receipt (in the app; by email —
Billing category) per paid invoice; a payment that fails moves the subscription past due with its
grace; a later paid renewal brings it back to active; an older event never overwrites a newer
one; the event records its organisation; the rows are the organisation's (scoped manager).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest

from numo9.billing.models import PlatformInvoice, StripeEvent
from numo9.entitlements.models import Subscription
from numo9.notifications.models import Notification
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.billing_helpers import (
    FakeGateway,
    deliver,
    owned_org,
    sold_package,
    stripe_event,
    stripe_invoice,
)

pytestmark = pytest.mark.django_db
T0 = 1_790_000_000


@pytest.fixture(autouse=True)
def packages() -> Iterator[None]:
    FakeGateway.reset()
    sold_package("growth")
    yield


@pytest.fixture
def org() -> Organisation:
    organisation: Organisation = owned_org()[0]
    Subscription._base_manager.filter(organisation=organisation).update(
        stripe_customer_id="cus_test_0001", stripe_subscription_id="sub_1", status="active"
    )
    return organisation


def rows(org: Organisation) -> list[PlatformInvoice]:
    with org_context(org):
        return list(PlatformInvoice.objects.order_by("stripe_invoice_id"))


def test_local_rows_equal_stripe_invoices(org: Organisation) -> None:
    deliver(stripe_event("invoice.finalized", stripe_invoice(status="open"), created=T0))
    (invoice,) = rows(org)
    assert (invoice.status, invoice.amount_due_cents, invoice.paid_at) == ("open", 5537, None)
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=T0 + 10))
    paid = stripe_event("invoice.paid", stripe_invoice(), created=T0 + 10)
    deliver(paid)
    deliver(
        stripe_event("invoice.paid", stripe_invoice("in_2", number="NUMO9-0002"), created=T0 + 20)
    )
    first, second = rows(org)
    assert [r.number for r in rows(org)] == ["NUMO9-0001", "NUMO9-0002"]
    assert (first.status, first.currency) == ("paid", "CAD")
    assert (first.subtotal_cents, first.tax_cents, first.total_cents) == (4900, 637, 5537)
    assert (first.amount_paid_cents, first.amount_due_cents) == (5537, 5537)
    assert first.period_start == dt.datetime.fromtimestamp(T0, tz=dt.UTC)
    assert first.issued_at == dt.datetime.fromtimestamp(1_790_000_100, tz=dt.UTC)
    assert first.paid_at == dt.datetime.fromtimestamp(1_790_000_200, tz=dt.UTC)
    assert first.pdf_url == "https://pay.stripe.com/invoice/in_1/pdf"
    assert first.hosted_url == "https://invoice.stripe.com/i/in_1"
    assert first.stripe_subscription_id == "sub_1" and first.organisation == org
    assert StripeEvent.objects.filter(organisation=org).count() == 4


def test_one_receipt_per_paid_invoice(org: Organisation) -> None:
    for created in (T0, T0 + 1):
        deliver(stripe_event("invoice.paid", stripe_invoice(), created=created))
    with org_context(org):
        receipts = list(Notification.objects.filter(title_key="notifications.billing.receipt"))
    assert len(receipts) == 1
    assert receipts[0].body_params["amount"] == "$55.37"
    assert receipts[0].body_params["number"] == "NUMO9-0001"
    assert rows(org)[0].receipt_sent_at is not None


def test_failure_then_recovery(org: Organisation) -> None:
    deliver(
        stripe_event(
            "invoice.payment_failed", stripe_invoice(status="open", attempt_count=1), created=T0
        )
    )
    s = Subscription._base_manager.get(organisation=org)
    assert s.status == "past_due"
    assert s.grace_until == dt.datetime.fromtimestamp(T0, tz=dt.UTC) + dt.timedelta(days=7)
    assert rows(org)[0].attempt_count == 1 and rows(org)[0].next_attempt_at is not None
    deliver(stripe_event("invoice.paid", stripe_invoice(attempt_count=2), created=T0 + 3 * 86400))
    s.refresh_from_db()
    assert s.status == "active" and s.grace_until is None
    assert rows(org)[0].status == "paid"


def test_older_event_never_overwrites(org: Organisation) -> None:
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=T0 + 10))
    deliver(stripe_event("invoice.finalized", stripe_invoice(status="open"), created=T0))
    assert rows(org)[0].status == "paid"
