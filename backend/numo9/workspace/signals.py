"""Signals that keep the organisation directory current (V-01-T03).

Every change to a record the directory shows schedules a refresh of that organisation's rows
(``summary.schedule_refresh``: once per organisation per transaction, after it commits):

- the organisation itself (name, status) and its practice assignments (a new client appears, a
  switched-off assignment disappears);
- organisation settings (display/legal name, industry, province, fiscal year end), tax
  registrations (the BN) and lock dates (V-04);
- the subscription and entitlement overrides (package, status, trial end, Payroll);
- owner memberships, and the owner's own name or email address;
- the practice's tags (V-02 calls ``summary.tags_changed``).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models.signals import post_delete, post_save

from numo9.entitlements.models import EntitlementOverride, Subscription
from numo9.orgsettings.models import LockDate, OrganisationSettings, TaxRegistration
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    PracticeAssignment,
)

from .summary import schedule_refresh

UID = "numo9.workspace.directory"


def _organisation_changed(sender: Any, instance: Organisation, **kwargs: Any) -> None:
    schedule_refresh(instance.pk)


def _owned_record_changed(sender: Any, instance: Any, **kwargs: Any) -> None:
    schedule_refresh(instance.organisation_id)


def _membership_changed(sender: Any, instance: OrganisationMember, **kwargs: Any) -> None:
    schedule_refresh(instance.organisation_id)


def _user_changed(sender: Any, instance: Any, created: bool = False, **kwargs: Any) -> None:
    if created:
        return
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and not {"name", "email"} & set(update_fields):
        return  # last_login, password…: nothing the directory shows
    owned = OrganisationMember.objects.filter(
        user_id=instance.pk, role=OrganisationRole.OWNER
    ).values_list("organisation_id", flat=True)
    for organisation_id in owned:
        schedule_refresh(organisation_id)


def connect() -> None:
    post_save.connect(_organisation_changed, sender=Organisation, dispatch_uid=f"{UID}.org")
    for model in (
        PracticeAssignment,
        OrganisationSettings,
        TaxRegistration,
        LockDate,
        Subscription,
        EntitlementOverride,
    ):
        label = model._meta.label_lower
        post_save.connect(_owned_record_changed, sender=model, dispatch_uid=f"{UID}.{label}.save")
        post_delete.connect(_owned_record_changed, sender=model, dispatch_uid=f"{UID}.{label}.del")
    post_save.connect(_membership_changed, sender=OrganisationMember, dispatch_uid=f"{UID}.om.save")
    post_delete.connect(
        _membership_changed, sender=OrganisationMember, dispatch_uid=f"{UID}.om.del"
    )
    post_save.connect(_user_changed, sender=settings.AUTH_USER_MODEL, dispatch_uid=f"{UID}.user")
