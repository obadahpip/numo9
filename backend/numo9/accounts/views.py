"""Numo9's adjustments to django-allauth's headless views (A-02).

Mounted in ``numo9/accounts/urls.py`` at the same paths as allauth's own views, ahead of
``allauth.headless.urls``, so the browser client keeps allauth's API contract:

- sign-up runs in one transaction — the user, their email address, the practice or
  organisation and the membership are created together or not at all (A-02-T02);
- login answers with the status the error means (A-02-T03): ``401`` for a wrong email or
  password (allauth says ``400``), ``429`` with ``Retry-After`` when the account is locked or the
  IP is rate limited; malformed input stays ``400``.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from allauth.headless.account import views as headless
from allauth.headless.internal.restkit.response import ErrorResponse
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse

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
            response["Retry-After"] = str(settings.NUMO9_LOGIN_LOCKOUT_SECONDS)
        return response
