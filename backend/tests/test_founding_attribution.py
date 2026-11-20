"""U-08-T07 — AcquisitionAttribution (referral source, UTM, promo) captured at sign-up.

Acceptance: stored for every new organisation — self sign-up (with the UTM, referral and promo
fields the sign-up page sends), in-app creation (owner or practice), demo conversion — and for the
practice of an accountant signing up; blank values stay blank; values are trimmed to their column.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.founding.attribution import clean, record_attribution
from numo9.founding.models import AcquisitionAttribution, AcquisitionSource
from numo9.tenancy.models import Organisation, OrganisationMember, PracticeMember
from tests.test_auth_signup import PASSWORD

pytestmark = pytest.mark.django_db
SIGNUP = "/_allauth/browser/v1/auth/signup"


def signup(body: dict[str, Any]) -> Any:
    return Client().post(SIGNUP, json.dumps(body), content_type="application/json")


def test_self_signup_stores_utm_referral_and_promo() -> None:
    response = signup(
        {
            "path": "organisation",
            "name": "Sam Roy",
            "email": "sam@refined.ca",
            "password": PASSWORD,
            "organisation_name": "Refined Interiors Inc.",
            "utm_source": "newsletter",
            "utm_medium": "email",
            "utm_campaign": "founding-1000",
            "referral_source": "A friend",
            "promo_code": "  founding25 ",
            "referrer": "https://numo9.ca/pricing",
        }
    )
    assert response.status_code == 401  # created; waiting for email verification
    organisation = OrganisationMember.objects.get(user__email="sam@refined.ca").organisation
    row = AcquisitionAttribution.objects.get(organisation=organisation)
    assert row.source == AcquisitionSource.SELF_SIGNUP
    assert (row.utm_source, row.utm_medium, row.utm_campaign) == (
        "newsletter",
        "email",
        "founding-1000",
    )
    assert (row.referral_source, row.promo_code) == ("A friend", "FOUNDING25")
    assert row.referrer == "https://numo9.ca/pricing" and row.utm_term == ""


def test_accountant_signup_is_recorded_on_the_practice() -> None:
    signup(
        {
            "path": "accountant",
            "name": "Dana Lee",
            "email": "dana@maple.ca",
            "password": PASSWORD,
            "practice_name": "Maple Leaf Accounting",
            "utm_source": "cpa-ontario",
        }
    )
    practice = PracticeMember.objects.get(user__email="dana@maple.ca").practice
    row = AcquisitionAttribution.objects.get(practice=practice)
    assert (row.source, row.utm_source) == (AcquisitionSource.ACCOUNTANT_SIGNUP, "cpa-ontario")


def test_signup_without_marketing_fields_still_stores_a_row() -> None:
    signup(
        {
            "path": "organisation",
            "name": "Ana",
            "email": "ana@birch.ca",
            "password": PASSWORD,
            "organisation_name": "Birch Ltd.",
        }
    )
    row = AcquisitionAttribution.objects.get(organisation__name="Birch Ltd.")
    assert row.source == AcquisitionSource.SELF_SIGNUP and row.utm_source == ""


def test_in_app_creation_is_recorded() -> None:
    user = User.objects.create_user("olivia@maple.ca", name="Olivia")
    client = APIClient()
    client.force_authenticate(user)
    response = client.post("/api/v1/organisations", {"name": "Maple Bakery Inc."}, format="json")
    assert response.status_code == 201
    row = AcquisitionAttribution.objects.get(organisation__name="Maple Bakery Inc.")
    assert row.source == AcquisitionSource.IN_APP


def test_values_are_trimmed_and_unknown_keys_ignored() -> None:
    values = clean({"utm_source": "x" * 300, "evil": "y", "utm_medium": "  a   b "})
    assert values == {"utm_source": "x" * 100, "utm_medium": "a b"}
    organisation = Organisation.objects.create(name="Pine Co.")
    record_attribution(organisation=organisation, source="in_app", data={"utm_source": "a"})
    record_attribution(organisation=organisation, source="in_app", data={"utm_source": "b"})
    assert AcquisitionAttribution.objects.get(organisation=organisation).utm_source == "b"
