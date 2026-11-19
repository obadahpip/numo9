"""Inactivity purge (U-07-T09): demo organisations idle for 30 days are purged.

``last_active_at`` is the last signed-in request to the demo (``DemoActivityMiddleware``, at most
one write per ``TOUCH_EVERY``). The daily job purges every demo whose last activity (or creation,
when it never had any) is **more than** ``IDLE_DAYS`` days ago — 30 days exactly is still kept,
the next day it goes:

- its data is wiped (seed and user-data tables, the demo outbox);
- its members are removed (anonymous demo users with no other organisation are deleted, U-07-T11);
- the organisation row stays as a cancelled demo (the audit trail keeps its id), never reused.

Template organisations (``DemoTemplate``) are never purged.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationStatus

from .cloning import wipe
from .models import DemoOutbox, DemoTemplate
from .reset import reset_tables
from .seeders import seed_models

IDLE_DAYS = 30
TOUCH_EVERY = dt.timedelta(minutes=15)


def idle_demos(now: dt.datetime | None = None) -> Any:
    cutoff = (now or timezone.now()) - dt.timedelta(days=IDLE_DAYS)
    templates = DemoTemplate.objects.values("organisation_id")
    return (
        Organisation.objects.filter(is_demo=True, status=OrganisationStatus.DEMO)
        .exclude(pk__in=templates)
        .filter(
            Q(last_active_at__lt=cutoff) | Q(last_active_at__isnull=True, created_at__lt=cutoff)
        )
    )


def purge_demo(organisation: Organisation) -> None:
    from .users import forget_demo_users

    with transaction.atomic():
        locked = Organisation.objects.select_for_update().get(pk=organisation.pk)
        wipe(locked, [*seed_models(), *reset_tables(), DemoOutbox])
        members = list(OrganisationMember.objects.filter(organisation=locked))
        OrganisationMember.objects.filter(organisation=locked).delete()
        forget_demo_users([member.user_id for member in members])
        locked.status = OrganisationStatus.CANCELLED
        locked.demo_seed_version = None
        locked.save(update_fields=["status", "demo_seed_version", "updated_at"])


def purge_inactive(now: dt.datetime | None = None) -> list[int]:
    purged = []
    for organisation in idle_demos(now):
        purge_demo(organisation)
        purged.append(organisation.pk)
    return purged


def touch(organisation: Organisation, now: dt.datetime | None = None) -> bool:
    """Record activity on a demo (at most once per ``TOUCH_EVERY``); True when written."""
    if not organisation.is_demo:
        return False
    now = now or timezone.now()
    last = organisation.last_active_at
    if last is not None and now - last < TOUCH_EVERY:
        return False
    Organisation.objects.filter(pk=organisation.pk).update(last_active_at=now)
    organisation.last_active_at = now
    return True


class DemoActivityMiddleware:
    """After the tenant middleware: a signed-in request to a demo keeps it alive."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        organisation = getattr(request, "organisation", None)
        user = getattr(request, "user", None)
        if organisation is not None and user is not None and user.is_authenticated:
            touch(organisation)
        return self.get_response(request)
