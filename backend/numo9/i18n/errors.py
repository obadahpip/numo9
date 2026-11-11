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
    #: Extra fields for the response body next to ``detail`` and ``code`` (exception handler).
    extra: dict[str, Any] | None = None

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


# ---- roles and permissions (A-03) ----------------------------------------------------------
PERMISSION_DENIED = define(
    "permission.denied",
    _(
        "You don't have permission to %(action)s. Ask someone who manages roles here to give you "
        "a role that allows it."
    ),
    status.HTTP_403_FORBIDDEN,
)

# ---- approval limits (A-03-T07) --------------------------------------------------------------
APPROVAL_LIMIT_EXCEEDED = define(
    "approval.limit_exceeded",
    _("This %(document)s is for %(amount)s, above your approval limit of %(limit)s. %(next_step)s"),
    status.HTTP_403_FORBIDDEN,
)
APPROVAL_NO_LIMIT = define(
    "approval.no_limit",
    _(
        "You don't have an approval limit for %(documents)s in this organisation, so you can't "
        "approve this one (%(amount)s). %(next_step)s"
    ),
    status.HTTP_403_FORBIDDEN,
)
#: The sentences that end the two messages above (``next_step``).
APPROVAL_ASK = _("Ask %(names)s to approve it.")
APPROVAL_NOBODY = _(
    "Nobody here can approve that amount yet: ask someone who manages roles to raise an "
    "approval limit."
)


# ---- segregation of duties (A-03-T08) ------------------------------------------------------
SELF_APPROVAL = define(
    "approval.self_approval",
    _("You created this %(record)s, so someone else has to approve it."),
    status.HTTP_403_FORBIDDEN,
)


# ---- roles, assignments and limits API (A-03-T09) ------------------------------------------
ROLE_SYSTEM = define(
    "roles.system_role",
    _(
        "%(role)s is a system role, so it can't be changed or deleted. Copy it into a custom "
        "role and change that instead."
    ),
    status.HTTP_409_CONFLICT,
)
ROLE_IN_USE = define(
    "roles.in_use",
    _(
        "%(role)s is still given to people here (%(count)s). Take it away from them first, then "
        "delete it."
    ),
    status.HTTP_409_CONFLICT,
)
ROLE_NAME_TAKEN = define(
    "roles.name_taken",
    _("There's already a role called %(name)s here. Choose another name."),
    status.HTTP_409_CONFLICT,
)
GRANT_EXCEEDS_OWN = define(
    "roles.grant_exceeds_own",
    _(
        "You can only give permissions you have yourself. You don't have: %(permissions)s. Ask "
        "an owner to do this."
    ),
    status.HTTP_403_FORBIDDEN,
)
UNKNOWN_PERMISSION = define(
    "roles.unknown_permission", _("There's no permission called %(key)s. Verify the key.")
)
PERMISSION_NOT_GRANTABLE = define(
    "roles.permission_scope",
    _("%(key)s is a %(scope)s permission, so an organisation role can't give it."),
)
ROLE_NOT_FOUND = define(
    "roles.not_found",
    _("This role doesn't exist in this organisation. Choose one from its list of roles."),
    status.HTTP_404_NOT_FOUND,
)
PERSON_NOT_FOUND = define(
    "roles.person_not_found",
    _("This person doesn't work in this organisation. Choose someone from its list of users."),
    status.HTTP_404_NOT_FOUND,
)
UNKNOWN_ROLE = define(
    "roles.unknown_role",
    _("This role doesn't exist here. Choose one of this organisation's roles."),
)
ROLE_NOT_ASSIGNABLE = define(
    "roles.not_assignable",
    _(
        "%(role)s is a practice role: practices give it to their own staff. Choose an "
        "organisation role."
    ),
)
NOT_A_MEMBER = define(
    "roles.not_a_member",
    _(
        "%(name)s works here through their practice, so they have no main role in this "
        "organisation. Give them a custom role instead."
    ),
)
LAST_OWNER = define(
    "roles.last_owner",
    _("%(name)s is the only owner. Make someone else an owner first."),
    status.HTTP_409_CONFLICT,
)
MAIN_ROLE = define(
    "roles.main_role",
    _(
        "Every member has one main role, so it can't be removed. Choose another main role for "
        "them instead."
    ),
    status.HTTP_409_CONFLICT,
)
UNKNOWN_PERSON = define(
    "roles.unknown_person",
    _("This person doesn't work in this organisation. Choose someone from its users."),
)
LIMIT_DUPLICATE = define(
    "limits.duplicate",
    _("%(who)s already has an approval limit for this document type. Change that one instead."),
    status.HTTP_409_CONFLICT,
)
LIMIT_TARGET = define(
    "limits.target", _("Choose either a person or a role for this limit, not both.")
)


# ---- "why can't I?" and access requests (A-03-T14) -----------------------------------------
ACCESS_ALREADY_HAVE = define(
    "access.already_have",
    _("You already have this permission here. Reload the page and try again."),
    status.HTTP_409_CONFLICT,
)
ACCESS_NOBODY = define(
    "access.nobody",
    _(
        "Nobody here can give this permission yet. Ask the organisation's owner to give you a "
        "role that allows it."
    ),
    status.HTTP_409_CONFLICT,
)
ACCESS_PERMISSION = define(
    "access.permission",
    _(
        "You can only ask for one of this organisation's permissions, e.g. "
        "organisation.settings.manage."
    ),
)
