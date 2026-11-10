"""Numo9's adjustments to django-allauth's headless views (A-02).

Mounted in ``numo9/accounts/urls.py`` at the same paths as allauth's own views, ahead of
``allauth.headless.urls``, so the browser client keeps allauth's API contract:

- sign-up runs in one transaction — the user, their email address, the practice or
  organisation and the membership are created together or not at all (A-02-T02);
- TOTP enrolment (A-02-T05): the set-up answer carries the QR code as an inline SVG, and the
  activation answer carries the 10 recovery codes — the only time they are shown;
- login answers with the status the error means (A-02-T03): ``401`` for a wrong email or
  password (allauth says ``400``), ``429`` with ``Retry-After`` when the account is locked or the
  IP is rate limited; malformed input stays ``400``.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from allauth.headless.account import views as headless
from allauth.headless.internal.restkit.response import ErrorResponse
from allauth.headless.mfa import response as mfa_response
from allauth.headless.mfa import views as headless_mfa
from allauth.mfa.adapter import get_adapter as get_mfa_adapter
from allauth.mfa.totp.internal import flows as totp_flows
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse

from numo9.security import bruteforce

# allauth error codes on the login form and the HTTP status Numo9 answers with.
LOGIN_ERROR_STATUS = {
    "too_many_login_attempts": HTTPStatus.TOO_MANY_REQUESTS,
    "email_password_mismatch": HTTPStatus.UNAUTHORIZED,
}


class SignupView(headless.SignupView):  # type: ignore[misc]  # allauth is untyped
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        with transaction.atomic():
            response: HttpResponse = super().post(request, *args, **kwargs)
        return response


class LoginView(headless.LoginView):  # type: ignore[misc]  # allauth is untyped
    def handle_invalid_input(self, input: Any) -> HttpResponse:
        codes = {error.code for errors in input.errors.as_data().values() for error in errors}
        status = next(
            (LOGIN_ERROR_STATUS[c] for c in LOGIN_ERROR_STATUS if c in codes),
            HTTPStatus.BAD_REQUEST,
        )
        response: HttpResponse = ErrorResponse(self.request, input=input, status=status)
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            email = str(input.data.get("email", "")) if hasattr(input, "data") else ""
            locked = bruteforce.locked_for(email)
            response["Retry-After"] = str(locked or settings.NUMO9_LOGIN_LOCKOUT_SECONDS)
        return response


class ManageTOTPView(headless_mfa.ManageTOTPView):  # type: ignore[misc]  # allauth is untyped
    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        response: HttpResponse = super().get(request, *args, **kwargs)
        if response.status_code == HTTPStatus.NOT_FOUND:  # not enrolled: set-up data
            payload = json.loads(response.content)
            meta = payload.get("meta", {})
            if meta.get("totp_url"):
                meta["qr_code"] = get_mfa_adapter().qr_code_data_uri(meta["totp_url"])
                response.content = json.dumps(payload).encode()
        return response

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        totp, recovery = totp_flows.activate_totp(request, self.input)
        codes = None
        if recovery is not None:
            wrapper = recovery.wrap()
            codes = wrapper.get_unused_codes()
            wrapper.mark_as_viewed()
        response: HttpResponse = mfa_response.AuthenticatorResponse(
            request, totp, meta={"recovery_codes": codes}
        )
        return response
