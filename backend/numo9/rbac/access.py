"""Request access (A-03-T14): someone refused a permission asks the people who could give it.

``request_access(user, organisation, key, note)``:

- the key must be an organisation permission of the catalogue (``400 access.permission``) that
  the user doesn't already have (``409 access.already_have``);
- recipients are ``explain.managers_for``: they may give roles and hold the permission (nobody
  can give what they don't have); none → ``409 access.nobody`` (ask the owner);
- one open request per person and permission: asking again returns the open one without
  emailing again;
- each recipient gets an email in their language naming who asks, for what, the note, and a
  link to Users and roles. The notification centre (A-07) will deliver in-app too; until then
  open requests are listed on Users and roles (``GET …/access-requests``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import translation
from django.utils.translation import gettext as _
from rest_framework import serializers

from numo9.i18n import errors
from numo9.i18n.errors import api_error, error_detail
from numo9.tenancy.models import Organisation

from . import audit
from .catalogue import Scope, UnknownPermission, catalogue
from .explain import managers_for
from .models import AccessRequest
from .resolver import has_perm


@dataclass(frozen=True)
class Requested:
    request: AccessRequest
    created: bool
    recipients: list[Any]


def users_roles_link(organisation: Organisation) -> str:
    return f"{settings.FRONTEND_URL}/o/{organisation.public_id}/settings/users-roles"


def _valid_key(key: str) -> str:
    try:
        permission = catalogue.get(key)
    except UnknownPermission:
        permission = None
    if permission is None or permission.scope != Scope.ORGANISATION:
        raise serializers.ValidationError({"permission": [error_detail(errors.ACCESS_PERMISSION)]})
    return key


def _email(recipient: Any, requester: Any, organisation: Organisation, key: str, note: str) -> None:
    with translation.override(recipient.locale or organisation.locale):
        label = str(catalogue.get(key).label)
        subject = _("%(name)s asks for access in %(organisation)s") % {
            "name": requester.name or requester.email,
            "organisation": organisation.name,
        }
        body = _(
            "%(name)s (%(email)s) can't do this in %(organisation)s and asks you for a role "
            "that allows it:\n\n%(permission)s\n\n%(note)s"
            "Give them a role on Users and roles:\n%(link)s\n\n"
            "You get this email because you can give roles in %(organisation)s."
        ) % {
            "name": requester.name or requester.email,
            "email": requester.email,
            "organisation": organisation.name,
            "permission": label,
            "note": (_("Their note: %(note)s") % {"note": note} + "\n\n") if note else "",
            "link": users_roles_link(organisation),
        }
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient.email])


def request_access(user: Any, organisation: Organisation, key: str, note: str = "") -> Requested:
    key = _valid_key(key)
    if has_perm(user, organisation, key):
        raise api_error(errors.ACCESS_ALREADY_HAVE)
    open_request = AccessRequest.objects.filter(
        requester=user, permission=key, deleted_at__isnull=True
    ).first()
    if open_request is not None:
        return Requested(open_request, False, [])
    recipients = managers_for(organisation, key, exclude=user)
    if not recipients:
        raise api_error(errors.ACCESS_NOBODY)
    try:
        with transaction.atomic():
            row = AccessRequest.objects.create(
                organisation=organisation,
                requester=user,
                permission=key,
                note=note.strip(),
                notified=len(recipients),
                created_by=user,
            )
            audit.record(
                "access_request.created",
                actor=user,
                organisation=organisation,
                obj=row,
                label=f"{user.name} → {key}",
                after={"permission": key, "note": row.note, "notified": len(recipients)},
            )
    except IntegrityError:  # a parallel request won the race
        row = AccessRequest.objects.get(requester=user, permission=key, deleted_at__isnull=True)
        return Requested(row, False, [])
    for recipient in recipients:
        _email(recipient, user, organisation, key, row.note)
    return Requested(row, True, recipients)
