"""Practices and organisations across every tenant, for the console (U-06-T03).

``GET /api/v1/platform/organisations`` — filters, any of several values within one, all together:

==============  ============================================================================
``q``           name contains (accents and case ignored)
``status``      organisation status (demo, trial, active, grace, read_only, cancelled)
``package``     current subscription's package code (``none`` = no package)
``province``    the organisation's mailing province (two letters)
``created_from`` / ``created_to``   creation date range (inclusive, ISO dates)
``page`` / ``page_size``            1-based; 1–200 a page (default 50); newest first
==============  ============================================================================

``GET /api/v1/platform/practices`` — ``q``, ``created_from`` / ``created_to``, paging; each
practice with its staff and client counts.

Both need ``platform.console.view``. Platform data across tenants: the queries use the base
managers deliberately (no organisation context) and return directory facts only.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

from django.contrib.postgres.lookups import Unaccent
from django.db.models import Count, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Lower

from numo9.entitlements.models import Subscription, SubscriptionStatus
from numo9.orgsettings.models import OrganisationSettings
from numo9.tenancy.models import Organisation, OrganisationStatus, Practice

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


class BadFilter(ValueError):
    def __init__(self, name: str, value: str) -> None:
        super().__init__(name)
        self.name, self.value = name, value


def _date(query: Any, name: str) -> dt.date | None:
    value = (query.get(name) or "").strip()
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise BadFilter(name, value) from None


def _int(query: Any, name: str, default: int, low: int, high: int) -> int:
    value = query.get(name)
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except ValueError:
        raise BadFilter(name, str(value)) from None
    if not low <= number <= high:
        raise BadFilter(name, str(value))
    return number


def _values(query: Any, name: str) -> list[str]:
    return [v.strip() for v in query.getlist(name) if v.strip()]


def _created(rows: QuerySet[Any], query: Any) -> QuerySet[Any]:
    start, end = _date(query, "created_from"), _date(query, "created_to")
    if start:
        rows = rows.filter(created_at__date__gte=start)
    if end:
        rows = rows.filter(created_at__date__lte=end)
    return rows


def _search(rows: QuerySet[Any], query: Any) -> QuerySet[Any]:
    q = (query.get("q") or "").strip()[:200]
    if q:
        from numo9.workspace.search import fold

        rows = rows.annotate(name_plain=Lower(Unaccent("name"))).filter(
            name_plain__contains=fold(q)
        )
    return rows


def _page(rows: QuerySet[Any], query: Any) -> tuple[list[Any], dict[str, int]]:
    page = _int(query, "page", 1, 1, 1_000_000)
    size = _int(query, "page_size", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    count = rows.count()
    start = (page - 1) * size
    return list(rows[start : start + size]), {
        "count": count,
        "page": page,
        "page_size": size,
        "pages": max(1, math.ceil(count / size)),
    }


def organisations(query: Any) -> dict[str, Any]:
    current = (
        Subscription._base_manager.filter(organisation=OuterRef("pk"), deleted_at__isnull=True)
        .exclude(status=SubscriptionStatus.CANCELLED)
        .order_by("-created_at")
    )
    province = OrganisationSettings._base_manager.filter(organisation=OuterRef("pk")).values(
        "mailing_province"
    )[:1]
    rows = Organisation.objects.annotate(
        package_code=Subquery(current.values("package__code")[:1]),
        subscription_status=Subquery(current.values("status")[:1]),
        province=Subquery(province),
    )
    statuses = _values(query, "status")
    for value in statuses:
        if value not in OrganisationStatus.values:
            raise BadFilter("status", value)
    if statuses:
        rows = rows.filter(status__in=statuses)
    packages = _values(query, "package")
    if packages:
        condition = Q(package_code__in=[p for p in packages if p != "none"])
        if "none" in packages:
            condition |= Q(package_code__isnull=True)
        rows = rows.filter(condition)
    provinces = [p.upper() for p in _values(query, "province")]
    if provinces:
        rows = rows.filter(province__in=provinces)
    rows = _search(_created(rows, query), query).order_by("-created_at", "-pk")
    items, paging = _page(rows, query)
    return {
        **paging,
        "results": [
            {
                "id": org.public_id,
                "name": org.name,
                "status": org.status,
                "is_demo": org.status == OrganisationStatus.DEMO,
                "package": org.package_code or "",
                "subscription_status": org.subscription_status or "",
                "province": org.province or "",
                "created_at": org.created_at,
            }
            for org in items
        ],
    }


def practices(query: Any) -> dict[str, Any]:
    rows = Practice.objects.annotate(
        staff_count=Count("members", distinct=True),
        client_count=Count("assignments", filter=Q(assignments__active=True), distinct=True),
    )
    rows = _search(_created(rows, query), query).order_by("-created_at", "-pk")
    items, paging = _page(rows, query)
    return {
        **paging,
        "results": [
            {
                "id": practice.public_id,
                "name": practice.name,
                "staff_count": practice.staff_count,
                "client_count": practice.client_count,
                "created_at": practice.created_at,
            }
            for practice in items
        ],
    }


# ---- one organisation (U-06-T04) ---------------------------------------------------------------


def _timeline(organisation: Organisation) -> list[dict[str, Any]]:
    """The subscription's state history, oldest first: trial started, every status change (from
    the audit log of the subscription), conversion."""
    from numo9.audit.models import AuditEvent
    from numo9.entitlements.models import TrialRegistry

    items: list[dict[str, Any]] = []
    trial = TrialRegistry.objects.filter(organisation=organisation).first()
    if trial is not None:
        items.append({"at": trial.started_at, "kind": "trial_started", "detail": ""})
    events = AuditEvent.platform_events.filter(
        organisation=organisation, object_type="entitlements.Subscription"
    ).order_by("created_at", "id")
    for event in events:
        status = (event.changes or {}).get("status")
        if event.action.endswith(".created"):
            new = status[1] if isinstance(status, list) and len(status) == 2 else ""
            items.append({"at": event.created_at, "kind": "subscribed", "detail": str(new or "")})
        elif isinstance(status, list) and len(status) == 2:
            items.append(
                {"at": event.created_at, "kind": "status", "detail": f"{status[0]} → {status[1]}"}
            )
    if trial is not None and trial.converted_at is not None:
        items.append({"at": trial.converted_at, "kind": "converted", "detail": ""})
    items.sort(key=lambda item: item["at"])
    return items


def organisation_detail(organisation: Organisation) -> dict[str, Any]:
    from numo9.audit.models import AuditEvent
    from numo9.tenancy.models import OrganisationMember, PracticeAssignment

    subscription = (
        Subscription._base_manager.filter(organisation=organisation, deleted_at__isnull=True)
        .select_related("package")
        .order_by("-created_at")
        .first()
    )
    settings_row = OrganisationSettings._base_manager.filter(organisation=organisation).first()
    members = OrganisationMember.objects.filter(organisation=organisation).select_related("user")
    assignments = (
        PracticeAssignment.objects.filter(organisation=organisation)
        .select_related("practice")
        .annotate(staff=Count("assigned_staff", distinct=True))
        .order_by("-active", "practice__name")
    )
    recent = AuditEvent.platform_events.filter(organisation=organisation).order_by(
        "-created_at", "-id"
    )[:20]
    return {
        "id": organisation.public_id,
        "name": organisation.name,
        "status": organisation.status,
        "is_demo": organisation.status == OrganisationStatus.DEMO,
        "province": settings_row.mailing_province if settings_row else "",
        "time_zone": organisation.time_zone,
        "created_at": organisation.created_at,
        "subscription": None
        if subscription is None
        else {
            "status": subscription.status,
            "reason": subscription.status_reason,
            "package": subscription.package.code if subscription.package else "",
            "interval": subscription.interval,
            "current_period_end": subscription.current_period_end,
            "founding": subscription.founding,
        },
        "timeline": _timeline(organisation),
        "users": [
            {
                "id": m.user.public_id,
                "name": m.user.name,
                "email": m.user.email,
                "role": m.role,
                "last_login": m.user.last_login,
            }
            for m in members.order_by("user__name")
        ],
        "practices": [
            {
                "id": a.practice.public_id,
                "name": a.practice.name,
                "role": a.role,
                "active": a.active,
                "staff_count": a.staff,
            }
            for a in assignments
        ],
        "recent_events": [
            {
                "at": e.created_at,
                "action": e.action,
                "actor": e.actor_label,
                "record": e.object_label,
            }
            for e in recent
        ],
    }
