"""Middleware resolving the active organisation and acting practice per request (A-01-T03).

Active organisation, by its public id (UUID):

- from the URL: ``/o/<org>/…`` or ``/api/v<n>/o/<org>/…``;
- or from the ``X-Numo9-Org`` header (API calls whose URL carries no organisation).

If both are present they must name the same organisation (``400`` otherwise). An organisation
id that is malformed or unknown answers ``404`` — the same answer as an organisation the user
may not see (A-01-T06), so the response never reveals whether an organisation exists.

Acting practice (only when an organisation is active):

- from the ``X-Numo9-Practice`` header (practice public id), which must name a practice actively
  assigned to the organisation (``404`` otherwise) — used when the user works for several
  practices assigned to the same organisation;
- otherwise derived: the single practice that the signed-in user belongs to and that is actively
  assigned to the organisation; none when there is no such practice or more than one.

API requests (``/api/…``) get the same JSON ``404`` body as DRF's ``NotFound``, so an unknown
organisation and one the user may not access (A-01-T06) are indistinguishable.

The context is set for the whole request and always cleared afterwards, even on errors.
Install after ``AuthenticationMiddleware``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from rest_framework.exceptions import NotFound

from .context import org_context
from .models import Organisation, Practice

ORG_HEADER = "X-Numo9-Org"
PRACTICE_HEADER = "X-Numo9-Practice"
ORG_PATH_RE = re.compile(r"^/(?:api/v\d+/)?o/(?P<org>[^/]+)(?:/|$)")


def _parse_public_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value.strip())
    except ValueError:
        raise Http404 from None


def org_id_from_request(request: HttpRequest) -> uuid.UUID | None:
    """Public id of the requested organisation, or ``None`` when the request names none.

    Raises ``Http404`` for a malformed id and ``ValueError`` when URL and header disagree.
    """
    match = ORG_PATH_RE.match(request.path_info)
    from_path = _parse_public_id(match["org"]) if match else None
    header = request.headers.get(ORG_HEADER)
    from_header = _parse_public_id(header) if header else None
    if from_path and from_header and from_path != from_header:
        raise ValueError("organisation in URL and header differ")
    return from_path or from_header


def resolve_acting_practice(request: HttpRequest, organisation: Organisation) -> Practice | None:
    assigned = Practice.objects.filter(
        assignments__organisation=organisation, assignments__active=True
    )
    header = request.headers.get(PRACTICE_HEADER)
    if header:
        practice = assigned.filter(public_id=_parse_public_id(header)).first()
        if practice is None:
            raise Http404
        return practice
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    candidates = list(assigned.filter(members__user=user).distinct()[:2])
    return candidates[0] if len(candidates) == 1 else None


def _is_api(request: HttpRequest) -> bool:
    return request.path_info.startswith("/api/")


class TenantContextMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self._call(request)
        except Http404:
            if not _is_api(request):
                raise
            return JsonResponse({"detail": str(NotFound.default_detail)}, status=404)

    def _call(self, request: HttpRequest) -> HttpResponse:
        try:
            org_id = org_id_from_request(request)
        except ValueError:
            return JsonResponse(
                {"detail": f"The organisation in the URL and the {ORG_HEADER} header differ."},
                status=400,
            )
        organisation = practice = None
        if org_id is not None:
            organisation = Organisation.objects.filter(public_id=org_id).first()
            if organisation is None:
                raise Http404
            practice = resolve_acting_practice(request, organisation)
        request.organisation = organisation  # type: ignore[attr-defined]
        request.acting_practice = practice  # type: ignore[attr-defined]
        with org_context(organisation, practice):
            return self.get_response(request)
