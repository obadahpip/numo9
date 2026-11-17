"""U-05-T10 (API side) — the entitlements bootstrap gives the trial chip its end and days left.

``GET /api/v1/o/<org>/entitlements`` answers ``trial_ends_at`` (local 23:59:59 on the last day)
and ``trial_days_left`` (whole days on the organisation's calendar) during the trial, ``null``
otherwise.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.test import Client
from django.utils import timezone

from numo9.entitlements.trials import start_trial
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db


def test_trial_fields_in_the_bootstrap() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")
    owner = user("sam@refined.ca")
    OrganisationMember.objects.create(organisation=org, user=owner, role=OrganisationRole.OWNER)
    start_trial(org, now=timezone.now() - dt.timedelta(days=17))
    browser = Client()
    browser.force_login(owner)
    body = browser.get(f"/api/v1/o/{org.public_id}/entitlements").json()
    assert body["reason"] == "trialing"
    assert body["trial_days_left"] == 12
    assert body["trial_ends_at"] is not None and body["grace_until"] is None
