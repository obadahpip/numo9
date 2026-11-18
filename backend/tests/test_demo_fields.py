"""U-07-T02 — ``is_demo``, ``demo_seed_version``, ``last_active_at`` on Organisation.

A new organisation is not a demo and has no seed version or activity yet; a demo records its seed
version; the database refuses a seed version on a real organisation.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.tenancy.models import Organisation, OrganisationStatus

pytestmark = pytest.mark.django_db


def test_defaults() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    org.refresh_from_db()
    assert (org.is_demo, org.demo_seed_version, org.last_active_at) == (False, None, None)


def test_demo_records_its_seed_version_and_activity() -> None:
    now = timezone.now()
    org = Organisation.objects.create(
        name="Maple & Pine Supply Co.",
        status=OrganisationStatus.DEMO,
        is_demo=True,
        demo_seed_version=1,
        last_active_at=now,
    )
    org.refresh_from_db()
    assert (org.is_demo, org.demo_seed_version, org.last_active_at) == (True, 1, now)


def test_seed_version_only_on_a_demo() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Organisation.objects.create(name="Real Ltd.", demo_seed_version=1)
