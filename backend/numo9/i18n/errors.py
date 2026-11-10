"""Error-message catalogue (A-10-T14): every API error is a stable key plus a gettext message.

Clients and tests rely on the key (``code``); people read the message, translated into the
request's language. Messages follow the microcopy rules (Phase 0 plan §3.5): say what happened
and what to do, name the record, no blame, Canadian English, sentence case, never "Oops".

Add an error here — not as an inline string — and run ``make i18n``; the French text goes in
``backend/locale/fr_CA/LC_MESSAGES/django.po``.

    raise serializers.ValidationError({"practice": [error_detail(UNKNOWN_PRACTICE)]})
    raise api_error(ORG_HEADER_MISMATCH)                # 400 with {"detail", "code"}
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException, ErrorDetail

CODE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


@dataclass(frozen=True)
class ErrorMessage:
    code: str
    message: Promise
    status: int = status.HTTP_400_BAD_REQUEST

    def text(self, **params: Any) -> str:
        """The message in the active language, with ``%(name)s`` parameters filled in."""
        message = str(self.message)
        return message % params if params else message


CATALOGUE: dict[str, ErrorMessage] = {}


def define(
    code: str, message: Promise, status_code: int = status.HTTP_400_BAD_REQUEST
) -> ErrorMessage:
    if not CODE.match(code):
        raise ValueError(f"Error code {code!r} must be a dotted lower-case key like 'area.reason'.")
    if code in CATALOGUE:
        raise ValueError(f"Error code {code!r} is defined twice.")
    error = ErrorMessage(code, message, status_code)
    CATALOGUE[code] = error
    return error


def error_detail(error: ErrorMessage, **params: Any) -> ErrorDetail:
    """A DRF ErrorDetail carrying the translated message and the key (for field errors)."""
    return ErrorDetail(error.text(**params), code=error.code)


class CatalogueError(APIException):
    def __init__(self, error: ErrorMessage, **params: Any) -> None:
        self.status_code = error.status
        super().__init__(detail=error.text(**params), code=error.code)


def api_error(error: ErrorMessage, **params: Any) -> CatalogueError:
    return CatalogueError(error, **params)


# ---- tenancy (A-01) ------------------------------------------------------------------------
UNKNOWN_PRACTICE = define(
    "tenancy.unknown_practice",
    _("This practice doesn't exist or you're not a member. Choose one of your practices."),
)
ORG_HEADER_MISMATCH = define(
    "tenancy.org_header_mismatch",
    _(
        "The organisation in the address and the one in the X-Numo9-Org header differ. "
        "Send one organisation, or the same one in both."
    ),
)


# ---- invitations (A-02-T09) ----------------------------------------------------------------
INVITATION_NOT_ALLOWED = define(
    "invitation.not_allowed",
    _(
        "You can't send this invitation: only the practice's admins invite its staff, and only "
        "an organisation's owner or admins invite its users and accountant."
    ),
    status.HTTP_403_FORBIDDEN,
)
INVITATION_ALREADY_MEMBER = define(
    "invitation.already_member",
    _("%(email)s is already a member. Change their role instead of inviting them again."),
    status.HTTP_409_CONFLICT,
)
INVITATION_ALREADY_PENDING = define(
    "invitation.already_pending",
    _("%(email)s already has an invitation waiting. Resend it, or revoke it first."),
    status.HTTP_409_CONFLICT,
)
INVITATION_HAS_OWNER = define(
    "invitation.has_owner",
    _("This organisation already has an owner. Ask the owner to invite you, or to add users."),
    status.HTTP_409_CONFLICT,
)
INVITATION_INVALID = define(
    "invitation.invalid",
    _("This invitation link isn't valid. Make sure you copied the whole link from the email."),
    status.HTTP_404_NOT_FOUND,
)
INVITATION_USED = define(
    "invitation.used",
    _("This invitation has already been accepted. Sign in to open it."),
    status.HTTP_410_GONE,
)
INVITATION_REVOKED = define(
    "invitation.revoked",
    _("This invitation was withdrawn by the person who sent it. Ask them for a new one."),
    status.HTTP_410_GONE,
)
INVITATION_EXPIRED = define(
    "invitation.expired",
    _("This invitation expired on %(date)s. Ask the person who sent it to resend it."),
    status.HTTP_410_GONE,
)
INVITATION_WRONG_ACCOUNT = define(
    "invitation.wrong_account",
    _(
        "This invitation is for %(email)s, but you're signed in as another account. Sign out, "
        "then sign in or sign up with %(email)s."
    ),
    status.HTTP_403_FORBIDDEN,
)
INVITATION_CHOOSE_PRACTICE = define(
    "invitation.choose_practice",
    _("You belong to more than one practice. Choose the practice that will serve this client."),
)
INVITATION_NOT_PENDING = define(
    "invitation.not_pending",
    _("This invitation is no longer waiting (accepted, revoked or expired). Send a new one."),
    status.HTTP_409_CONFLICT,
)
INVITATION_RESEND_TOO_SOON = define(
    "invitation.resend_too_soon",
    _("This invitation was just sent. Wait a minute before sending it again."),
    status.HTTP_429_TOO_MANY_REQUESTS,
)
INVITATION_ROLE_INVALID = define(
    "invitation.role_invalid",
    _(
        "This role doesn't fit the invitation: staff get a practice role, users an organisation "
        "role, and an accountant what their practice will do (e.g. bookkeeping, tax)."
    ),
)
