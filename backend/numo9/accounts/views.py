"""Numo9's adjustments to django-allauth's headless views (A-02).

Mounted in ``numo9/accounts/urls.py`` at the same paths as allauth's own views, ahead of
``allauth.headless.urls``, so the browser client keeps allauth's API contract:

- sign-up runs in one transaction — the user, their email address, the practice or
  organisation and the membership are created together or not at all (A-02-T02).
"""

from __future__ import annotations

from typing import Any

from allauth.headless.account import views as headless
from django.db import transaction
from django.http import HttpRequest, HttpResponse


class SignupView(headless.SignupView):  # type: ignore[misc]  # allauth is untyped
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        with transaction.atomic():
            response: HttpResponse = super().post(request, *args, **kwargs)
        return response
