"""U-08-T03 — founding slot allocated by the first-payment handler (U-04-T08), same transaction.

Acceptance: a replay does not allocate twice; a $0 (trial) invoice allocates nothing; a handler
that fails after the allocation leaves no slot and the counter unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.billing.processing import EventFailed
from numo9.entitlements.models import Subscription
from numo9.founding.models import FoundingCounter, FoundingSlot
from numo9.tenancy.models import Organisation
from tests.billing_helpers import FakeGateway, deliver, owned_org, sold_package, stripe_event
from tests.billing_helpers import stripe_invoice as invoice

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


def test_first_paid_invoice_allocates_a_slot(org: Organisation) -> None:
    deliver(stripe_event("invoice.paid", invoice(), created=T0))
    slot = FoundingSlot.objects.get(organisation=org)
    assert (slot.slot_no, slot.payment_ref) == (1, "in_1")
    assert FoundingCounter.current().allocated == 1


def test_replay_and_later_invoices_do_not_allocate_twice(org: Organisation) -> None:
    deliver(stripe_event("invoice.paid", invoice(), created=T0))
    deliver(stripe_event("invoice.paid", invoice(), created=T0 + 1))  # re-sent event
    deliver(stripe_event("invoice.paid", invoice("in_2", number="NUMO9-0002"), created=T0 + 99))
    assert FoundingSlot.objects.filter(organisation=org).count() == 1
    assert FoundingCounter.current().allocated == 1


def test_zero_amount_invoice_is_not_a_payment(org: Organisation) -> None:
    deliver(stripe_event("invoice.paid", invoice(total=0, subtotal=0), created=T0))
    deliver(stripe_event("invoice.finalized", invoice("in_9", status="open"), created=T0 + 1))
    assert not FoundingSlot.objects.exists()
    assert FoundingCounter.current().allocated == 0


def test_failed_handler_rolls_the_slot_back(
    org: Organisation, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("mail down")

    monkeypatch.setattr("numo9.notifications.services.notify", boom)
    with pytest.raises(EventFailed):
        deliver(stripe_event("invoice.paid", invoice(), created=T0))
    assert not FoundingSlot.objects.exists()
    assert FoundingCounter.current().allocated == 0
