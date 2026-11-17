"""U-04-T16 — Billing security. Acceptance: practice users never reach billing; replays are no-ops.

Covers, for every billing endpoint and method: the owner may; practice staff in every practice
role (practice admin included) assigned to the client get 403 — accountants are never billed and
never bill; the organisation's admins and other members get 403; a stranger gets 404 and an
anonymous request 401/403; no billing route exists outside an organisation (no practice or user
billing). Webhooks: an exact replay (same body and signature) is acknowledged as a duplicate and
runs nothing; a tampered body under a captured signature is refused (400) and stores nothing; a
replay with a new event id but an older ``created`` can't roll the state back; the endpoint needs
no session and ignores one.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from django.test import Client, override_settings
from django.urls import get_resolver

from numo9.accounts.models import User
from numo9.billing import tasks
from numo9.billing.models import StripeEvent
from numo9.billing.processing import process_event
from numo9.entitlements.models import Subscription
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)
from tests.billing_helpers import (
    FakeGateway,
    owned_org,
    sold_package,
    stripe_event,
    stripe_subscription,
)

pytestmark = pytest.mark.django_db
SECRET = "whsec_security"  # noqa: S105 - a test placeholder, not a key
SIGNED = f"t=1,v1=valid-for-{SECRET}"

ENDPOINTS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("get", "", None),
    ("post", "/portal", None),
    ("post", "/checkout", {"package": "growth", "interval": "month"}),
    ("get", "/change/preview?package=growth&interval=year", None),
    ("post", "/change", {"package": "growth", "interval": "year"}),
    ("post", "/cancel", {}),
    ("get", "/export", None),
    ("post", "/export", None),
]


@pytest.fixture(autouse=True)
def fake() -> Iterator[None]:
    FakeGateway.reset()
    sold_package("growth")
    with override_settings(
        NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway", STRIPE_WEBHOOK_SECRET=SECRET
    ):
        yield


def call(client: Client, org: Organisation, method: str, path: str, body: Any) -> int:
    url = f"/api/v1/o/{org.public_id}/billing{path}"
    if method == "get":
        return int(client.get(url).status_code)
    return int(
        getattr(client, method)(url, body or {}, content_type="application/json").status_code
    )


def login(user: User) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS)
def test_only_the_owner(method: str, path: str, body: Any) -> None:
    org, _ = owned_org()
    practice = Practice.objects.create(name="Tremblay CPA")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    for role in ("practice_admin", "accountant", "reviewer", "payroll_specialist", "read_only"):
        user = User.objects.create_user(f"{role}@cpa.ca", password="x" * 12)
        assignment.assigned_staff.add(
            PracticeMember.objects.create(practice=practice, user=user, role=role)
        )
        assert call(login(user), org, method, path, body) == 403, role
    for role in (
        "admin",
        "accountant_delegate",
        "sales",
        "purchasing",
        "payroll",
        "hr",
        "employee",
    ):
        user = User.objects.create_user(f"{role}@maple.ca", password="x" * 12)
        OrganisationMember.objects.create(organisation=org, user=user, role=role)
        assert call(login(user), org, method, path, body) == 403, role
    _, stranger = owned_org("Other Inc.", "other@other.ca")
    assert call(login(stranger), org, method, path, body) == 404
    assert call(Client(), org, method, path, body) in (401, 403)
    assert FakeGateway.calls == []


def test_no_billing_route_outside_an_organisation() -> None:
    def routes(patterns: Any, prefix: str = "") -> Iterator[str]:
        for p in patterns:
            text = prefix + str(p.pattern)
            if hasattr(p, "url_patterns"):
                yield from routes(p.url_patterns, text)
            else:
                yield text

    billing = [r for r in routes(get_resolver().url_patterns) if "billing" in r]
    assert billing and all(r.startswith("api/v1/o/<uuid:org>/billing") for r in billing)


def send(body: bytes, signature: str = SIGNED, session: Client | None = None) -> Any:
    client = session or Client(enforce_csrf_checks=True)
    return client.post(
        "/webhooks/stripe/",
        body,
        content_type="application/json",
        headers={"Stripe-Signature": signature},
    )


def test_exact_replay_runs_nothing() -> None:
    org, owner = owned_org()
    Subscription._base_manager.filter(organisation=org).update(stripe_customer_id="cus_test_0001")
    body = json.dumps(stripe_event("customer.subscription.updated", stripe_subscription())).encode()
    queued: list[int] = []
    with mock.patch.object(tasks.process_stripe_event, "delay", queued.append):
        first = send(body)
        process_event(StripeEvent.objects.get().pk)
        replay = send(body, session=login(owner))  # a session changes nothing
    assert first.json()["duplicate"] is False and replay.json()["duplicate"] is True
    assert len(queued) <= 1 and StripeEvent.objects.count() == 1
    assert process_event(StripeEvent.objects.get().pk) == "skipped"


def test_tampered_body_is_refused() -> None:
    body = json.dumps(stripe_event("invoice.paid", {"id": "in_1"}))
    tampered = body.replace("in_1", "in_2").encode()
    with mock.patch(
        "tests.billing_helpers.FakeGateway.construct_event",
        side_effect=__import__("numo9.billing.gateway", fromlist=["x"]).SignatureInvalid("bad"),
    ):
        assert send(tampered).status_code == 400
    assert not StripeEvent.objects.exists()


def test_old_event_with_a_new_id_cannot_roll_back(django_capture_on_commit_callbacks: Any) -> None:
    org, _ = owned_org()
    Subscription._base_manager.filter(organisation=org).update(stripe_customer_id="cus_test_0001")
    now = stripe_event("customer.subscription.deleted", stripe_subscription(status="canceled"))
    old = stripe_event(
        "customer.subscription.updated", stripe_subscription(), created=now["created"] - 3600
    )
    with mock.patch.object(tasks.process_stripe_event, "delay", process_event):
        for event in (now, old):
            with django_capture_on_commit_callbacks(execute=True):
                send(json.dumps(event).encode())
    assert Subscription._base_manager.get(organisation=org).status == "cancelled"
