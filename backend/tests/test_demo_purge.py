"""U-07-T09 — inactivity purge job (30 days).

Acceptance: a fixture demo idle for 30 days and one second is purged, at exactly 30 days (and at
29) it is kept; purged = data wiped, members removed, anonymous demo users deleted, organisation
cancelled; templates are never purged; signed-in requests keep a demo alive (at most one write
per 15 minutes); the beat schedule runs the job daily.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.conf import settings
from django.test import Client

from numo9.accounts.models import User
from numo9.contacts.models import Contact
from numo9.demo.cloning import create_demo, template_for
from numo9.demo.purge import idle_demos, purge_inactive, touch
from numo9.demo.tasks import purge_inactive_job
from numo9.demo.users import make_demo_user
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationStatus

pytestmark = pytest.mark.django_db
NOW = dt.datetime(2026, 11, 19, 12, 0, tzinfo=dt.UTC)


def _demo(days_idle: float) -> Organisation:
    demo = create_demo()
    Organisation.objects.filter(pk=demo.pk).update(
        last_active_at=NOW - dt.timedelta(days=days_idle)
    )
    demo.refresh_from_db()
    return demo


def test_purged_after_30_days_not_at_29_or_30() -> None:
    at_29, at_30, past_30 = _demo(29), _demo(30), _demo(30 + 1 / 86400)
    visitor = make_demo_user()
    OrganisationMember.objects.create(organisation=past_30, user=visitor, role="owner")
    assert purge_inactive(NOW) == [past_30.pk]
    past_30.refresh_from_db()
    assert past_30.status == OrganisationStatus.CANCELLED and past_30.demo_seed_version is None
    with org_context(past_30):
        assert Contact.objects.count() == 0
    assert not OrganisationMember.objects.filter(organisation=past_30).exists()
    assert not User.objects.filter(pk=visitor.pk).exists()
    for kept in (at_29, at_30):
        kept.refresh_from_db()
        assert kept.status == OrganisationStatus.DEMO
        with org_context(kept):
            assert Contact.objects.count() == 25
    assert purge_inactive(NOW) == []  # a purged demo is not purged again


def test_templates_and_real_organisations_are_never_purged() -> None:
    template = template_for()
    Organisation.objects.filter(pk=template.organisation.pk).update(
        last_active_at=NOW - dt.timedelta(days=400)
    )
    real = Organisation.objects.create(name="Real Ltd.")
    Organisation.objects.filter(pk=real.pk).update(last_active_at=NOW - dt.timedelta(days=400))
    assert list(idle_demos(NOW)) == []


def test_a_real_user_member_is_kept() -> None:
    demo = _demo(31)
    accountant = User.objects.create_user("cpa@practice.example", password="x" * 12)
    OrganisationMember.objects.create(organisation=demo, user=accountant, role="owner")
    purge_inactive(NOW)
    assert User.objects.filter(pk=accountant.pk).exists()


def test_touch_at_most_every_15_minutes() -> None:
    demo = _demo(1)
    assert touch(demo, NOW)
    assert not touch(demo, NOW + dt.timedelta(minutes=10))
    assert touch(demo, NOW + dt.timedelta(minutes=16))
    assert not touch(Organisation.objects.create(name="Real Ltd."), NOW)


def test_signed_in_request_keeps_the_demo_alive() -> None:
    demo = _demo(20)
    user = User.objects.create_user("cpa2@practice.example", password="x" * 12)
    OrganisationMember.objects.create(organisation=demo, user=user, role="owner")
    browser = Client()
    browser.force_login(user)
    browser.get(f"/api/v1/o/{demo.public_id}/contacts")
    demo.refresh_from_db()
    assert demo.last_active_at is not None
    assert demo.last_active_at > NOW - dt.timedelta(days=1)


def test_job_and_schedule() -> None:
    assert "numo9.demo.purge_inactive" in settings.CELERY_BEAT_SCHEDULE
    assert purge_inactive_job.name == "numo9.demo.purge_inactive"
