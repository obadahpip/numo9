"""Optional social sign-in — Google and Microsoft (A-02-T16), behind a feature flag.

Off by default: the flag ``auth.social_signin`` (django-waffle, ``platform.FeatureFlag``; created
off by the migration and switched in the console, U-06-T12) decides. While it is off the adapter
lists **no** provider app, so allauth's headless configuration (``GET /_allauth/browser/v1/config``)
names no provider — the sign-in page shows no button — and a provider redirect is refused (the
app doesn't exist). A provider also needs its client id and secret in the environment
(``NUMO9_GOOGLE_CLIENT_ID``/``_SECRET``, ``NUMO9_MICROSOFT_CLIENT_ID``/``_SECRET``).

Social sign-in signs in an **existing** Numo9 account whose verified email the provider returns
(``SOCIALACCOUNT_EMAIL_AUTHENTICATION``, auto-connected); it never creates an account — sign-up
stays the 4-field form with its path (accountant / organisation), so the practice or trial
organisation is always created.
"""

from __future__ import annotations

from typing import Any

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpRequest

FLAG = "auth.social_signin"
PROVIDERS: tuple[str, ...] = ("google", "microsoft")


def social_signin_enabled(request: HttpRequest | None) -> bool:
    from waffle import flag_is_active

    if request is None:
        return False
    return bool(flag_is_active(request, FLAG))


class SocialAccountAdapter(DefaultSocialAccountAdapter):  # type: ignore[misc]  # allauth is untyped
    def list_apps(
        self, request: HttpRequest, provider: Any = None, client_id: Any = None
    ) -> list[Any]:
        if not social_signin_enabled(request):
            return []
        apps: list[Any] = super().list_apps(request, provider=provider, client_id=client_id)
        return [app for app in apps if app.provider in PROVIDERS]

    def is_open_for_signup(self, request: HttpRequest, sociallogin: Any) -> bool:
        return False  # sign-up is the 4-field form; social sign-in is for existing accounts
