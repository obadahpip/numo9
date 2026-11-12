"""Sign-in, two-step verification and invitation events in the audit log (A-02-T14).

Sign-in and 2FA events belong to a person, not to an organisation: they are **platform events**
(no organisation), read by platform staff through the platform audit log (A-04-T07). Invitation
events belong to what the invitation is for: the organisation's log, or the practice's.

- ``auth.login.succeeded`` — a person finished signing in (after 2FA when they use it);
- ``auth.login.failed`` — wrong email or password (``meta.email``: the address typed);
- ``auth.login.locked`` — refused: the address is locked after repeated failures (S-03-T07);
- ``auth.logout`` — signed out;
- ``auth.2fa.failed`` — a wrong 2FA or recovery code;
- ``auth.2fa.enabled`` / ``auth.2fa.disabled`` — authenticator app added / removed;
- ``auth.recovery_codes.created`` / ``…regenerated`` / ``…removed`` — recovery codes;
- ``tenancy.invitation.created`` / ``resent`` / ``revoked`` / ``accepted`` — the invitation
  flows (A-02-T09), recorded on the invitation.

The record of a sign-in or 2FA event is the user (an unknown address: no record id, the address
typed as its label).

Failed sign-ins are recorded for unknown addresses too (the address typed is the record's label),
so staff can see an attack on addresses that have no account. Passwords and codes are never
recorded.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed

from numo9.accounts.models import normalise_email

from .context import client_ip, user_agent_of
from .service import record

USER_TYPE = "accounts.User"


def _user_by_email(email: str) -> Any:
    if not email:
        return None
    return get_user_model()._default_manager.filter(email=normalise_email(email)).first()


def _for_user(action: str, user: Any, request: Any, meta: dict[str, Any] | None = None) -> None:
    """A platform event about ``user`` made by ``user`` (or nobody, for an unknown address)."""
    meta = meta or {}
    if user is not None:
        record(
            action,
            organisation=None,
            obj=user,
            object_label=user.email,
            actor=user,
            meta=meta,
            ip=client_ip(request),
            user_agent=user_agent_of(request),
        )
    else:
        email = str(meta.get("email", ""))
        record(
            action,
            organisation=None,
            object_type=USER_TYPE,
            object_label=email,
            actor_label=email or "Unknown",
            meta=meta,
            ip=client_ip(request),
            user_agent=user_agent_of(request),
        )


def _email_from(credentials: dict[str, Any]) -> str:
    return str(credentials.get("email") or credentials.get("username") or "").strip()


def on_logged_in(sender: Any, request: Any, user: Any, **kwargs: Any) -> None:
    _for_user("auth.login.succeeded", user, request)


def on_logged_out(sender: Any, request: Any, user: Any, **kwargs: Any) -> None:
    if user is not None and getattr(user, "is_authenticated", False):
        _for_user("auth.logout", user, request)


def on_login_failed(
    sender: Any, credentials: dict[str, Any], request: Any = None, **kw: Any
) -> None:
    email = normalise_email(_email_from(credentials))
    user = _user_by_email(email)
    _for_user(
        "auth.login.failed",
        user,
        request,
        meta={"email": email, "reason": "invalid_credentials"},
    )


def login_locked(request: Any, email: str) -> None:
    """Called by the account adapter when a locked address tries to sign in (S-03-T07)."""
    email = normalise_email(email)
    _for_user(
        "auth.login.locked",
        _user_by_email(email),
        request,
        meta={"email": email, "reason": "locked"},
    )


# ---- two-step verification (allauth.mfa signals) -----------------------------------------------

_ADDED = {"totp": "auth.2fa.enabled", "recovery_codes": "auth.recovery_codes.created"}
_REMOVED = {"totp": "auth.2fa.disabled", "recovery_codes": "auth.recovery_codes.removed"}


def _kind(authenticator: Any) -> str:
    return str(getattr(authenticator, "type", "") or "")


def on_authenticator_added(
    sender: Any, request: Any, user: Any, authenticator: Any, **kw: Any
) -> None:
    kind = _kind(authenticator)
    _for_user(_ADDED.get(kind, "auth.2fa.added"), user, request, meta={"type": kind})


def on_authenticator_removed(
    sender: Any, request: Any, user: Any, authenticator: Any, **kw: Any
) -> None:
    kind = _kind(authenticator)
    _for_user(_REMOVED.get(kind, "auth.2fa.removed"), user, request, meta={"type": kind})


def on_authenticator_reset(
    sender: Any, request: Any, user: Any, authenticator: Any, **kw: Any
) -> None:
    kind = _kind(authenticator)
    action = "auth.recovery_codes.regenerated" if kind == "recovery_codes" else "auth.2fa.reset"
    _for_user(action, user, request, meta={"type": kind})


def on_mfa_failed(
    sender: Any, request: Any, user: Any, authenticator: Any = None, **kw: Any
) -> None:
    _for_user("auth.2fa.failed", user, request, meta={"type": _kind(authenticator)})


def connect() -> None:
    from allauth.mfa import signals as mfa

    user_logged_in.connect(on_logged_in, dispatch_uid="numo9.audit.login")
    user_logged_out.connect(on_logged_out, dispatch_uid="numo9.audit.logout")
    user_login_failed.connect(on_login_failed, dispatch_uid="numo9.audit.login_failed")
    mfa.authenticator_added.connect(on_authenticator_added, dispatch_uid="numo9.audit.mfa_add")
    mfa.authenticator_removed.connect(on_authenticator_removed, dispatch_uid="numo9.audit.mfa_rm")
    mfa.authenticator_reset.connect(on_authenticator_reset, dispatch_uid="numo9.audit.mfa_reset")
    mfa.authentication_failed.connect(on_mfa_failed, dispatch_uid="numo9.audit.mfa_failed")


# ---- invitations (called by numo9.tenancy.invitations) ------------------------------------------


def invitation_event(
    action: str, invitation: Any, *, by: Any, changes: dict[str, list[Any]], **meta: Any
) -> None:
    target = invitation.organisation if invitation.organisation_id else None
    record(
        f"tenancy.invitation.{action}",
        obj=invitation,
        organisation=target,
        practice=invitation.practice if invitation.practice_id else None,
        object_label=f"{invitation.email} — {invitation.target.name}",
        changes=changes,
        meta={"kind": invitation.kind, "role": invitation.role, "email": invitation.email, **meta},
        actor=by,
    )
