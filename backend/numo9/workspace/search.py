"""Organisation directory search, filters, facets and sorting (V-01-T04).

Everything here starts from ``directory_scope(user, practice)``: the practice's directory rows that
the user may see — every client of the practice for a practice-wide role (practice admin), only the
clients the user is assigned to otherwise (groups join with V-02), and always intersected with the
access resolver (A-01-T05), so an organisation the user cannot open is never listed, counted or
matched (isolation tests: ``tests/test_workspace_isolation.py``).

**Search** (``q``) — PostgreSQL full text over ``search_vector`` (``simple`` + ``unaccent``): every
word must match the start of a word (prefix: "map sup" finds "Maple Leaf Supply"), accents and case
ignored. A query made of digits, spaces and dashes is also matched against the BN anywhere in its
nine digits (trigram index): "123 456" finds ``123456789``. Results are ranked (name, legal name and
BN first) unless a sort is chosen.

**Filters** — any of several values within a filter (OR), every filter together (AND):
``package``, ``status``, ``province``, ``fye`` (month), ``gst_cycle``, ``payroll``, ``overdue``,
``unfiled`` (``yes`` / ``no``), ``tag`` and ``group`` (V-02-T08: a group's public id; an
organisation in the group **or any of its sub-groups** matches). The practice dashboard's
drill-downs (V-04-T07) add ``trial_ending`` (a trial ending within 7 days), ``bn_missing``,
``lock_missing`` (no lock date on any module) and ``mine`` (the organisations the user is assigned
to — directly or through a group — as opposed to the whole practice), ``yes`` / ``no`` each.
Archived organisations (cancelled) are left out unless ``include_archived`` (or the status
filter names ``archived``).

**Facets** — for each filter, how many organisations each value would show **with every other
filter applied** (the usual faceted-search rule): choosing a value in a filter that had none
selected narrows the list to exactly the count shown next to it.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Case, F, Q, QuerySet, Value, When

from numo9.tenancy.access import PRACTICE_WIDE_ROLES, accessible_organisations
from numo9.tenancy.models import Practice, PracticeAssignment, PracticeMember

from .models import (
    DirectoryStatus,
    GroupStaffAssignment,
    OrgDirectorySummary,
    OrgGroup,
    OrgGroupMembership,
)

YES, NO = "yes", "no"
BOOLEAN_FILTERS: dict[str, Q] = {
    "payroll": Q(payroll_enabled=True),
    "overdue": Q(overdue_count__gt=0),
    "unfiled": Q(unfiled_count__gt=0),
    # Practice dashboard drill-downs (V-04-T07).
    "bn_missing": Q(bn=""),
    "lock_missing": Q(lock_date__isnull=True),
}
#: Yes/no filters computed per request: a trial ending within ``TRIAL_ENDING_DAYS`` (time), the
#: organisations the user is assigned to (the user).
DYNAMIC_FILTERS: tuple[str, ...] = ("trial_ending", "mine")
TRIAL_ENDING_DAYS = 7  # also the dashboard's trials_ending widget (V-04)
VALUE_FILTERS: dict[str, str] = {
    "package": "package",
    "status": "status",
    "province": "province",
    "fye": "fye_month",
    "gst_cycle": "gst_cycle",
}
FILTERS: tuple[str, ...] = (*VALUE_FILTERS, *BOOLEAN_FILTERS, *DYNAMIC_FILTERS, "tag", "group")
#: Every yes/no filter (static and per request).
YES_NO_FILTERS: frozenset[str] = frozenset({*BOOLEAN_FILTERS, *DYNAMIC_FILTERS})

#: Sort keys of the API → model fields (``-key`` sorts descending).
SORTS: dict[str, tuple[str, ...]] = {
    "name": ("name",),
    "legal_name": ("legal_name",),
    "bn": ("bn",),
    "owner": ("owner_name",),
    "industry": ("industry",),
    "province": ("province",),
    "package": ("package",),
    "status": ("status",),
    "trial_ends": ("trial_ends_at",),
    "fye": ("fye_month", "fye_day"),
    "gst_cycle": ("gst_cycle",),
    "payroll": ("payroll_enabled",),
    "overdue": ("overdue_count",),
    "unfiled": ("unfiled_count",),
}
#: Text columns whose empty value sorts last whichever the direction.
_BLANK_LAST = frozenset(
    {"legal_name", "bn", "owner_name", "industry", "province", "package", "gst_cycle"}
)

MIN_BN_DIGITS = 3
_WORD = re.compile(r"[0-9a-z]+")


def fold(text: str) -> str:
    """Lower case without accents (what ``unaccent`` + ``simple`` do in the database)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def query_words(q: str) -> list[str]:
    return _WORD.findall(fold(q))


