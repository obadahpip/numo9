"""Which language a request, an email or a document uses (A-10-T14).

Request (API and pages), first match wins:

1. the signed-in user's ``locale`` (A-02-T01) — what they chose in their profile;
2. the ``numo9_locale`` cookie — the web app's language (A-10-T13), for signed-out pages;
3. the browser's ``Accept-Language`` (``fr``, ``fr-FR`` → French (Canada));
4. ``LANGUAGE_CODE`` (English (Canada)).

Work without a request (emails, PDFs, background jobs) uses :func:`locale_for`: the recipient
user's locale, else the organisation's ``locale``, else English (Canada).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.utils import translation

SUPPORTED = ("en-ca", "fr-ca")
DEFAULT = "en-ca"


def normalise_locale(code: str | None) -> str | None:
    """``fr-CA`` / ``fr_CA`` / ``fr`` / ``FR-fr`` → ``fr-ca``; unsupported → None."""
    if not code:
        return None
    tag = code.strip().replace("_", "-").lower()
    if tag in SUPPORTED:
        return tag
    language = tag.split("-")[0]
    for supported in SUPPORTED:
        if supported.split("-")[0] == language:
            return supported
    return None


def request_locale(request: HttpRequest) -> str:
    user: Any = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        chosen = normalise_locale(getattr(user, "locale", None))
        if chosen:
            return chosen
    cookie = normalise_locale(request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME))
    if cookie:
        return cookie
    for part in request.headers.get("Accept-Language", "").split(","):
        tag, _, quality = part.strip().partition(";q=")
        if quality:
            try:
                if float(quality) <= 0:
                    continue
            except ValueError:
                continue
        chosen = normalise_locale(tag)
        if chosen:
            return chosen
    return normalise_locale(settings.LANGUAGE_CODE) or DEFAULT


def locale_for(user: Any = None, organisation: Any = None) -> str:
    """Locale for output without a request: the user's, else the organisation's, else default."""
    for source in (user, organisation):
        chosen = normalise_locale(getattr(source, "locale", None)) if source is not None else None
        if chosen:
            return chosen
    return DEFAULT


def override_for(user: Any = None, organisation: Any = None) -> translation.override:
    """``with override_for(user=u, organisation=o): render_email(...)``."""
    return translation.override(locale_for(user, organisation))
