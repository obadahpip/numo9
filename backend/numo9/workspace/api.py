"""Organisation directory API (V-01-T05), under ``/api/v1/``.

``GET /api/v1/practice/orgs`` — the practice's organisation directory:

=================  ==========================================================================
``practice``       practice public id (also the ``X-Numo9-Practice`` header); may be omitted
                   when the user belongs to exactly one practice
``q``              search: name, legal name, BN (with or without spaces), owner, tags,
                   industry, province — accents and case ignored, word prefixes
``package``,       filters, repeatable (``?province=ON&province=QC`` = either);
``status``,        ``payroll`` / ``overdue`` / ``unfiled`` take ``yes`` / ``no``
``province``,
``fye``, ``gst_cycle``, ``payroll``, ``overdue``, ``unfiled``, ``tag``
``archived``       ``include`` shows archived (cancelled) organisations, hidden by default
``sort``           comma-separated column keys, ``-`` for descending (``-overdue,name``); default
                   relevance when searching, else name
``page``,          1-based page; ``page_size`` 1–2,000 (default 50)
``page_size``
``columns``        comma-separated columns to return (default all); ``id`` and ``name`` always
``facets``         ``0`` leaves the facet counts out (they are included by default)
=================  ==========================================================================

The answer names the practice, ``count`` (matching), ``total`` (all the user's organisations in the
directory, archived ones only when shown), the page, the rows and the facet counts (for each
filter, each value's count with every *other* filter applied — ``search.py``).

Who: a member of the practice with ``practice.directory.view`` (every practice role has it); a
practice-wide role sees every client, other roles their assigned clients. Not a member → 404, the
same answer as an unknown practice. Not organisation-scoped: on the tenant-sweep exempt list, with
its own isolation sweep (``tests/test_workspace_isolation.py``).
"""

from __future__ import annotations

import math
import uuid
from typing import Any, cast

from django.utils import dates, timezone, translation
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.i18n.errors import CatalogueError, api_error
from numo9.orgsettings.validators import Province
from numo9.packages.models import Package
from numo9.rbac.drf import AUTHENTICATED, requires_permission
from numo9.rbac.resolver import has_practice_perm
from numo9.tenancy.middleware import PRACTICE_HEADER
from numo9.tenancy.models import Practice, PracticeMember

from .models import DirectoryStatus, GstCycle, OrgDirectorySummary
from .permissions import DIRECTORY_VIEW
from .search import (
    BOOLEAN_FILTERS,
    FILTERS,
    NO,
    SORTS,
    YES,
    DirectoryParams,
    DirectoryQuery,
    GroupInfo,
    practice_groups,
)
from .serializers import DirectoryPageSerializer

MAX_PAGE_SIZE = 2000
DEFAULT_PAGE_SIZE = 50

#: Output columns → the row fields they add (``id`` and ``name`` are always there).
COLUMNS: dict[str, tuple[str, ...]] = {
    "name": (),
    "legal_name": ("legal_name",),
    "bn": ("bn",),
    "owner": ("owner_name", "owner_email"),
    "industry": ("industry",),
    "province": ("province",),
    "package": ("package", "package_name"),
    "status": ("status", "trial_ends_at", "trial_days_left"),
    "fye": ("fye_month", "fye_day"),
    "gst_cycle": ("gst_cycle",),
    "payroll": ("payroll_enabled",),
    "overdue": ("overdue_count",),
    "unfiled": ("unfiled_count",),
    "tags": ("tags",),
    "groups": ("groups",),
}


# ---- practice ----------------------------------------------------------------------------------


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value.strip())
    except ValueError:
        raise NotFound from None


def resolve_practice(request: Request, given: str | None = None) -> Practice:
    """The practice named by the request (query, body or header), of which the user is a member.

    Unknown practice and "not a member" answer the same 404. Omitted: the user's only practice.
    """
    value = given or request.query_params.get("practice") or request.headers.get(PRACTICE_HEADER)
    memberships = PracticeMember.objects.filter(user=cast(User, request.user)).select_related(
        "practice"
    )
    if value:
        member = memberships.filter(practice__public_id=_parse_uuid(str(value))).first()
        if member is None:
            raise NotFound
        return member.practice
    found = list(memberships[:2])
    if not found:
        raise NotFound
    if len(found) > 1:
        raise api_error(errors.WORKSPACE_PRACTICE_REQUIRED)
    return found[0].practice


def _require_directory(request: Request, practice: Practice) -> None:
    if not has_practice_perm(request.user, practice, DIRECTORY_VIEW.key):
        raise api_error(errors.PERMISSION_DENIED, action=_directory_action())


