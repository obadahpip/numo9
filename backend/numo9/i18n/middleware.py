"""Locale middleware (A-10-T14): activates the request's language (see ``locale.request_locale``).

Install after ``AuthenticationMiddleware`` (the user's own locale wins) and before
``TenantContextMiddleware`` (its 404/400 answers are then localised too). Responses carry
``Content-Language`` and ``Vary: Accept-Language, Cookie``.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.utils import translation
from django.utils.cache import patch_vary_headers

from .locale import request_locale


class LocaleMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        language = request_locale(request)
        with translation.override(language):
            request.LANGUAGE_CODE = translation.get_language()
            response = self.get_response(request)
        patch_vary_headers(response, ("Accept-Language", "Cookie"))
        response.headers.setdefault("Content-Language", language)
        return response
