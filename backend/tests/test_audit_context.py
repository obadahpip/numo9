"""Audit context: actor, IP, device and request id per request; job attribution (A-04-T04).

Acceptance: a change made by a background job is attributed to ``System: <job name>`` (gap-44) —
with the job and the person who started it in ``meta`` — and a change made through the API
carries the signed-in user, the client's IP, the device and the request id that the response
returns in ``X-Request-ID``.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client, override_settings
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.audit.context import (
    REQUEST_ID_HEADER,
    AuditContextMiddleware,
    audit_context,
    client_ip,
    current_actor,
)
from numo9.audit.models import ActorKind, AuditEvent
from numo9.audit.service import record
from numo9.jobs.runtime import org_job, start_job
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.job_helpers import deliver
from tests.testapp.models import AuditedInvoice

pytestmark = pytest.mark.django_db


@org_job(name="tests.audit.reprice_invoices", label="Reprice invoices", max_retries=0)
def reprice_invoices(*, org_id: str, amount: str) -> dict[str, int]:
    invoices = list(AuditedInvoice.objects.all())
    for invoice in invoices:
        invoice.amount = Decimal(amount)
        invoice.save()
    return {"repriced": len(invoices)}


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def owner(org: Organisation) -> User:
    user = User.objects.create_user("avery@refined.ca", password="x" * 12, name="Avery Owner")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    return user


def org_events(org: Organisation, **filters: Any) -> list[AuditEvent]:
    with org_context(org):
        return list(AuditEvent.objects.filter(**filters).order_by("id"))


# ---- acceptance: a system job is attributed --------------------------------------------------


def test_change_made_by_a_job_is_attributed_to_the_job(
    org: Organisation, owner: User, sent: list[dict[str, Any]]
) -> None:
    with org_context(org):
        AuditedInvoice.objects.create(number="INV-1", amount=Decimal("10.00"))
    run = start_job(reprice_invoices, organisation=org, created_by=owner, amount="12.00")
    assert deliver(reprice_invoices, sent[0]) == {"repriced": 1}
    (event,) = org_events(org, action="testapp.auditedinvoice.updated")
    assert event.actor_kind == ActorKind.SYSTEM and event.actor_user is None
    assert event.actor_label == "System: Reprice invoices"
    assert event.meta["job"] == {
        "id": str(run.public_id),
        "task": "tests.audit.reprice_invoices",
        "started_by": {"id": str(owner.public_id), "label": "Avery Owner (avery@refined.ca)"},
    }
    assert event.changes == {"amount": ["10.00", "12.00"]}


def test_process_without_request_or_job_is_system() -> None:
    actor = current_actor()
    assert actor.kind == ActorKind.SYSTEM and actor.user is None
    assert actor.label.startswith("System")


# ---- acceptance: a request is attributed ------------------------------------------------------


def test_api_change_carries_user_ip_device_and_request_id(org: Organisation, owner: User) -> None:
    client = APIClient(REMOTE_ADDR="203.0.113.9", HTTP_USER_AGENT="Numo9Test/1.0")
    client.force_authenticate(owner)
    response = client.post(f"/api/v1/o/{org.public_id}/roles", {"name": "Buyer"}, format="json")
    assert response.status_code == 201
    (event,) = org_events(org, action="role.created")
    assert event.actor_kind == ActorKind.USER and event.actor_user == owner
    assert event.actor_label == "Avery Owner (avery@refined.ca)"
    assert event.ip == "203.0.113.9" and event.user_agent == "Numo9Test/1.0"
    assert event.request_id == response[REQUEST_ID_HEADER]


def test_every_response_has_a_request_id_and_a_good_one_is_kept() -> None:
    made = Client().get("/healthz")[REQUEST_ID_HEADER]
    assert re.fullmatch(r"[0-9a-f]{32}", made)
    kept = Client().get("/healthz", HTTP_X_REQUEST_ID="caddy-1234abcd")[REQUEST_ID_HEADER]
    assert kept == "caddy-1234abcd"
    replaced = Client().get("/healthz", HTTP_X_REQUEST_ID="bad id; drop")[REQUEST_ID_HEADER]
    assert replaced != "bad id; drop" and re.fullmatch(r"[0-9a-f]{32}", replaced)


def test_impersonation_names_both_people(org: Organisation, owner: User) -> None:
    staff = User.objects.create_user("support@numo9.ca", name="Pat Support")
    seen: dict[str, Any] = {}

    def view(request: Any) -> Any:
        from django.http import HttpResponse

        request.user = owner
        request.audit_impersonator = staff
        seen["event"] = record("tests.impersonated", organisation=org)
        return HttpResponse("ok")

    from django.test import RequestFactory

    AuditContextMiddleware(view)(RequestFactory().get("/x"))
    event = seen["event"]
    assert event.actor_kind == ActorKind.IMPERSONATION
    assert event.actor_user == owner and event.impersonator == staff
    assert "Pat Support" in event.actor_label and "Avery Owner" in event.actor_label


def test_explicit_context_wins(org: Organisation, owner: User) -> None:
    with audit_context(kind=ActorKind.SYSTEM, label="System: data migration", request_id="mig-1"):
        event = record("tests.manual", organisation=org)
    assert event.actor_label == "System: data migration" and event.request_id == "mig-1"


# ---- client IP behind proxies ----------------------------------------------------------------


class _Req:
    def __init__(self, **meta: str) -> None:
        self.META = meta


def test_client_ip_ignores_forwarded_for_unless_proxies_are_trusted() -> None:
    request = _Req(REMOTE_ADDR="10.0.0.2", HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.7")
    assert client_ip(request) == "10.0.0.2"
    with override_settings(NUMO9_TRUSTED_PROXY_COUNT=1):
        assert client_ip(request) == "198.51.100.7"  # the address Caddy saw, not the client's claim
    with override_settings(NUMO9_TRUSTED_PROXY_COUNT=1):
        assert client_ip(_Req(REMOTE_ADDR="10.0.0.2", HTTP_X_FORWARDED_FOR="junk")) == "10.0.0.2"
    assert client_ip(_Req(REMOTE_ADDR="not an ip")) is None