def _directory_action() -> str:
    label = str(DIRECTORY_VIEW.label)
    return label[:1].lower() + label[1:]


# ---- directory parameters ----------------------------------------------------------------------


def bad_parameter(code: errors.ErrorMessage, field: str, **params: Any) -> CatalogueError:
    """A 400 ``{"detail", "code", "field"}``: which parameter was refused, and why."""
    error = api_error(code, **params)
    error.extra = {"field": field}
    return error


def filter_choices(name: str) -> set[str] | None:
    """Allowed values of a filter (None: any text — package codes and tags are data)."""
    if name == "status":
        return set(DirectoryStatus.values)
    if name == "province":
        return set(Province.values)
    if name == "fye":
        return {str(month) for month in range(1, 13)}
    if name == "gst_cycle":
        return set(GstCycle.values)
    if name in BOOLEAN_FILTERS:
        return {YES, NO}
    return None


def _int(value: str | None, default: int, field: str, low: int, high: int) -> int:
    if value in (None, ""):
        return default
    try:
        number = int(str(value))
    except ValueError:
        raise bad_parameter(errors.WORKSPACE_BAD_PAGE, field, max=MAX_PAGE_SIZE) from None
    if not low <= number <= high:
        raise bad_parameter(errors.WORKSPACE_BAD_PAGE, field, max=MAX_PAGE_SIZE)
    return number


