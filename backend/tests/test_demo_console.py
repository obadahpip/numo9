"""U-06-T13 (API part) — the console's demo manager: open demos, their purge day, templates.

Acceptance: lists every open demo (not templates, not purged) with its seed version, last
activity, purge day (31 days after the last activity) and members; counts those purged within 7
days; purging one needs ``platform.catalogue.manage`` (support may look) and leaves it cancelled.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone

from numo9.demo.cloning import create_demo
from numo9.demo.seeders import SEED_VERSION
from numo9.tenancy.models import Organisation, OrganisationStatus
from tests.test_platform_lists import staff

pytestmark = pytest.mark.django_db
URL = "/api/v1/platform/demos"


def test_lists_open_demos_with_their_purge_day() -> None:
    fresh, idle = create_demo(name="Fresh demo"), create_demo(name="Idle demo")
    Organisation.objects.filter(pk=idle.pk).update(
        last_active_at=timezone.now() - dt.timedelta(days=26)
    )
    body = staff().get(URL).json()
    assert body["seed_version"] == SEED_VERSION and body["idle_days"] == 30
    assert body["open"] == 2 and body["purge_soon"] == 1
    assert [t["seed_version"] for t in body["templates"]] == [SEED_VERSION]
    names = {row["name"]: row for row in body["demos"]}
    assert set(names) == {"Fresh demo", "Idle demo"}
    expected = timezone.localdate(timezone.now() - dt.timedelta(days=26) + dt.timedelta(days=31))
    assert names["Idle demo"]["purge_on"] == expected.isoformat()
    assert names["Fresh demo"]["id"] == str(fresh.public_id)


def test_purge_one_demo_needs_catalogue_manage() -> None:
    demo = create_demo(name="Purge me")
    url = f"{URL}/{demo.public_id}/purge"
    support, owner = staff(), staff("platform_owner")
    assert support.post(url).status_code == 403
    assert owner.post(url).status_code == 204
    demo.refresh_from_db()
    assert demo.status == OrganisationStatus.CANCELLED
    assert support.get(URL).json()["open"] == 0
    assert owner.post(url).status_code == 404  # no longer open
