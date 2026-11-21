"""Convert a demo to a trial (U-07-T10): a new, empty organisation with its free trial; the demo
is deleted (purged).

The sample data never moves: the trial starts with nothing in it (no contacts, no journals, no
chart until the owner picks a template). The visitor must be a real account — an anonymous demo
visitor signs up first (``demo.sign_up_first``). One trial per BN and owner email still holds
(U-05-T06): when the email already had a trial, nothing is created and the demo stays.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from numo9.entitlements.trials import start_trial
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
)

from .exclusions import is_demo
from .purge import purge_demo
from .users import is_demo_user


class NotADemo(ValueError):
    pass


class SignUpFirst(ValueError):
    pass


def convert_to_trial(
    demo: Organisation, user: Any, *, name: str, time_zone: str = ""
) -> Organisation:
    """The new trial organisation (owner ``user``); the demo is purged in the same transaction."""
    if not is_demo(demo) or demo.status != OrganisationStatus.DEMO:
        raise NotADemo(demo.pk)
    if not getattr(user, "is_authenticated", False) or is_demo_user(user):
        raise SignUpFirst(demo.pk)
    with transaction.atomic():
        organisation = Organisation.objects.create(
            name=name.strip() or user.email,
            time_zone=time_zone or demo.time_zone,
            locale=demo.locale,
            status=OrganisationStatus.TRIAL,
        )
        OrganisationMember.objects.create(
            organisation=organisation, user=user, role=OrganisationRole.OWNER
        )
        from numo9.founding.attribution import record_attribution
        from numo9.founding.models import AcquisitionSource

        record_attribution(organisation=organisation, source=AcquisitionSource.DEMO_CONVERSION)
        start_trial(organisation)  # TrialAlreadyUsed rolls everything back
        purge_demo(demo)
    return organisation