def _split(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def parse_directory_params(query: Any) -> tuple[DirectoryParams, list[str], bool]:
    """``DirectoryParams``, the requested columns and whether to include facets."""
    filters: dict[str, list[str]] = {}
    for name in FILTERS:
        values = [v.strip() for v in query.getlist(name) if v.strip()]
        allowed = filter_choices(name)
        for value in values:
            if (
                (allowed is not None and value not in allowed)
                or len(value) > 100
                or (name == "group" and not _is_uuid(value))
            ):
                raise bad_parameter(errors.WORKSPACE_BAD_FILTER, name, name=name, value=value[:100])
        if values:
            filters[name] = sorted(set(values), key=values.index)
    sort = _split(query.get("sort"))
    for key in sort:
        if key.lstrip("-") not in SORTS:
            raise bad_parameter(errors.WORKSPACE_BAD_SORT, "sort", value=key)
    columns = _split(query.get("columns")) or list(COLUMNS)
    for column in columns:
        if column not in COLUMNS:
            raise bad_parameter(errors.WORKSPACE_BAD_COLUMN, "columns", value=column)
    archived = query.get("archived", "")
    if archived not in ("", "include", "exclude"):
        raise bad_parameter(
            errors.WORKSPACE_BAD_FILTER, "archived", name="archived", value=archived[:100]
        )
    group_by = query.get("group_by", "")
    if group_by not in ("", "group"):
        raise bad_parameter(
            errors.WORKSPACE_BAD_FILTER, "group_by", name="group_by", value=group_by[:100]
        )
    params = DirectoryParams(
        q=(query.get("q") or "")[:200],
        filters=filters,
        include_archived=archived == "include",
        sort=sort,
        page=_int(query.get("page"), 1, "page", 1, 1_000_000),
        page_size=_int(query.get("page_size"), DEFAULT_PAGE_SIZE, "page_size", 1, MAX_PAGE_SIZE),
        group_by=group_by,
    )
    return params, columns, query.get("facets", "1") != "0"


# ---- presenting rows and facets ----------------------------------------------------------------


def _package_names() -> dict[str, str]:
    locale = translation.get_language() or "en-CA"
    return {package.code: package.name(locale) for package in Package.objects.all()}


def present_row(
    row: OrgDirectorySummary,
    columns: list[str],
    package_names: dict[str, str],
    groups: dict[int, list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"id": row.organisation.public_id, "name": row.name}
    now = timezone.now()
    for column in columns:
        for name in COLUMNS[column]:
            if name == "groups":  # the groups it's filed in directly (badges, V-02-T08)
                out[name] = (groups or {}).get(row.organisation_id, [])
            elif name == "package_name":
                out[name] = package_names.get(row.package, row.package)
            elif name == "trial_days_left":
                out[name] = (
                    max(0, math.ceil((row.trial_ends_at - now).total_seconds() / 86400))
                    if row.trial_ends_at and row.status == DirectoryStatus.TRIAL
                    else None
                )
            else:
                out[name] = getattr(row, name)
    return out


def _labels(
    name: str, package_names: dict[str, str], group_names: dict[str, str] | None = None
) -> dict[str, str]:
    if name == "group":
        return group_names or {}
    if name == "status":
        return {k: str(v) for k, v in DirectoryStatus.choices}
    if name == "province":
        return {k: str(v) for k, v in Province.choices}
    if name == "gst_cycle":
        return {k: str(v) for k, v in GstCycle.choices}
    if name == "fye":
        return {str(month): str(label) for month, label in dates.MONTHS.items()}
    if name in BOOLEAN_FILTERS:
        return {YES: str(translation.gettext("Yes")), NO: str(translation.gettext("No"))}
    if name == "package":
        return package_names
    return {}


def present_facets(
    facets: dict[str, list[dict[str, Any]]],
    package_names: dict[str, str],
    groups: list[GroupInfo] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    group_names = {group.id: group.name for group in groups or []}
    depth = {group.id: group.depth for group in groups or []}
    out: dict[str, list[dict[str, Any]]] = {}
    for name, items in facets.items():
        labels = _labels(name, package_names, group_names)
        out[name] = [
            {
                **item,
                "label": labels.get(item["value"], item["value"]),
                **({"depth": depth.get(item["value"], 1)} if name == "group" else {}),
            }
            for item in items
        ]
    return out


_LIST_PARAMETERS = [
    OpenApiParameter("practice", OpenApiTypes.UUID, description="Practice public id."),
    OpenApiParameter("q", OpenApiTypes.STR, description="Search text (name, BN, owner, tag…)."),
    *[
        OpenApiParameter(name, OpenApiTypes.STR, many=True, description=f"Filter: {name}.")
        for name in FILTERS
    ],
    OpenApiParameter("archived", OpenApiTypes.STR, enum=["include", "exclude"]),
    OpenApiParameter("sort", OpenApiTypes.STR, description="e.g. -overdue,name"),
    OpenApiParameter("page", OpenApiTypes.INT),
    OpenApiParameter("page_size", OpenApiTypes.INT, description=f"1–{MAX_PAGE_SIZE}"),
    OpenApiParameter("columns", OpenApiTypes.STR, description="e.g. name,bn,province"),
    OpenApiParameter("facets", OpenApiTypes.STR, enum=["0", "1"]),
    OpenApiParameter(
        "group_by",
        OpenApiTypes.STR,
        enum=["group"],
        description="group: add the group headers (counts and organisation ids per group).",
    ),
]


class DirectoryView(APIView):
    required_feature = CORE  # the Practice product is free: never gated

    # Membership and practice.directory.view are checked in the view: the practice comes from the
    # query, not from an organisation URL (rbac's practice scope needs an active organisation).
    @requires_permission(AUTHENTICATED)
    @extend_schema(
        operation_id="practice_orgs_list",
        summary="Organisation directory of a practice (search, filters, facets)",
        parameters=_LIST_PARAMETERS,
        responses=DirectoryPageSerializer,
    )
    def get(self, request: Request) -> Response:
        practice = resolve_practice(request)
        _require_directory(request, practice)
        params, columns, with_facets = parse_directory_params(request.query_params)
        query = DirectoryQuery(request.user, practice, params)
        rows, count = query.page()
        package_names = _package_names()
        groups = practice_groups(practice)
        badges: dict[int, list[dict[str, str]]] = {}
        if "groups" in columns:
            names = {group.id: group.name for group in groups}
            _within, direct = query.groups_of()
            badges = {
                pk: [{"id": gid, "name": names[gid]} for gid in ids] for pk, ids in direct.items()
            }
        body: dict[str, Any] = {
            "practice": {"id": practice.public_id, "name": practice.name},
            "count": count,
            "total": query.total(),
            "page": params.page,
            "page_size": params.page_size,
            "pages": max(1, math.ceil(count / params.page_size)),
            "columns": columns,
            "results": [present_row(row, columns, package_names, badges) for row in rows],
        }
        if with_facets:
            body["facets"] = present_facets(query.facets(), package_names, groups)
        if params.group_by == "group":
            public = dict(
                OrgDirectorySummary.objects.filter(practice=practice).values_list(
                    "organisation_id", "organisation__public_id"
                )
            )
            body["grouping"] = [
                {
                    "group": None
                    if item["group"] is None
                    else {
                        "id": item["group"].id,
                        "name": item["group"].name,
                        "depth": item["group"].depth,
                        "parent": item["group"].parent,
                    },
                    "count": item["count"],
                    "organisations": [public[pk] for pk in item["organisation_ids"]],
                }
                for item in query.grouping()
            ]
        return Response(body)
