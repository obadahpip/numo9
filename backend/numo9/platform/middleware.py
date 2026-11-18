"""Impersonation (U-06-T09): the request acts as the impersonated user, inside the time box.

``ImpersonationMiddleware`` (after ``AuthenticationMiddleware`` and the 2FA policy, which apply to
the staff member, before the audit and tenant context): when the browser session holds an
impersonation session id and the signed-in user is its actor, still with ``platform.impersonate``,

- an **open** session swaps ``request.user`` for the user acted as and sets
  ``request.audit_impersonator`` (the audit context names both, A-04/U-06-T10) and
  ``request.impersonation``;
- an **expired** session is ended there and then (``expired``) and forgotten; the request is
  refused with ``403 impersonation.expired`` (nothing it asked for happens — the page learns the
  session is over) unless it is the console's own impersonation endpoint;
- a staff member who lost ``platform.impersonate`` has the session ended (``revoked``).

While impersonating, **blocked endpoints** answer ``403 impersonation.blocked`` (``BLOCKED``):
billing portal, checkout, package change and cancellation (payment methods stay with the user),
passwords, two-factor authentication and email addresses, revealing masked SIN/bank details,
practice workspaces and creating organisations/practices, the Django admin and the console itself
(except the impersonation ``current`` and ``end`` endpoints). Every other request is **scoped to
the session's organisation**: naming another organisation answers 404, as for any organisation the
user can't see.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from rest_framework.exceptions import NotFound

from numo9.i18n import errors
from numo9.rbac.resolver import platform_permissions

from .models import ImpersonationEndReason

SESSION_KEY = "numo9_impersonation"
IMPERSONATE = "platform.impersonate"

#: Endpoints refused while impersonating (``path_info`` regexes).
BLOCKED: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^/api/v\d+/o/[^/]+/billing/(portal|checkout|change|cancel)(/|$)",
        r"^/api/v\d+/o/[^/]+/reveal(/|$)",
        r"^/_allauth/[^/]+/v\d+/account/(password|email|authenticators|phone|providers)(/|$)",
        r"^/_allauth/[^/]+/v\d+/auth/(password|2fa|webauthn|reauthenticate|signup)(/|$)",
        r"^/_allauth/[^/]+/v\d+/auth/sessions(/|$)",
        r"^/api/v\d+/practice(/|$)",
        r"^/api/v\d+/(practices|organisations)/?$",
        r"^/api/v\d+/platform/(?!impersonation/(current|end)$)",
        r"^/admin(/|$)",
    )
)
#: Still answered when a session has just expired (the console learns it is over).
CONSOLE_IMPERSONATION = re.compile(r"^/api/v\d+/platform/impersonation(/|$)")


def is_blocked(path: str) -> bool:
    return any(pattern.match(path) for pattern in BLOCKED)


def _refuse(error: errors.ErrorMessage) -> JsonResponse:
    return JsonResponse({"detail": error.text(), "code": error.code}, status=error.status)


def _not_found() -> JsonResponse:
    return JsonResponse(
        {"detail": str(NotFound.default_detail), "code": NotFound.default_code}, status=404
    )


class ImpersonationMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        session_store: Any = getattr(request, "session", None)
        if session_store is None or SESSION_KEY not in session_store:
            return self.get_response(request)
        from numo9.tenancy.middleware import org_id_from_request

        from .models import ImpersonationSession

        actor = request.user
        session = (
            ImpersonationSession.objects.select_related("target_user", "organisation")
            .filter(public_id=session_store[SESSION_KEY], ended_at__isnull=True)
            .first()
            if actor.is_authenticated
            else None
        )
        if session is None or session.actor_id != actor.pk:
            session_store.pop(SESSION_KEY, None)
            return self.get_response(request)
        if IMPERSONATE not in platform_permissions(actor):
            session.end(ImpersonationEndReason.REVOKED)
            session_store.pop(SESSION_KEY, None)
            return self.get_response(request)
        if not session.is_open():
            session.end(ImpersonationEndReason.EXPIRED)
            session_store.pop(SESSION_KEY, None)
            request.impersonation_ended = session  # type: ignore[attr-defined]
            if CONSOLE_IMPERSONATION.match(request.path_info):
                return self.get_response(request)
            return _refuse(errors.IMPERSONATION_EXPIRED)
        if is_blocked(request.path_info):
            return _refuse(errors.IMPERSONATION_BLOCKED)
        try:
            org_id = org_id_from_request(request)
        except (Http404, ValueError):
            org_id = None  # the tenant middleware answers it
        if org_id is not None and org_id != session.organisation.public_id:
            return _not_found()
        request.user = session.target_user
        request.audit_impersonator = actor  # type: ignore[attr-defined]
        request.impersonation = session  # type: ignore[attr-defined]
        return self.get_response(request)
