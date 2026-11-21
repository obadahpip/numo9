"""U-07-T10 — convert a demo to a trial: new empty organisation + trial, demo deleted.

Acceptance (integration): the new organisation has 0 sample records (no contacts, accounts,
journals), a trialing subscription and the user as owner; the demo is purged (data wiped, member
removed, cancelled); an anonymous demo visitor must sign up first; a real organisation is not a
demo; an email that already had a trial creates nothing and keeps the demo.
"""

from __future__ import annotations

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.contacts.models import Contact
from numo9.demo.cloning import create_demo
from numo9.demo.users import make_demo_user
from numo9.entitlements.models import Subscription, SubscriptionStatus
from numo9.entitlements.trials import register_trial
from numo9.ledger.models import Account, JournalEntry
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationStatus

pytestmark = pytest.mark.django_db


def _owner(demo: Organisation, user: User) -> Client:
    OrganisationMember.objects.create(organisation=demo, user=user, role="owner")
    browser = Client()
    browser.force_login(user)
    return browser


def url(org: Organisation) -> str:
    return f"/api/v1/o/{org.public_id}/demo/convert"


def test_convert_creates_an_empty_trial_and_deletes_the_demo() -> None:
    demo = create_demo()
    user = User.objects.create_user("owner@maplepine.example", password="x" * 12)
    response = _owner(demo, user).post(
        url(demo), {"name": "Maple & Pine Supply Co."}, content_type="application/json"
    )
    assert response.status_code == 201, response.content
    new = Organisation.objects.get(public_id=response.json()["id"])
    assert new.status == OrganisationStatus.TRIAL and not new.is_demo
    assert OrganisationMember.objects.filter(organisation=new, user=user, role="owner").exists()
    assert new.acquisition.source == "demo_conversion"  # U-08-T07
    with org_context(new):
        assert Contact.objects.count() == 0
        assert Account.objects.count() == 0
        assert JournalEntry.objects.count() == 0
        assert Subscription.objects.get().status == SubscriptionStatus.TRIALING
    demo.refresh_from_db()
    assert demo.status == OrganisationStatus.CANCELLED
    assert not OrganisationMember.objects.filter(organisation=demo).exists()
    with org_context(demo):
        assert Contact.objects.count() == 0


def test_anonymous_visitor_signs_up_first() -> None:
    demo = create_demo()
    response = _owner(demo, make_demo_user()).post(
        url(demo), {"name": "Mine"}, content_type="application/json"
    )
    assert response.status_code == 409
    assert response.json()["code"] == "demo.sign_up_first"
    demo.refresh_from_db()
    assert demo.status == OrganisationStatus.DEMO


def test_real_organisation_is_not_a_demo() -> None:
    real = Organisation.objects.create(name="Real Ltd.")
    user = User.objects.create_user("o@real.example", password="x" * 12)
    response = _owner(real, user).post(url(real), {"name": "X"}, content_type="application/json")
    assert response.status_code == 409 and response.json()["code"] == "demo.not_a_demo"


def test_trial_already_used_keeps_the_demo() -> None:
    demo = create_demo()
    user = User.objects.create_user("used@maplepine.example", password="x" * 12)
    earlier = Organisation.objects.create(name="Earlier Ltd.")
    register_trial(earlier, email="used@maplepine.example")
    before = Organisation.objects.count()
    response = _owner(demo, user).post(
        url(demo), {"name": "Again"}, content_type="application/json"
    )
    assert response.status_code == 409
    assert response.json()["code"] == "entitlements.trial_already_used"
    assert Organisation.objects.count() == before
    demo.refresh_from_db()
    assert demo.status == OrganisationStatus.DEMO
    with org_context(demo):
        assert Contact.objects.count() == 25


def test_reset_and_outbox_endpoints() -> None:
    from numo9.demo.models import DemoOutbox

    demo = create_demo()
    user = User.objects.create_user("o2@maplepine.example", password="x" * 12)
    browser = _owner(demo, user)
    with org_context(demo):
        Contact(organisation=demo, display_name="Visitor Co.", roles=["customer"]).save()
        DemoOutbox(organisation=demo, to_email="a@b.example", subject="Statement").save()
    reset = browser.post(f"/api/v1/o/{demo.public_id}/demo/reset")
    assert reset.status_code == 200 and reset.json() == {"seed_version": 1}
    with org_context(demo):
        assert Contact.objects.count() == 25
    outbox = browser.get(f"/api/v1/o/{demo.public_id}/demo/outbox").json()["results"]
    assert [row["subject"] for row in outbox] == ["Statement"]
    real = Organisation.objects.create(name="Real Ltd.")
    owner = _owner(real, User.objects.create_user("r@real.example", password="x" * 12))
    assert owner.post(f"/api/v1/o/{real.public_id}/demo/reset").status_code == 409
