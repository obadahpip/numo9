"""U-06-T04 (API side) — ``GET /api/v1/platform/organisations/<id>``: the state history.

The timeline holds the trial start, the subscription's creation and every status change (from its
audit log), and the conversion — oldest first; users, practices and the latest audit events come
with it; an unknown id is 404; ``platform.console.view`` only.
"""

from __future__ import annotations

import pytest
from django.test import Client
from django.utils import timezone

from numo9.entitlements.models import SubscriptionStatus
from numo9.entitlements.trials import start_trial, trial_converted
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, PracticeAssignment
from tests.test_platform_lists import staff
from tests.workspace_helpers import practice, user

pytestmark = pytest.mark.django_db


def test_detail_shows_the_state_history() -> None:
    org = Organisation.objects.create(name="Maple Leaf Supply Ltd.", time_zone="America/Toronto")
    OrganisationMember.objects.create(
        organisation=org, user=user("dana@maple.ca", "Dana Lee"), role="owner"
    )
    firm = practice("Abuodeh CPA")
    PracticeAssignment.objects.create(practice=firm, organisation=org)
    subscription = start_trial(org)
    with org_context(org):
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.save()
        trial_converted(subscription, timezone.now())
    body = staff().get(f"/api/v1/platform/organisations/{org.public_id}").json()
    assert [item["kind"] for item in body["timeline"]] == [
        "trial_started",
        "subscribed",
        "status",
        "converted",
    ]
    assert body["timeline"][2]["detail"] == "trialing → active"
    assert body["subscription"]["status"] == "active"
    assert body["users"][0]["email"] == "dana@maple.ca"
    assert body["practices"] == [
        {
            "id": str(firm.public_id),
            "name": "Abuodeh CPA",
            "role": "full_service",
            "active": True,
            "staff_count": 0,
        }
    ]
    assert any(e["action"] == "entitlements.trial.converted" for e in body["recent_events"])


def test_unknown_is_404_and_staff_only() -> None:
    assert (
        staff()
        .get("/api/v1/platform/organisations/00000000-0000-4000-8000-000000000000")
        .status_code
        == 404
    )
    outsider = Client()
    outsider.force_login(user("x@y.ca"))
    org = Organisation.objects.create(name="X")
    assert outsider.get(f"/api/v1/platform/organisations/{org.public_id}").status_code == 403
