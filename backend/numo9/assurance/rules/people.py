"""People rules (K-09-T15): dormant administrators and changed contact bank details.

**DORMANT_USER_WITH_ADMIN** — a person who can manage the organisation's users
(``organisation.members.manage``: owners, admins, practice admins serving it) and hasn't signed in
for ``days`` days (never signed in: counted from joining). The teardown subscriber hadn't signed in
for four months and kept user-management rights.

**CONTACT_BANK_DETAILS_CHANGED** — a contact's bank or payment details changed in the last
``lookback_days``, read from the audit log (A-04): bank fields are masked there, so the event
says *that* they changed, never the numbers. Payment-redirection fraud starts with this change:
confirm it with the supplier by phone before the next payment.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

from django.utils.translation import gettext_lazy

from ..models import Severity
from .base import Context, Hit, Param, Rule, register

MANAGE_USERS = "organisation.members.manage"
#: Field-name parts of bank and payment details (the audit log masks them, A-04).
BANK_PARTS = ("bank", "transit", "institution", "account_number", "iban", "routing", "payee")


@register
class DormantUserWithAdmin(Rule):
    code = "DORMANT_USER_WITH_ADMIN"
    name = gettext_lazy("Dormant user with user-management rights")
    description = gettext_lazy(
        "Someone who can add people and change roles hasn't signed in for a long time."
    )
    explanation = gettext_lazy(
        "%(person)s can manage users but hasn't signed in since %(last_active)s (%(idle)s days). "
        "Remove the right or the access if it isn't needed any more."
    )
    default_severity = Severity.WARNING
    date_keys = ("last_active",)
    params = {"days": Param("int", 60, gettext_lazy("Days"), minimum=7, maximum=365)}

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        from numo9.rbac.models import RoleAssignment
        from numo9.rbac.resolver import has_perm
        from numo9.tenancy.models import OrganisationMember

        organisation = ctx.organisation
        joined: dict[int, dt.datetime] = {}
        members = OrganisationMember.objects.filter(organisation=organisation).select_related(
            "user"
        )
        people: dict[int, Any] = {}
        for member in members:
            people[member.user_id] = member.user
            joined[member.user_id] = member.created_at
        for row in RoleAssignment.objects.filter(organisation=organisation).select_related("user"):
            people.setdefault(row.user_id, row.user)
            joined.setdefault(row.user_id, row.created_at)
        for pk, user in sorted(people.items()):
            if not user.is_active:
                continue
            last = user.last_login or joined.get(pk)
            if last is None:
                continue
            idle = (ctx.now - last).days
            if idle < ctx.params["days"] or not has_perm(user, organisation, MANAGE_USERS):
                continue
            yield Hit(
                "accounts.User",
                str(user.public_id),
                str(user.name or user.email),
                None,
                {
                    "person": str(user.name or user.email),
                    "email": user.email,
                    "last_active": last.astimezone(ctx.zone).date().isoformat(),
                    "never_signed_in": user.last_login is None,
                    "idle": idle,
                },
            )


def is_bank_field(name: str) -> bool:
    lowered = name.lower()
    return any(part in lowered for part in BANK_PARTS)


@register
class ContactBankDetailsChanged(Rule):
    code = "CONTACT_BANK_DETAILS_CHANGED"
    name = gettext_lazy("Contact bank details changed")
    description = gettext_lazy(
        "A supplier's or employee's bank details changed recently: confirm before paying."
    )
    explanation = gettext_lazy(
        "%(contact)s's bank details (%(fields)s) were changed on %(changed_on)s by %(by)s. Call "
        "the contact on a number you already have to confirm before the next payment."
    )
    default_severity = Severity.WARNING
    date_keys = ("changed_on",)
    params = {"lookback_days": Param("int", 30, gettext_lazy("Days back"), minimum=1, maximum=365)}

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        from numo9.audit.models import AuditEvent

        since = ctx.now - dt.timedelta(days=ctx.params["lookback_days"])
        events = AuditEvent.objects.filter(
            organisation=ctx.organisation,
            object_type="contacts.Contact",
            action__endswith=".updated",
            created_at__gte=since,
        ).order_by("-created_at", "-id")
        seen: set[str] = set()
        for event in events:
            fields = sorted(name for name in (event.changes or {}) if is_bank_field(str(name)))
            if not fields or event.object_id in seen:
                continue
            seen.add(event.object_id)
            yield Hit(
                "contacts.Contact",
                event.object_id,
                event.object_label,
                None,
                {
                    "contact": event.object_label,
                    "fields": ", ".join(fields),
                    "changed_on": event.created_at.astimezone(ctx.zone).date().isoformat(),
                    "changed_at": event.created_at.isoformat(),
                    "by": event.actor_label or "—",
                },
            )
