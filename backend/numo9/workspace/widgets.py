"""Phase 0 practice-home widgets (V-04-T03, T04, T05), registered at start-up (``apps.ready``).

Count widgets — each counts the directory rows of the dashboard's scope and returns the directory
filters that list exactly those organisations (V-04-T07):

- ``trials_ending`` — trials ending within 7 days (``status=trial&trial_ending=yes``);
- ``missing_bn`` — no Business Number registered (``bn_missing=yes``);
- ``missing_lock_date`` — no lock date on any module (``lock_missing=yes``);
- ``read_only`` — read-only organisations (``status=read_only``);
- ``dormant_staff`` — practice members dormant for the practice's threshold (60 days), for those
  who manage staff; its drill-down is the staff list.

``workload`` (T04) — per active staff member: the organisations they're assigned to (directly or
through groups, within the dashboard's scope) and their open tasks (0 until tasks exist).
``deadlines`` (T05) — the next 30 days' filing and remittance deadlines from the registered
deadline providers (G-03a GST/HST, N-07 payroll …); none in Phase 0, so an empty list.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext_lazy as _

from .dashboard import (
    COUNT,
    LIST,
    WORKLOAD,
    DashboardContext,
    Widget,
    WidgetAnswer,
    member_organisations,
    register_widget,
)
from .models import DirectoryStatus

TRIAL_ENDING_DAYS = 7
DEADLINE_DAYS = 30


def _count(filters: dict[str, list[str]], rows: Callable[[DashboardContext], Any]) -> Any:
    def provider(ctx: DashboardContext) -> WidgetAnswer:
        return WidgetAnswer(count=rows(ctx).count(), filters=ctx.scoped(filters))

    return provider


def trial_window(now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    return now, now + dt.timedelta(days=TRIAL_ENDING_DAYS)


def _trials_ending(ctx: DashboardContext) -> Any:
    start, end = trial_window(ctx.now)
    return ctx.rows.filter(
        status=DirectoryStatus.TRIAL, trial_ends_at__gte=start, trial_ends_at__lte=end
    )


def _manages_staff(ctx: DashboardContext) -> bool:
    from numo9.rbac.resolver import has_practice_perm

    return has_practice_perm(ctx.user, ctx.practice, "practice.staff.manage")


def _dormant(ctx: DashboardContext) -> WidgetAnswer:
    from numo9.staff.dormant import dormant_staff

    staff = dormant_staff(ctx.practice, ctx.now)
    return WidgetAnswer(
        count=len(staff),
        href=f"/p/{ctx.practice.public_id}/staff",
        items=[{"name": s["name"], "email": s["email"], "days": s["days"]} for s in staff],
    )


# ---- workload (T04) ------------------------------------------------------------------------


def workload(ctx: DashboardContext) -> WidgetAnswer:
    from numo9.tenancy.models import PracticeMember

    visible = set(ctx.rows.values_list("organisation_id", flat=True))
    members = PracticeMember.objects.filter(
        practice=ctx.practice, suspended_at__isnull=True
    ).select_related("user")
    items: list[dict[str, Any]] = []
    for member in members:
        count = len(member_organisations(member) & visible)
        items.append(
            {
                "id": str(member.user.public_id),
                "name": member.user.name or member.user.email,
                "role": member.role,
                "organisations": count,
                "open_tasks": open_tasks(member),
            }
        )
    items.sort(key=lambda item: (-item["organisations"], item["name"].lower()))
    return WidgetAnswer(count=len(items), items=items)


def open_tasks(member: Any) -> int:
    """Open tasks of the member: none until tasks exist (practice management, Phase 4)."""
    return 0


# ---- deadlines (T05) ------------------------------------------------------------------------


@dataclass(frozen=True)
class Deadline:
    """A filing or remittance due date of one organisation."""

    date: dt.date
    kind: str  # "gst_hst", "payroll_remittance", "t2", "t4" …
    label: str
    organisation_id: int


#: ``provider(organisation_ids, start, end) -> list[Deadline]``.
DeadlineProvider = Callable[[set[int], dt.date, dt.date], list[Deadline]]
_deadline_providers: dict[str, DeadlineProvider] = {}


def register_deadline_provider(name: str, provider: DeadlineProvider) -> None:
    _deadline_providers[name] = provider


def unregister_deadline_provider(name: str) -> None:
    _deadline_providers.pop(name, None)


def no_deadlines_yet(organisations: set[int], start: dt.date, end: dt.date) -> list[Deadline]:
    """The Phase 0 stub: no tax or payroll module yet, so no deadline."""
    return []


def deadlines(ctx: DashboardContext) -> WidgetAnswer:
    from django.utils import timezone

    start = timezone.localdate(ctx.now)
    end = start + dt.timedelta(days=DEADLINE_DAYS)
    names = dict(ctx.rows.values_list("organisation_id", "name"))
    public = dict(ctx.rows.values_list("organisation_id", "organisation__public_id"))
    found: list[Deadline] = []
    for provider in list(_deadline_providers.values()):
        found.extend(provider(set(names), start, end))
    found = [d for d in found if d.organisation_id in names and start <= d.date <= end]
    found.sort(key=lambda d: (d.date, names[d.organisation_id].lower()))
    return WidgetAnswer(
        count=len(found),
        items=[
            {
                "date": d.date.isoformat(),
                "kind": d.kind,
                "label": d.label,
                "organisation_id": str(public[d.organisation_id]),
                "organisation_name": names[d.organisation_id],
            }
            for d in found
        ],
    )


def register_phase0_widgets() -> None:
    register_widget(
        Widget(
            "trials_ending",
            _("Trials ending in 7 days"),
            COUNT,
            _count({"status": ["trial"], "trial_ending": ["yes"]}, _trials_ending),
            order=10,
        )
    )
    register_widget(
        Widget(
            "missing_bn",
            _("Organisations without a BN"),
            COUNT,
            _count({"bn_missing": ["yes"]}, lambda ctx: ctx.rows.filter(bn="")),
            order=20,
        )
    )
    register_widget(
        Widget(
            "missing_lock_date",
            _("No lock date set"),
            COUNT,
            _count({"lock_missing": ["yes"]}, lambda ctx: ctx.rows.filter(lock_date__isnull=True)),
            order=30,
        )
    )
    register_widget(
        Widget(
            "read_only",
            _("Read-only organisations"),
            COUNT,
            _count(
                {"status": ["read_only"]},
                lambda ctx: ctx.rows.filter(status=DirectoryStatus.READ_ONLY),
            ),
            order=40,
        )
    )
    register_widget(
        Widget(
            "dormant_staff",
            _("Dormant staff"),
            COUNT,
            _dormant,
            description=_("No sign-in for the practice's dormant threshold (60 days)."),
            visible=_manages_staff,
            order=50,
        )
    )
    register_widget(
        Widget(
            "deadlines",
            _("Deadlines in the next 30 days"),
            LIST,
            deadlines,
            description=_(
                "GST/HST, payroll remittances, T2 and T4 — from the tax and payroll modules."
            ),
            order=60,
        )
    )
    register_widget(
        Widget(
            "workload",
            _("Workload"),
            WORKLOAD,
            workload,
            description=_("Organisations per staff member and their open tasks."),
            order=70,
        )
    )
    register_deadline_provider("phase0", no_deadlines_yet)
