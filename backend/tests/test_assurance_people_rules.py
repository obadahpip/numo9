"""K-09-T15 — people rules: DORMANT_USER_WITH_ADMIN and CONTACT_BANK_DETAILS_CHANGED.

Acceptance: the dormant subscriber with manage-users rights is flagged (teardown: no sign-in for
four months); a recent sign-in or a role without user management is not; a contact whose bank
details changed recently (audit log, masked fields) is flagged, an older or non-bank change is not.
"""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.assurance.rules.base import evaluate, registry
from numo9.audit import service as audit
from numo9.tenancy.context import org_context
from tests.assurance_helpers import NOW, at, refined

pytestmark = pytest.mark.django_db


def test_dormant_subscriber_with_manage_users_is_flagged() -> None:
    books = refined()
    (hit,) = evaluate(books["org"], "DORMANT_USER_WITH_ADMIN", now=NOW)
    assert (hit.subject_type, hit.subject_id) == ("accounts.User", str(books["owner"].public_id))
    assert hit.details["idle"] == 123 and hit.details["last_active"] == "2026-07-26"
    text = registry.get("DORMANT_USER_WITH_ADMIN").explain(hit.details)
    assert text.startswith("Dana Lee can manage users but hasn't signed in since 26 Jul 2026")
    assert evaluate(books["org"], "DORMANT_USER_WITH_ADMIN", now=NOW, params={"days": 200}) == []


def test_recent_sign_in_or_no_user_management_is_not_flagged() -> None:
    from numo9.accounts.models import User
    from numo9.tenancy.models import OrganisationMember

    books = refined()
    org = books["org"]
    User.objects.filter(pk=books["owner"].pk).update(last_login=NOW - dt.timedelta(days=3))
    clerk = User.objects.create_user(f"clerk+{org.pk}@refined.ca", name="Sam Clerk")
    User.objects.filter(pk=clerk.pk).update(last_login=NOW - dt.timedelta(days=300))
    OrganisationMember.objects.create(organisation=org, user=clerk, role="sales")
    assert evaluate(org, "DORMANT_USER_WITH_ADMIN", now=NOW) == []


def test_recent_bank_detail_change_is_flagged() -> None:
    from tests.contact_helpers import contact

    books = refined()
    org = books["org"]
    with org_context(org):
        cedar = contact(org, "Cedar Supply Co.", roles=["supplier"])
        maple = contact(org, "Maple Hardware Ltd", roles=["supplier"])
        masked = {"masked": True}
        with at(NOW - dt.timedelta(days=5)):
            audit.record(
                "contacts.contact.updated",
                obj=cedar,
                changes={"bank_account": [masked, masked], "transit_number": [masked, masked]},
            )
            audit.record("contacts.contact.updated", obj=maple, changes={"email": ["a", "b"]})
        with at(NOW - dt.timedelta(days=60)):
            audit.record(
                "contacts.contact.updated", obj=maple, changes={"bank_account": [masked, masked]}
            )
    (hit,) = evaluate(org, "CONTACT_BANK_DETAILS_CHANGED", now=NOW)
    assert (hit.subject_type, hit.subject_id) == ("contacts.Contact", str(cedar.public_id))
    assert hit.details["fields"] == "bank_account, transit_number"
    assert hit.details["changed_on"] == "2026-11-21"
    longer = evaluate(org, "CONTACT_BANK_DETAILS_CHANGED", now=NOW, params={"lookback_days": 90})
    assert len(longer) == 2
