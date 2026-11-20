"""A practice fixture for the dashboard tests (V-04): known counts per widget."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationStatus, Practice, PracticeMember
from numo9.workspace.models import OrgDirectorySummary
from numo9.workspace.summary import rebuild_all
from tests.workspace_helpers import client_org, member, practice, user, valid_bn


@dataclass
class Firm:
    practice: Practice
    admin: Any
    sam: PracticeMember  # accountant, assigned to 3 organisations
    lina: PracticeMember  # reviewer, dormant, assigned to none
    orgs: dict[str, Organisation]


def build_firm() -> Firm:
    """Six clients of Abuodeh CPA:

    ===============  ======  ==========  =========  ==========  ============
    organisation     staff   status      BN         lock date   trial ends
    ===============  ======  ==========  =========  ==========  ============
    Maple            Sam     trial       —          —           in 3 days
    Birch            Sam     trial       yes        yes         in 10 days
    Cedar            Sam     read_only   —          yes         —
    Pine             —       active      yes        —           —
    Spruce           —       read_only   yes        yes         —
    Fir (archived)   —       cancelled   —          —           —
    ===============  ======  ==========  =========  ==========  ============
    """
    admin = user("ada@cpa.ca", name="Ada Admin")
    firm = practice("Abuodeh CPA", admin=admin)
    sam = member(firm, user("sam@cpa.ca", name="Sam Patel"))
    lina = member(firm, user("lina@cpa.ca", name="Lina Roy"), role="reviewer")
    now = timezone.now()
    type(admin).objects.filter(pk__in=[admin.pk, sam.user_id]).update(last_login=now)
    type(admin).objects.filter(pk=lina.user_id).update(last_login=now - dt.timedelta(days=61))
    plan = [
        ("Maple", [sam], OrganisationStatus.TRIAL, "", False, 3),
        ("Birch", [sam], OrganisationStatus.TRIAL, valid_bn(11111111), True, 10),
        ("Cedar", [sam], OrganisationStatus.READ_ONLY, "", True, None),
        ("Pine", [], OrganisationStatus.ACTIVE, valid_bn(22222222), False, None),
        ("Spruce", [], OrganisationStatus.READ_ONLY, valid_bn(33333333), True, None),
        ("Fir", [], OrganisationStatus.CANCELLED, "", False, None),
    ]
    orgs: dict[str, Organisation] = {}
    for name, staff, status, bn, locked, _trial in plan:
        org = client_org(firm, name, staff=staff, status=status, bn=bn, settings={})
        if locked:
            with org_context(org):
                LockDate(
                    organisation=org, module="gl", level="everyone", date=dt.date(2025, 12, 31)
                ).save()
        orgs[name] = org
    rebuild_all()
    for name, *_rest, trial_days in plan:
        if trial_days is not None:
            OrgDirectorySummary.objects.filter(organisation=orgs[name]).update(
                trial_ends_at=now + dt.timedelta(days=trial_days)
            )
    return Firm(practice=firm, admin=admin, sam=sam, lina=lina, orgs=orgs)
