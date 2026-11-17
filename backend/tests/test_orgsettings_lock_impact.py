"""A-05-T07 — Lock impact preview endpoint (count of drafts / unposted records dated before).

Acceptance: the count is correct on a fixture — journals in draft or awaiting approval dated on
or before the date are counted (posted ones, later ones, deleted ones and other organisations'
are not); module previews list their own sources and the GL preview every module's; validation
and permission.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from numo9.accounts.models import User
from numo9.ledger.models import JournalEntry, JournalStatus
from numo9.orgsettings.impact import register_impact
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = pytest.mark.django_db

register_impact("ar", "test_invoices", "Draft invoices (test)", lambda org, date: 2)


def _entry(org: Organisation, day: str, status: str = "draft", number: int | None = None) -> None:
    with org_context(org):
        entry = JournalEntry(
            organisation=org,
            date=dt.date.fromisoformat(day),
            status=status,
            number=number,
            posted_at=timezone.now() if number else None,
        )
        entry.save()


def _client(org: Organisation, role: str = "owner") -> Client:
    user = User.objects.create_user(f"{role}@refined.ca", password="x" * 12, name=role)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


def test_count_correct_on_fixture() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    other = Organisation.objects.create(name="Maple Leaf Bakery")
    _entry(org, "2026-03-01")  # draft before → counted
    _entry(org, "2026-03-31", "awaiting_approval")  # on the date → counted
    _entry(org, "2026-03-15", JournalStatus.POSTED, number=1)  # posted → not counted
    _entry(org, "2026-04-01")  # after → not counted
    _entry(other, "2026-03-01")  # another organisation → not counted
    with org_context(org):
        deleted = JournalEntry(organisation=org, date=dt.date(2026, 2, 1))
        deleted.save()
        deleted.soft_delete()

    url = f"/api/v1/o/{org.public_id}/settings/lock-dates/impact"
    body: Any = _client(org).get(url, {"module": "gl", "date": "2026-03-31"}).json()
    by_kind = {item["kind"]: item for item in body["items"]}
    assert by_kind["journals"]["count"] == 2
    assert by_kind["journals"]["label"] == "Journal entries not posted (draft or awaiting approval)"
    assert by_kind["test_invoices"]["count"] == 2  # the GL lock stops every module
    assert body["total"] == 4 and body["module"] == "gl" and body["date"] == "2026-03-31"

    ar = _client(org, "admin").get(url, {"module": "ar", "date": "2026-03-31"}).json()
    assert [item["kind"] for item in ar["items"]] == ["test_invoices"] and ar["total"] == 2


def test_validation_and_permission() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    url = f"/api/v1/o/{org.public_id}/settings/lock-dates/impact"
    owner = _client(org)
    assert owner.get(url, {"module": "nope", "date": "2026-03-31"}).status_code == 400
    assert owner.get(url, {"module": "gl", "date": "31/03/2026"}).status_code == 400
    assert owner.get(url, {"module": "gl"}).status_code == 400
    assert (
        _client(org, "employee").get(url, {"module": "gl", "date": "2026-03-31"}).status_code == 403
    )
