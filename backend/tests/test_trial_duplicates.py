"""U-05-T06 — Duplicate trial refusal with a clear error (``trial_already_used``; the masked name
of the organisation that used it, to the Platform Owner only).

Acceptance: a second trial with the same BN is refused. Also with the same owner email (case and
plus-addressing ignored) — at sign-up (the form error on the email) and when creating an
organisation (409, nothing created); a BN entered *after* the trial started is checked then; the
Platform Owner sees which organisation used it (masked), nobody else does.
"""

from __future__ import annotations

import json

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from numo9.entitlements.models import TrialRegistry
from numo9.entitlements.trials import TrialAlreadyUsed, mask_name, start_trial
from numo9.orgsettings.models import RegistrationType, TaxRegistration
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.auth_helpers import enrol_two_factor
from tests.workspace_helpers import user, valid_bn

pytestmark = pytest.mark.django_db
PASSWORD = "Correct-horse-battery-9"  # noqa: S105 (test account)
BN = valid_bn(12345678)


def _owned(name: str, owner_email: str, bn: str = "") -> Organisation:
    org = Organisation.objects.create(name=name)
    OrganisationMember.objects.create(
        organisation=org, user=user(owner_email), role=OrganisationRole.OWNER
    )
    if bn:
        with org_context(org):
            TaxRegistration(organisation=org, type=RegistrationType.BN, number=bn).save()
    return org


def test_second_trial_with_the_same_bn_is_refused() -> None:
    first = _owned("Maple Leaf Supply Ltd.", "dana@maple.ca", bn=BN)
    start_trial(first)
    second = _owned(
        "Maple Leaf Supply (2) Ltd.", "other@maple.ca", bn=f"{BN[:3]} {BN[3:6]} {BN[6:]}"
    )
    with pytest.raises(TrialAlreadyUsed) as refused:
        start_trial(second)
    assert refused.value.code == "trial_already_used" and refused.value.field == "bn"
    assert refused.value.existing == first
    assert TrialRegistry.objects.count() == 1


def test_second_trial_with_the_same_email_is_refused() -> None:
    start_trial(_owned("Refined Interiors Inc.", "dana@refined.ca"))
    with pytest.raises(TrialAlreadyUsed) as refused:
        start_trial(_owned("Refined Kitchens Inc.", "Dana+second@Refined.CA"))
    assert refused.value.field == "email"


def test_bn_entered_after_the_trial_is_checked_then() -> None:
    start_trial(_owned("Maple Leaf Supply Ltd.", "dana@maple.ca", bn=BN))
    later = _owned("Copycat Inc.", "copy@cat.ca")
    start_trial(later)  # no BN yet: allowed
    with org_context(later), pytest.raises(ValidationError) as refused:
        TaxRegistration(organisation=later, type=RegistrationType.BN, number=BN).save()
    assert refused.value.code == "trial_already_used"
    other = valid_bn(87654321)
    with org_context(later):
        TaxRegistration(organisation=later, type=RegistrationType.BN, number=other).save()
    assert TrialRegistry.objects.get(organisation=later).normalised_bn == other


def test_signup_with_a_used_email_is_refused_on_the_email() -> None:
    start_trial(_owned("Refined Interiors Inc.", "sam@refined.ca"))
    body = {
        "path": "organisation",
        "name": "Sam Roy",
        "email": "SAM+again@refined.ca",
        "password": PASSWORD,
        "organisation_name": "Refined Kitchens Inc.",
    }
    response = Client().post(
        "/_allauth/browser/v1/auth/signup", json.dumps(body), content_type="application/json"
    )
    assert response.status_code == 400
    errors = response.json()["errors"]
    assert any(e["param"] == "email" and e["code"] == "trial_already_used" for e in errors)
    assert not Organisation.objects.filter(name="Refined Kitchens Inc.").exists()


def _platform_owner() -> Client:
    person = user("owner@numo9.ca")
    RoleAssignment.objects.create(
        user=person, role=Role.objects.get(scope=RoleScope.PLATFORM, key="platform_owner")
    )
    enrol_two_factor(person)
    browser = Client()
    browser.force_login(person)
    return browser


def test_api_refusal_is_409_and_masked_for_the_platform_owner_only() -> None:
    first = _owned("Maple Leaf Supply Ltd.", "dana@maple.ca")
    start_trial(first)
    dana = OrganisationMember.objects.get(organisation=first).user
    browser = Client()
    browser.force_login(dana)
    response = browser.post(
        "/api/v1/organisations", {"name": "Second Co."}, content_type="application/json"
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "entitlements.trial_already_used" and body["field"] == "email"
    assert "existing_organisation" not in body
    assert not Organisation.objects.filter(name="Second Co.").exists()  # nothing created
    # The Platform Owner trying the same sees which organisation used it — masked.
    staff = _platform_owner()
    TrialRegistry.objects.create(
        organisation=Organisation.objects.create(name="Owner Trial Inc."),
        normalised_email="owner@numo9.ca",
    )
    refused = staff.post(
        "/api/v1/organisations", {"name": "Third Co."}, content_type="application/json"
    )
    assert refused.status_code == 409
    assert refused.json()["existing_organisation"] == "Ow*** Tr*** In***"


def test_mask_name() -> None:
    assert mask_name("Maple Leaf Supply Ltd.") == "Ma*** Le*** Su*** Lt***"
