"""U-04-T10 — Upgrade/downgrade with proration preview. Acceptance: preview = Stripe's upcoming.

Covers: an upgrade (higher per month; monthly → annual) previews Stripe's own amount for the item
moved to the new price at a proration date, and the change uses that same date with
``always_invoice`` (charged = preview); a downgrade charges nothing today, takes effect at the
period end (a scheduled change, replaced by a later choice, cancelled by an upgrade) and the job
moves the subscription to the new price without proration in the period's last hour, once;
refusals: same package and interval, not paying yet, unknown package, unsynced price; owner only
through the API; with stripe-mock (CI) the real client returns a preview invoice.
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator
from typing import Any

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from numo9.billing.changes import apply_due_changes, change, preview
from numo9.billing.gateway import StripeBillingApi
from numo9.billing.models import ScheduledChange
from numo9.entitlements.models import Subscription
from numo9.i18n.errors import CatalogueError
from numo9.packages.models import Package
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.billing_helpers import FakeGateway, owned_org, sold_package

pytestmark = pytest.mark.django_db
STRIPE_MOCK = os.environ.get("NUMO9_TEST_STRIPE_MOCK_URL", "")
PERIOD_END = timezone.now().replace(microsecond=0) + dt.timedelta(days=12)


@pytest.fixture(autouse=True)
def fake() -> Iterator[None]:
    FakeGateway.reset()
    FakeGateway.subscriptions = {"sub_1": {"id": "sub_1", "items": {"data": [{"id": "si_1"}]}}}
    FakeGateway.preview_amount = 2513
    sold_package("starter", 2900, 29000)
    sold_package("growth", 4900, 49000)
    sold_package("complete", 9900, 99000)
    with override_settings(NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway"):
        yield


@pytest.fixture
def org_owner() -> tuple[Organisation, Any]:
    org, owner = owned_org()
    Subscription._base_manager.filter(organisation=org).update(
        stripe_customer_id="cus_test_0001",
        stripe_subscription_id="sub_1",
        status="active",
        package=Package.objects.get(code="growth"),
        interval="month",
        current_period_end=PERIOD_END,
    )
    return org, owner


def calls(name: str) -> list[dict[str, Any]]:
    return [params for call, params in FakeGateway.calls if call == name]


def pending(org: Organisation) -> list[ScheduledChange]:
    with org_context(org):
        return list(ScheduledChange.objects.filter(applied_at=None, cancelled_at=None))


def test_upgrade_preview_equals_stripe_and_change_uses_the_same_date(
    org_owner: tuple[Organisation, Any],
) -> None:
    org, _ = org_owner
    shown = preview(org, "complete", "month")
    assert (shown.kind, shown.charged_today_cents, shown.amount_cents) == ("upgrade", 2513, 9900)
    asked = calls("preview_change")[0]
    assert asked == {
        "customer": "cus_test_0001",
        "subscription": "sub_1",
        "item": "si_1",
        "price": "price_complete_month",
        "proration_date": shown.proration_date,
    }
    done = change(org, "complete", "month", shown.proration_date)
    assert done.kind == "upgrade"
    applied = calls("change_price")[0]
    assert applied["proration_behavior"] == "always_invoice"
    assert (
        applied["proration_date"] == shown.proration_date
        and applied["price"] == "price_complete_month"
    )
    assert pending(org) == []


def test_monthly_to_annual_is_an_upgrade(org_owner: tuple[Organisation, Any]) -> None:
    assert preview(org_owner[0], "growth", "year").kind == "upgrade"


def test_downgrade_at_period_end(org_owner: tuple[Organisation, Any]) -> None:
    org, _ = org_owner
    shown = preview(org, "starter", "month")
    assert (shown.kind, shown.charged_today_cents, shown.effective_at) == (
        "downgrade",
        0,
        PERIOD_END,
    )
    assert calls("preview_change") == []
    change(org, "starter", "month")
    (scheduled,) = pending(org)
    assert (scheduled.package.code, scheduled.interval, scheduled.effective_at) == (
        "starter",
        "month",
        PERIOD_END,
    )
    assert calls("change_price") == []
    assert apply_due_changes(PERIOD_END - dt.timedelta(hours=2)) == 0
    assert apply_due_changes(PERIOD_END - dt.timedelta(minutes=30)) == 1
    applied = calls("change_price")[0]
    assert applied["proration_behavior"] == "none" and applied["price"] == "price_starter_month"
    assert apply_due_changes(PERIOD_END) == 0
    assert pending(org) == []


def test_later_choice_replaces_and_upgrade_cancels_the_downgrade(
    org_owner: tuple[Organisation, Any],
) -> None:
    org, _ = org_owner
    change(org, "starter", "month")
    Subscription._base_manager.filter(organisation=org).update(interval="year")
    change(org, "starter", "year")
    (scheduled,) = pending(org)
    assert scheduled.interval == "year"
    change(org, "complete", "year")
    assert pending(org) == []


def test_refusals(org_owner: tuple[Organisation, Any]) -> None:
    org, _ = org_owner
    for args, code in [
        (("growth", "month"), "billing.no_change"),
        (("nope", "month"), "billing.package_unknown"),
    ]:
        with pytest.raises(CatalogueError) as refused:
            preview(org, *args)
        assert refused.value.get_codes() == code
    Subscription._base_manager.filter(organisation=org).update(stripe_subscription_id="")
    with pytest.raises(CatalogueError) as not_paying:
        change(org, "complete", "month")
    assert not_paying.value.get_codes() == "billing.not_paying"


def test_api_owner_only(org_owner: tuple[Organisation, Any]) -> None:
    org, owner = org_owner
    client = Client()
    client.force_login(owner)
    base = f"/api/v1/o/{org.public_id}/billing/change"
    shown = client.get(f"{base}/preview?package=complete&interval=month")
    assert shown.status_code == 200 and shown.json()["charged_today_cents"] == 2513
    done = client.post(
        base,
        {
            "package": "complete",
            "interval": "month",
            "proration_date": shown.json()["proration_date"],
        },
        content_type="application/json",
    )
    assert done.status_code == 200 and done.json()["kind"] == "upgrade"
    from numo9.accounts.models import User
    from numo9.tenancy.models import OrganisationMember

    admin = User.objects.create_user("admin@maple.ca", password="x" * 12)
    OrganisationMember.objects.create(organisation=org, user=admin, role="admin")
    other = Client()
    other.force_login(admin)
    assert other.get(f"{base}/preview?package=complete&interval=month").status_code == 403
    assert (
        other.post(
            base, {"package": "complete", "interval": "month"}, content_type="application/json"
        ).status_code
        == 403
    )


@pytest.mark.skipif(not STRIPE_MOCK, reason="needs stripe-mock (NUMO9_TEST_STRIPE_MOCK_URL)")
def test_stripe_mock_preview_invoice() -> None:
    with override_settings(STRIPE_SECRET_KEY="sk_test_" + "x" * 24, STRIPE_API_BASE=STRIPE_MOCK):
        invoice = StripeBillingApi().preview_change(
            customer="cus_123",
            subscription="sub_123",
            item="si_123",
            price="price_123",
            proration_date=int(timezone.now().timestamp()),
        )
    assert "amount_due" in invoice