def bn_digits(q: str) -> str:
    """The digits of a BN-looking query ("123 456", "123-456-789"), else ""."""
    compact = re.sub(r"[\s\-]", "", q)
    return compact if compact.isdigit() and len(compact) >= MIN_BN_DIGITS else ""


@dataclass
class DirectoryParams:
    q: str = ""
    filters: dict[str, list[str]] = field(default_factory=dict)
    include_archived: bool = False
    sort: list[str] = field(default_factory=list)  # ["name", "-overdue"]
    page: int = 1
    page_size: int = 50
    group_by: str = ""  # "group": group headers (V-02-T08)


def directory_scope(user: Any, practice: Practice) -> QuerySet[OrgDirectorySummary]:
    """The practice's directory rows the user may see (empty for a non-member)."""
    none = OrgDirectorySummary.objects.none()
    if user is None or not user.is_authenticated or not user.is_active:
        return none
    member = PracticeMember.objects.filter(
        practice=practice, user=user, suspended_at__isnull=True
    ).first()
    if member is None:
        return none
    assignments = PracticeAssignment.objects.filter(practice=practice, active=True)
    rows = OrgDirectorySummary.objects.filter(practice=practice)
    if member.role not in PRACTICE_WIDE_ROLES:
        direct = assignments.filter(assigned_staff=member).values("organisation_id")
        rows = rows.filter(
            Q(organisation_id__in=direct)
            | Q(organisation_id__in=group_scope(member))  # through the practice's groups (V-02)
        )
    rows = rows.filter(organisation_id__in=assignments.values("organisation_id"))
    return rows.filter(organisation_id__in=accessible_organisations(user).values("pk"))


def group_scope(member: PracticeMember) -> list[int]:
    """Organisations a staff member reaches through this practice's groups: filed in a group
    they're assigned to or one of its sub-groups (V-02-T08)."""
    paths = list(
        GroupStaffAssignment.objects.filter(practice_member=member).values_list(
            "group__path", flat=True
        )
    )
    if not paths:
        return []
    cover = Q()
    for path in paths:
        cover |= Q(group__path__startswith=path)
    return list(
        OrgGroupMembership.objects.filter(group__practice_id=member.practice_id)
        .filter(cover)
        .values_list("organisation_id", flat=True)
        .distinct()
    )


@dataclass(frozen=True)
class GroupInfo:
    id: str  # public id
    name: str
    path: str
    depth: int
    parent: str | None


def practice_groups(practice: Practice) -> list[GroupInfo]:
    """The practice's groups in tree order (depth-first, siblings by name)."""
    rows = list(
        OrgGroup.objects.filter(practice=practice)
        .order_by("path")
        .values_list("public_id", "name", "path", "depth")
    )
    by_path = {path: str(public_id) for public_id, _n, path, _d in rows}
    return [
        GroupInfo(
            id=str(public_id),
            name=name,
            path=path,
            depth=depth,
            parent=by_path.get(path[: -OrgGroup.steplen]) if depth > 1 else None,
        )
        for public_id, name, path, depth in rows
    ]


