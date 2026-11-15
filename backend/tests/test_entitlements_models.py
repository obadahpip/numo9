"""U-03-T02, T03 — Subscription skeleton and EntitlementOverride models.

Acceptance: one active subscription per organisation (partial unique index); an expired override
is ignored. Also: a cancelled subscription frees the slot (history kept); past-due needs a grace
end; draft packages can't be subscribed to; the override JSON is checked; status changes stamp
the time and mirror the organisation's status; overrides need a reason and a future end; every
change is in the organisation's audit log; the subscription source answers packages (U-02).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.catalogue.models import Product
from numo9.entitlements.models import (
    EntitlementOverride,
    StatusReason,
    Subscription,
    SubscriptionStatus,
    active_overrides,
    current_subscription,
)
from numo9.entitlements.source import Subscriptions
from numo9.packages.models import PackageStatus
from numo9.packages.subscriptions import get_source
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationStatus
from tests.entitlement_helpers import grant, package, subscribe

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


def codes(excinfo: pytest.ExceptionInfo[ValidationError]) -> dict[str, list[str]]:
    return {f: [e.code or "" for e in errs] for f, errs in excinfo.value.error_dict.items()}


# ---- Subscription (T02) ------------------------------------------------------------------------


def test_subscription_skeleton_fields(org: Organisation) -> None:
    growth = package("growth", ["accounting"])
    end = timezone.now() + timedelta(days=30)
    item = subscribe(
        org,
        growth,
        current_period_end=end,
        founding=True,
        override={"products": ["payroll"], "limits": {"max_org_users": 20}},
    )
    item.refresh_from_db()
    assert (item.package, item.status, item.current_period_end) == (growth, "active", end)
    assert item.founding is True
    assert item.extra_products == ["payroll"]
    assert current_subscription(org) == item


def test_one_current_subscription_per_organisation(org: Organisation) -> None:
    growth = package("growth", ["accounting"])
    subscribe(org, growth)
    with pytest.raises(ValidationError) as excinfo:
        subscribe(org, growth, status=SubscriptionStatus.TRIALING)
    assert codes(excinfo) == {"status": ["entitlements.subscription.one_current"]}


def test_database_refuses_a_second_current_subscription(org: Organisation) -> None:
    growth = package("growth", ["accounting"])
    subscribe(org, growth)
    with pytest.raises(IntegrityError), transaction.atomic():
        Subscription._base_manager.bulk_create(
            [Subscription(organisation=org, package=growth, status=SubscriptionStatus.READ_ONLY)]
        )


def test_cancelled_subscriptions_stay_as_history(org: Organisation) -> None:
    growth = package("growth", ["accounting"])
    first = subscribe(org, growth)
    first.status = SubscriptionStatus.CANCELLED
    first.status_reason = StatusReason.CANCELLED
    first.save()
    assert current_subscription(org) == first  # the latest cancelled one when none is live
    second = subscribe(org, growth)  # the slot is free again
    assert current_subscription(org) == second
    with org_context(org):
        assert Subscription.objects.count() == 2


def test_past_due_needs_a_grace_end(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        subscribe(
            org, package("growth", ["accounting"]), SubscriptionStatus.PAST_DUE, grace_until=None
        )
    assert codes(excinfo) == {"grace_until": ["entitlements.subscription.grace_required"]}


def test_draft_package_cannot_be_subscribed_to(org: Organisation) -> None:
    draft = package("draft_plan", ["accounting"], status=PackageStatus.DRAFT)
    with pytest.raises(ValidationError) as excinfo:
        subscribe(org, draft)
    assert codes(excinfo) == {"package": ["entitlements.subscription.package_draft"]}


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"colour": "red"}, "entitlements.subscription.override_keys"),
        ({"products": "payroll"}, "entitlements.subscription.override_products"),
        ({"products": ["nope"]}, "entitlements.subscription.override_unknown_product"),
    ],
)
def test_override_json_is_checked(
    org: Organisation, override: dict[str, object], code: str
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        subscribe(org, None, SubscriptionStatus.TRIALING, override=override)
    assert codes(excinfo) == {"override": [code]}


def test_status_change_is_stamped_and_mirrored_on_the_organisation(org: Organisation) -> None:
    item = subscribe(org, None, SubscriptionStatus.TRIALING)
    org.refresh_from_db()
    assert org.status == OrganisationStatus.TRIAL
    before = item.status_changed_at
    item.status = SubscriptionStatus.PAST_DUE
    item.grace_until = timezone.now() + timedelta(days=7)
    item.save()
    org.refresh_from_db()
    assert org.status == OrganisationStatus.GRACE
    assert item.status_changed_at > before
    item.status = SubscriptionStatus.READ_ONLY
    item.save(update_fields=["status", "updated_at"])
    org.refresh_from_db()
    assert org.status == OrganisationStatus.READ_ONLY


def test_subscription_changes_are_audited_in_the_organisation(org: Organisation) -> None:
    item = subscribe(org, package("growth", ["accounting"]))
    item.status = SubscriptionStatus.PAST_DUE
    item.grace_until = timezone.now() + timedelta(days=7)
    item.save()
    with org_context(org):
        events = list(
            AuditEvent.objects.filter(object_type="entitlements.Subscription").order_by("id")
        )
    assert [e.action for e in events] == [
        "entitlements.subscription.created",
        "entitlements.subscription.updated",
    ]
    assert {e.organisation_id for e in events} == {org.pk}
    assert events[1].changes["status"] == ["active", "past_due"]


def test_subscription_source_for_packages(org: Organisation) -> None:
    growth = package("growth", ["accounting"])
    other = Organisation.objects.create(name="Birch Ltd.")
    assert isinstance(get_source(), Subscriptions)
    assert get_source().count(growth) == 0
    assert get_source().package_of(org) is None
    subscribe(org, growth)
    ended = subscribe(other, growth)
    ended.status = SubscriptionStatus.CANCELLED
    ended.save()
    assert get_source().count(growth) == 1
    assert get_source().affected_by_price(growth, "month", date(2027, 1, 1)) == 1
    assert get_source().package_of(org) == "growth"


# ---- EntitlementOverride (T03) -----------------------------------------------------------------


def test_override_grants_until_it_expires(org: Organisation) -> None:
    item = grant(org, "payroll", days=14, reason="  Payroll   trial for a prospect ")
    assert item.reason == "Payroll trial for a prospect"
    assert item.is_active()
    assert list(active_overrides(org, timezone.now())) == [item]
    later = item.expires_at + timedelta(seconds=1)
    assert not item.is_active(later)
    assert list(active_overrides(org, later)) == []  # expired override ignored
    assert list(active_overrides(org, item.expires_at)) == []  # expires_at itself is past it


def test_removed_override_is_ignored(org: Organisation) -> None:
    item = grant(org, "payroll")
    with org_context(org):
        item.soft_delete()
    assert not item.is_active()
    assert list(active_overrides(org, timezone.now())) == []


def test_override_needs_a_reason_and_a_future_end(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        grant(org, "payroll", reason="   ")
    assert codes(excinfo) == {"reason": ["entitlements.override.reason_required"]}
    with pytest.raises(ValidationError) as excinfo:
        grant(org, "payroll", days=-1)
    assert codes(excinfo) == {"expires_at": ["entitlements.override.expires_past"]}


def test_override_is_in_the_organisation_audit_log(org: Organisation) -> None:
    grant(org, "payroll")
    with org_context(org):
        event = AuditEvent.objects.get(object_type="entitlements.EntitlementOverride")
    assert event.action == "entitlements.entitlementoverride.created"
    assert event.organisation_id == org.pk
    assert event.changes["product"][1]["label"] == "payroll"
    assert event.changes["reason"] == [None, "Prospect trial of the product"]


def test_overrides_are_scoped_to_their_organisation(org: Organisation) -> None:
    grant(org, "payroll")
    other = Organisation.objects.create(name="Birch Ltd.")
    with org_context(other):
        assert not EntitlementOverride.objects.exists()
    with org_context(org):
        assert EntitlementOverride.objects.get().product == Product.objects.get(code="payroll")
