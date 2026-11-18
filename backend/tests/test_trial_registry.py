"""U-05-T02 — TrialRegistry (normalised_bn, normalised_email, org, started_at) with unique indexes.

Acceptance: a second insert with the same BN raises IntegrityError — and the same for the owner
email; empty values never collide (organisations without a BN or an owner yet); the database
refuses a BN that isn't 9 digits and an email that isn't lower-case.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from numo9.entitlements.models import TrialRegistry
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def _org(name: str) -> Organisation:
    return Organisation.objects.create(name=name)


def _insert(**fields: str) -> TrialRegistry:
    with transaction.atomic():
        return TrialRegistry.objects.create(organisation=_org(fields.pop("name", "Org")), **fields)


def test_second_trial_same_bn_is_refused() -> None:
    _insert(normalised_bn="123456782", normalised_email="dana@refined.ca")
    with pytest.raises(IntegrityError):
        _insert(normalised_bn="123456782")


def test_second_trial_same_email_is_refused() -> None:
    _insert(normalised_email="dana@refined.ca")
    with pytest.raises(IntegrityError):
        _insert(normalised_bn="987654321", normalised_email="dana@refined.ca")


def test_empty_values_never_collide() -> None:
    for _ in range(3):
        _insert()
    _insert(normalised_bn="123456782")
    _insert(normalised_email="lee@cpa.ca")
    assert TrialRegistry.objects.count() == 5


@pytest.mark.parametrize(
    "fields",
    [
        {"normalised_bn": "12345678"},
        {"normalised_bn": "12345678A"},
        {"normalised_email": "Dana@Refined.ca"},
    ],
)
def test_only_normalised_values(fields: dict[str, str]) -> None:
    with pytest.raises(IntegrityError):
        _insert(**fields)
