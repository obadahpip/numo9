"""django-allauth adapter (A-02): Numo9's account rules on top of allauth's defaults."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.http import HttpRequest
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from numo9.security import bruteforce


@dataclass(frozen=True)
class Brand:
    """What emails call the site: the product, at the web app's address (not the API host)."""

    name: str
    domain: str


def brand() -> Brand:
    return Brand(name="Numo9", domain=urlsplit(settings.FRONTEND_URL).netloc or "numo9.ca")


def login_email(credentials: dict[str, Any]) -> str:
    return str(credentials.get("email") or credentials.get("username") or "")


def _captcha_token(request: HttpRequest) -> str | None:
    """The ``captcha`` value of the JSON login body, if any."""
    try:
        body = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    token = body.get("captcha") if isinstance(body, dict) else None
    return str(token) if token else None


class AccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]  # allauth is untyped
    error_messages = {
        **DefaultAccountAdapter.error_messages,
        "too_many_login_attempts": _(
            "This account is locked for 15 minutes after 10 failed sign-in attempts. Try again "
            "later, or reset your password to unlock it now."
        ),
        "captcha_required": _(
            "Several sign-in attempts failed for this account. Complete the security check, "
            "then sign in again."
        ),
    }

    def send_mail(self, template_prefix: str, email: str, context: dict[str, Any]) -> None:
        """allauth's emails (verification, password reset, password changed…) in the language
        of the account they are about (A-02-T15): the user's locale when the address belongs to
        a user, otherwise the request's language."""
        from .models import User, normalise_email

        owner_pk = getattr(context.get("user"), "pk", None)
        users = (
            User.objects.filter(pk=owner_pk)
            if owner_pk  # else: no user in the context — the account of the address, if any
            else User.objects.filter(email=normalise_email(email))
        )
        # Read from the database: the context's user object may predate the sign-up's language.
        language = users.values_list("locale", flat=True).first() or translation.get_language()
        with translation.override(language):
            super().send_mail(template_prefix, email, {"current_site": brand(), **context})

    # ---- brute-force protection (S-03-T07) -------------------------------------------------

    def pre_authenticate(self, request: HttpRequest, **credentials: Any) -> None:
        email = login_email(credentials)
        if bruteforce.locked_for(email):
            from numo9.audit.auth_events import login_locked  # A-02-T14

            login_locked(request, email)
            raise self.validation_error("too_many_login_attempts")
        if bruteforce.captcha_required(email) and not bruteforce.captcha_ok(
            _captcha_token(request), request.META.get("REMOTE_ADDR")
        ):
            raise self.validation_error("captcha_required")
        super().pre_authenticate(request, **credentials)  # allauth's per-IP limits

    def authenticate(self, request: HttpRequest, **credentials: Any) -> Any:
        user = super().authenticate(request, **credentials)
        if user is not None:
            bruteforce.record_success(login_email(credentials))
        return user

    def authentication_failed(self, request: HttpRequest, **credentials: Any) -> None:
        super().authentication_failed(request, **credentials)
        bruteforce.record_failure(login_email(credentials))

    def _delete_login_attempts_cached_email(self, request: HttpRequest, **credentials: Any) -> None:
        # Called by allauth after a completed password reset: the mailbox owner proved who
        # they are, so failures and any lock are forgotten.
        super()._delete_login_attempts_cached_email(request, **credentials)
        bruteforce.clear(login_email(credentials))
