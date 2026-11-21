"""Practice home dashboard (V-04): a registry of widgets, each answered by a provider.

A **widget** (``Widget``) is a card, list or chart of the practice home: a key, a title, a kind
(``count`` — a big number; ``list`` — dated items; ``workload`` — a bar per staff member) and a
**provider**: ``provider(ctx) -> WidgetAnswer``. The context (``DashboardContext``) carries the
practice, the signed-in member, the scope (``mine`` — the organisations the member is assigned
to; ``all`` — every client the member may see, practice-wide roles only) and the directory rows
of that scope (``rows``: ``OrgDirectorySummary`` queryset, never sampled).

``register_widget(widget)`` exposes it on the dashboard (V-04-T02); later phases register their
own (deadlines from G-03a/N-07, unreconciled lines from F-05, approvals from C-04/E-02).
``answer_all(ctx)`` asks every visible widget; a provider that raises answers ``status: error``
for that widget only — the rest of the dashboard still loads (V-04-T06).

A count widget's answer carries ``filters``: the organisation directory's filter parameters that
list exactly the organisations counted (V-04-T07) — the card's link opens the directory with them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.functional import Promise

from numo9.tenancy.access import PRACTICE_WIDE_ROLES
from numo9.tenancy.models import Practice, PracticeMember

from .models import OrgDirectorySummary

logger = logging.getLogger(__name__)

COUNT, LIST, WORKLOAD = "count", "list", "workload"
KINDS: tuple[str, ...] = (COUNT, LIST, WORKLOAD)
MINE, ALL = "mine", "all"


@dataclass
class DashboardContext:
    user: Any
    practice: Practice
    member: PracticeMember
    scope: str  # MINE or ALL
    now: Any = field(default_factory=timezone.now)
    _rows: QuerySet[OrgDirectorySummary] | None = None

    @property
    def practice_wide(self) -> bool:
        return self.member.role in PRACTICE_WIDE_ROLES

    @property
    def rows(self) -> QuerySet[OrgDirectorySummary]:
        """The directory rows of the scope, archived organisations left out (as the directory)."""
        if self._rows is None:
            from .models import DirectoryStatus
            from .search import directory_scope

            rows = directory_scope(self.user, self.practice)
            if self.scope == MINE:
                rows = rows.filter(organisation_id__in=sorted(member_organisations(self.member)))
            self._rows = rows.exclude(status=DirectoryStatus.ARCHIVED)
        return self._rows

    def scoped(self, filters: dict[str, list[str]]) -> dict[str, list[str]]:
        """A widget's directory filters with the scope added (``mine=yes`` for "my
        organisations"), so the drill-down lists the same organisations."""
        return {**filters, "mine": ["yes"]} if self.scope == MINE else dict(filters)


def member_organisations(member: PracticeMember) -> set[int]:
    """The organisations a staff member is assigned to in their practice: directly or through
    the practice's groups (V-02) — "my organisations"."""
    from numo9.tenancy.models import PracticeAssignment

    from .search import group_scope

    direct = PracticeAssignment.objects.filter(
        practice_id=member.practice_id, active=True, assigned_staff=member
    ).values_list("organisation_id", flat=True)
    return {*direct, *group_scope(member)}


@dataclass
class WidgetAnswer:
    count: int | None = None
    filters: dict[str, list[str]] | None = None  # directory drill-down (count widgets)
    href: str = ""  # another drill-down page (dormant staff → the staff list)
    items: list[dict[str, Any]] = field(default_factory=list)  # list / workload widgets


Provider = Callable[[DashboardContext], WidgetAnswer]


@dataclass(frozen=True)
class Widget:
    key: str
    title: Promise | str
    kind: str
    provider: Provider
    description: Promise | str = ""
    #: Who sees it: ``None`` everyone with the directory; else a predicate on the context.
    visible: Callable[[DashboardContext], bool] | None = None
    #: Order on a dashboard nobody customised (lower first).
    order: int = 100

    def shown_to(self, ctx: DashboardContext) -> bool:
        return self.visible is None or bool(self.visible(ctx))


_widgets: dict[str, Widget] = {}


def register_widget(widget: Widget) -> Widget:
    if widget.kind not in KINDS:
        raise ValueError(f"Unknown widget kind {widget.kind!r}: one of {', '.join(KINDS)}.")
    _widgets[widget.key] = widget
    return widget


def unregister_widget(key: str) -> None:
    _widgets.pop(key, None)


def widgets() -> list[Widget]:
    return sorted(_widgets.values(), key=lambda w: (w.order, w.key))


def answer(widget: Widget, ctx: DashboardContext) -> dict[str, Any]:
    """One widget's answer for the API: ``status`` ok with its figures, or error."""
    base: dict[str, Any] = {
        "key": widget.key,
        "title": str(widget.title),
        "description": str(widget.description),
        "kind": widget.kind,
    }
    try:
        result = widget.provider(ctx)
    except Exception:  # a provider's failure is shown on its card, never fails the dashboard
        logger.exception("Dashboard widget %s failed", widget.key)
        return {**base, "status": "error", "count": None, "filters": None, "href": "", "items": []}
    return {
        **base,
        "status": "ok",
        "count": result.count,
        "filters": result.filters,
        "href": result.href,
        "items": result.items,
    }


def answer_all(ctx: DashboardContext) -> list[dict[str, Any]]:
    return [answer(widget, ctx) for widget in widgets() if widget.shown_to(ctx)]
