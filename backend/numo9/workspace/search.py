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
``unfiled`` (``yes`` / ``no``) and ``tag``. Archived organisations (cancelled) are left out unless
``include_archived`` (or the status filter names ``archived``).

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

from .models import DirectoryStatus, OrgDirectorySummary

YES, NO = "yes", "no"
BOOLEAN_FILTERS: dict[str, Q] = {
    "payroll": Q(payroll_enabled=True),
    "overdue": Q(overdue_count__gt=0),
    "unfiled": Q(unfiled_count__gt=0),
}
VALUE_FILTERS: dict[str, str] = {
    "package": "package",
    "status": "status",
    "province": "province",
    "fye": "fye_month",
    "gst_cycle": "gst_cycle",
}
FILTERS: tuple[str, ...] = (*VALUE_FILTERS, *BOOLEAN_FILTERS, "tag")

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


def directory_scope(user: Any, practice: Practice) -> QuerySet[OrgDirectorySummary]:
    """The practice's directory rows the user may see (empty for a non-member)."""
    none = OrgDirectorySummary.objects.none()
    if user is None or not user.is_authenticated or not user.is_active:
        return none
    member = PracticeMember.objects.filter(practice=practice, user=user).first()
    if member is None:
        return none
    assignments = PracticeAssignment.objects.filter(practice=practice, active=True)
    if member.role not in PRACTICE_WIDE_ROLES:
        assignments = assignments.filter(assigned_staff=member)
    return OrgDirectorySummary.objects.filter(
        practice=practice,
        organisation_id__in=assignments.values("organisation_id"),
    ).filter(organisation_id__in=accessible_organisations(user).values("pk"))


class DirectoryQuery:
    """One directory request: ``page()`` for the rows, ``facets()`` for the counts."""

    def __init__(self, user: Any, practice: Practice, params: DirectoryParams) -> None:
        self.params = params
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
        if name in BOOLEAN_FILTERS:
            condition = Q()
            if YES in values:
                condition |= BOOLEAN_FILTERS[name]
            if NO in values:
                condition |= ~BOOLEAN_FILTERS[name]
            return condition
        condition = Q()
        for tag in values:  # tag: any of the chosen tags
            condition |= Q(tags__contains=[tag])
        return condition

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
    )

    def _slim(self) -> list[dict[str, Any]]:
        if not hasattr(self, "_slim_rows"):
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
                ) in self._searched().values_list(*self._SLIM)
            ]
        return self._slim_rows

    def _passes(self, row: dict[str, Any], *, skip: str | None = None) -> bool:
        for name, values in self.params.filters.items():
            if name == skip or not values:
                continue
            value = row[name]
            if name == "tag":
                if not value & set(values):
                    return False
            elif name in BOOLEAN_FILTERS:
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
                if name == "tag":
                    counts.update(value)
                elif name in BOOLEAN_FILTERS:
                    counts[YES if value else NO] += 1
                elif value not in ("", None):
                    counts[value] += 1
            if name in BOOLEAN_FILTERS:
                counts.setdefault(YES, 0)
                counts.setdefault(NO, 0)
            if name == "status":  # every status is always offered (zero ones dimmed)
                for status in DirectoryStatus.values:
                    if status != DirectoryStatus.ARCHIVED or self._archived_visible():
                        counts.setdefault(status, 0)
            for value in self.params.filters.get(name, []):  # a chosen value stays listed
                counts.setdefault(value, 0)
            answer[name] = [{"value": v, "count": n} for v, n in _ordered(name, dict(counts))]
        return answer


_STATUS_ORDER = {status: index for index, status in enumerate(DirectoryStatus.values)}


def _ordered(name: str, counts: dict[str, int]) -> list[tuple[str, int]]:
    if name == "status":
        return sorted(counts.items(), key=lambda item: _STATUS_ORDER.get(item[0], 99))
    if name == "fye":
        return sorted(counts.items(), key=lambda item: int(item[0]))
    if name in BOOLEAN_FILTERS:
        return [(YES, counts.get(YES, 0)), (NO, counts.get(NO, 0))]
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


__all__ = [
    "FILTERS",
    "SORTS",
    "DirectoryParams",
    "DirectoryQuery",
    "bn_digits",
    "directory_scope",
    "fold",
    "query_words",
]
