"""Two-factor authentication policy (A-02-T06).

Who **must** use two-factor authentication:

- every **platform owner** (system role ``platform_owner``) — always;
- every **practice admin** of a practice that turned on "Practice admins must use two-factor
  authentication" (``Practice.require_2fa_for_admins``).

``two_factor_required(user)`` names why (``platform_owner`` / ``practice_admin``) or answers
``None``. ``TwoFactorEnforcementMiddleware`` enforces it: a signed-in user who must use 2FA and
has no TOTP authenticator yet can only reach what enrolling needs — the session, sign-out,
password confirmation, the authenticator endpoints, the CSRF token and their own profile; every
other API call answers ``403 auth.two_factor_required`` (the web app sends them to Security
settings). Enrolling lifts it at once; nothing to skip.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import translation

from numo9.i18n import errors

PLATFORM_OWNER = "platform_owner"
PRACTICE_ADMIN = "practice_admin"

#: What a user who still has to enrol may reach.
ALLOWED = re.compile(
    r"^/(_allauth/browser/v1/(auth/session|auth/reauthenticate|auth/sessions|config|"
    r"account/authenticators(/.*)?|auth/2fa/.*)"
    r"|api/v1/auth/csrf|api/v1/me/.*|healthz)$"
)


def two_factor_required(user: Any) -> str | None:
    from numo9.rbac.models import RoleAssignment, RoleScope
    from numo9.tenancy.models import PracticeMember

    if not getattr(user, "is_authenticated", False):
        return None
    if RoleAssignment.objects.filter(
        user=user, role__scope=RoleScope.PLATFORM, role__is_system=True, role__key=PLATFORM_OWNER
    ).exists():
        return PLATFORM_OWNER
    if PracticeMember.objects.filter(
        user=user, role=PRACTICE_ADMIN, practice__require_2fa_for_admins=True
    ).exists():
        return PRACTICE_ADMIN
    return None


def has_two_factor(user: Any) -> bool:
    from allauth.mfa.models import Authenticator

    return bool(Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists())


class TwoFactorEnforcementMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not ALLOWED.match(request.path)
            and (request.path.startswith("/api/") or request.path.startswith("/_allauth/"))
        ):
            reason = two_factor_required(user)
            if reason is not None and not has_two_factor(user):
                error = errors.AUTH_TWO_FACTOR_REQUIRED
                with translation.override(getattr(user, "locale", None) or None):
                    return JsonResponse(
                        {"detail": error.text(), "code": error.code, "reason": reason},
                        status=error.status,
                    )
        return self.get_response(request)