def organisation_groups(practice: Practice) -> tuple[dict[int, set[str]], dict[int, list[str]]]:
    """Per organisation: the groups it's in **with their ancestors** (what the group filter
    matches) and the groups it's filed in directly (the row's badges), as public ids."""
    groups = practice_groups(practice)
    by_path = {group.path: group for group in groups}
    within: dict[int, set[str]] = {}
    direct: dict[int, list[str]] = {}
    memberships = OrgGroupMembership.objects.filter(group__practice=practice).values_list(
        "organisation_id", "group__path"
    )
    for organisation_id, path in memberships.order_by("group__path"):
        group = by_path[path]
        direct.setdefault(organisation_id, []).append(group.id)
        ancestors = within.setdefault(organisation_id, set())
        for depth in range(1, group.depth + 1):
            ancestor = by_path.get(path[: depth * OrgGroup.steplen])
            if ancestor is not None:
                ancestors.add(ancestor.id)
    return within, direct


class DirectoryQuery:
    """One directory request: ``page()`` for the rows, ``facets()`` for the counts."""

    def __init__(
        self, user: Any, practice: Practice, params: DirectoryParams, now: Any = None
    ) -> None:
        from django.utils import timezone

        self.params = params
        self.practice = practice
        self.user = user
        self.now = now or timezone.now()
        self.scope = directory_scope(user, practice)
        words = query_words(params.q)
        self.search: SearchQuery | None = (
            SearchQuery(" & ".join(f"{w}:*" for w in words), search_type="raw", config="simple")
            if words
            else None
        )
        self.bn = bn_digits(params.q)

    # ---- building blocks -----------------------------------------------------------------

    def _archived_visible(self) -> bool:
        return self.params.include_archived or DirectoryStatus.ARCHIVED in self.params.filters.get(
            "status", []
        )

    def visible(self) -> QuerySet[OrgDirectorySummary]:
        """The scope without archived organisations (unless asked for): the "of N" total."""
        rows = self.scope
        if not self._archived_visible():
            rows = rows.exclude(status=DirectoryStatus.ARCHIVED)
        return rows

    def _searched(self) -> QuerySet[OrgDirectorySummary]:
        rows = self.visible()
        if self.search is None and not self.bn:
            return rows
        condition = Q()
        if self.search is not None:
            condition |= Q(search_vector=self.search)
        if self.bn:
            condition |= Q(bn__contains=self.bn)
        return rows.filter(condition)

    def _filter(self, name: str, values: list[str]) -> Q:
        if name in VALUE_FILTERS:
            column = VALUE_FILTERS[name]
            return Q(**{f"{column}__in": [int(v) for v in values] if name == "fye" else values})
        if name in YES_NO_FILTERS:
            test = self._dynamic_q(name) if name in DYNAMIC_FILTERS else BOOLEAN_FILTERS[name]
            condition = Q()
            if YES in values:
                condition |= test
            if NO in values:
                condition |= ~test
            return condition
        condition = Q()
        if name == "group":  # any of the chosen groups, sub-groups included
            paths = list(
                OrgGroup.objects.filter(
                    practice=self.practice, public_id__in=[_uuid_or_none(v) for v in values]
                ).values_list("path", flat=True)
            )
            if not paths:
                return Q(pk__in=[])
            cover = Q()
            for path in paths:
                cover |= Q(group__path__startswith=path)
            inside = OrgGroupMembership.objects.filter(group__practice=self.practice).filter(cover)
            return Q(organisation_id__in=inside.values("organisation_id"))
        for tag in values:  # tag: any of the chosen tags
            condition |= Q(tags__contains=[tag])
        return condition

    def trial_window(self) -> tuple[Any, Any]:
        import datetime as dt

        return self.now, self.now + dt.timedelta(days=TRIAL_ENDING_DAYS)

    def mine(self) -> set[int]:
        """The organisations the user is assigned to in this practice (direct and groups)."""
        if not hasattr(self, "_mine"):
            from .dashboard import member_organisations

            member = PracticeMember.objects.filter(
                practice=self.practice, user=self.user, suspended_at__isnull=True
            ).first()
            self._mine: set[int] = member_organisations(member) if member else set()
        return self._mine

    def _dynamic_q(self, name: str) -> Q:
        if name == "trial_ending":
            start, end = self.trial_window()
            return Q(status=DirectoryStatus.TRIAL, trial_ends_at__gte=start, trial_ends_at__lte=end)
        return Q(organisation_id__in=sorted(self.mine()))

    def filtered(self, *, skip: str | None = None) -> QuerySet[OrgDirectorySummary]:
        rows = self._searched()
        for name, values in self.params.filters.items():
            if name != skip and values:
                rows = rows.filter(self._filter(name, values))
        return rows

    def _ordering(self) -> list[Any]:
        order: list[Any] = []
        for key in self.params.sort:
            desc = key.startswith("-")
            for column in SORTS[key.lstrip("-")]:
                if column in _BLANK_LAST:
                    order.append(Case(When(**{column: ""}, then=Value(1)), default=Value(0)))
                if column == "trial_ends_at":
                    expression = (
                        F(column).desc(nulls_last=True) if desc else F(column).asc(nulls_last=True)
                    )
                else:
                    expression = F(column).desc() if desc else F(column).asc()
                order.append(expression)
        if not self.params.sort and self.search is not None:
            order.append(F("rank").desc())
        order += [F("name").asc(), F("organisation_id").asc()]
        return order

    # ---- answers ---------------------------------------------------------------------------

    def results(self) -> QuerySet[OrgDirectorySummary]:
        rows = self.filtered()
        if self.search is not None:
            rows = rows.annotate(rank=SearchRank(F("search_vector"), self.search))
        return rows.order_by(*self._ordering()).select_related("organisation")

    # Facets and counts come from one slim read of the searched rows (at most a practice's
    # directory: a few thousand small tuples), evaluated in Python with the same rules as
    # ``_filter`` — one query instead of one per filter (V-01-T07: p95 < 300 ms).
    _SLIM = (
        "status",
        "province",
        "package",
        "fye_month",
        "gst_cycle",
        "payroll_enabled",
        "overdue_count",
        "unfiled_count",
        "tags",
        "organisation_id",
        "bn",
        "lock_date",
        "trial_ends_at",
    )

    def groups_of(self) -> tuple[dict[int, set[str]], dict[int, list[str]]]:
        if not hasattr(self, "_groups_of"):
            self._groups_of = organisation_groups(self.practice)
        return self._groups_of

    def _slim(self) -> list[dict[str, Any]]:
        if not hasattr(self, "_slim_rows"):
            within, _direct = self.groups_of()
            start, end = self.trial_window()
            mine = self.mine() if "mine" in self.params.filters else set()
            self._slim_rows = [
                {
                    "status": status,
                    "province": province,
                    "package": package,
                    "fye": str(fye),
                    "gst_cycle": gst,
                    "payroll": payroll,
                    "overdue": overdue > 0,
                    "unfiled": unfiled > 0,
                    "tag": set(tags or []),
                    "group": within.get(organisation_id, set()),
                    "organisation_id": organisation_id,
                    "bn_missing": not bn,
                    "lock_missing": lock_date is None,
                    "trial_ending": status == DirectoryStatus.TRIAL
                    and trial_ends is not None
                    and start <= trial_ends <= end,
                    "mine": organisation_id in mine,
                }
                for (
                    status,
                    province,
                    package,
                    fye,
                    gst,
                    payroll,
                    overdue,
                    unfiled,
                    tags,
                    organisation_id,
                    bn,
                    lock_date,
                    trial_ends,
                ) in self._searched().values_list(*self._SLIM)
            ]
        return self._slim_rows

    def _passes(self, row: dict[str, Any], *, skip: str | None = None) -> bool:
        for name, values in self.params.filters.items():
            if name == skip or not values:
                continue
            value = row[name]
            if name in ("tag", "group"):
                if not value & set(values):
                    return False
            elif name in YES_NO_FILTERS:
                if (YES if value else NO) not in values:
                    return False
            elif value not in values:
                return False
        return True

    def total(self) -> int:
        """Organisations in the directory without search or filters (the "of N")."""
        if self.search is None and not self.bn:
            return len(self._slim())
        return self.visible().count()

    def count(self) -> int:
        """Rows matching the search and every filter (same answer as ``filtered().count()``)."""
        return sum(1 for row in self._slim() if self._passes(row))

    def page(self) -> tuple[list[OrgDirectorySummary], int]:
        """The requested page of rows and the number of matching rows."""
        start = (self.params.page - 1) * self.params.page_size
        return list(self.results()[start : start + self.params.page_size]), self.count()

    def facets(self) -> dict[str, list[dict[str, Any]]]:
        """Per filter: ``[{"value", "count"}]`` with every other filter applied."""
        answer: dict[str, list[dict[str, Any]]] = {}
        slim = self._slim()
        for name in FILTERS:
            counts: Counter[str] = Counter()
            for row in slim:
                if not self._passes(row, skip=name):
                    continue
                value = row[name]
                if name in ("tag", "group"):
                    counts.update(value)
                elif name in YES_NO_FILTERS:
                    counts[YES if value else NO] += 1
                elif value not in ("", None):
                    counts[value] += 1
            if name in YES_NO_FILTERS:
                counts.setdefault(YES, 0)
                counts.setdefault(NO, 0)
            if name == "status":  # every status is always offered (zero ones dimmed)
                for status in DirectoryStatus.values:
                    if status != DirectoryStatus.ARCHIVED or self._archived_visible():
                        counts.setdefault(status, 0)
            for value in self.params.filters.get(name, []):  # a chosen value stays listed
                counts.setdefault(value, 0)
            if name == "group":  # every group is offered, in tree order
                order = [group.id for group in practice_groups(self.practice)]
                answer[name] = [{"value": gid, "count": counts.get(gid, 0)} for gid in order]
                continue
            answer[name] = [{"value": v, "count": n} for v, n in _ordered(name, dict(counts))]
        return answer

    def grouping(self) -> list[dict[str, Any]]:
        """Group-by headers (V-02-T08): for each group in tree order, the matching organisations
        filed in it directly (ids in result order) and its count; then those in no group."""
        _within, direct = self.groups_of()
        matching = [row["organisation_id"] for row in self._slim() if self._passes(row)]
        order = {pk: index for index, pk in enumerate(self._result_ids())}
        matching.sort(key=lambda pk: order.get(pk, len(order)))
        buckets: dict[str | None, list[int]] = {}
        for pk in matching:
            filed: list[str | None] = [*direct.get(pk, [])] or [None]
            for gid in filed:
                buckets.setdefault(gid, []).append(pk)
        out: list[dict[str, Any]] = []
        for group in practice_groups(self.practice):
            ids = buckets.get(group.id, [])
            out.append({"group": group, "organisation_ids": ids, "count": len(ids)})
        ungrouped = buckets.get(None, [])
        out.append({"group": None, "organisation_ids": ungrouped, "count": len(ungrouped)})
        return out

    def _result_ids(self) -> list[int]:
        return list(self.results().values_list("organisation_id", flat=True))


def _uuid_or_none(value: str) -> Any:
    import uuid

    try:
        return uuid.UUID(value)
    except ValueError:
        return None


_STATUS_ORDER = {status: index for index, status in enumerate(DirectoryStatus.values)}


def _ordered(name: str, counts: dict[str, int]) -> list[tuple[str, int]]:
    if name == "status":
        return sorted(counts.items(), key=lambda item: _STATUS_ORDER.get(item[0], 99))
    if name == "fye":
        return sorted(counts.items(), key=lambda item: int(item[0]))
    if name in YES_NO_FILTERS:
        return [(YES, counts.get(YES, 0)), (NO, counts.get(NO, 0))]
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


__all__ = [
    "FILTERS",
    "YES_NO_FILTERS",
    "SORTS",
    "DirectoryParams",
    "DirectoryQuery",
    "bn_digits",
    "directory_scope",
    "fold",
    "query_words",
]
