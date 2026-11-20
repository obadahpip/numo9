"""A-02-T16 — optional social sign-in (Google, Microsoft) behind a feature flag, off by default.

Acceptance: flag off → the headless configuration names no provider (the sign-in page shows no
button) and a provider redirect is refused; flag on with credentials → Google and Microsoft are
listed; on without credentials → none; social sign-in never opens a sign-up.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client, override_settings

from numo9.accounts.social import FLAG, SocialAccountAdapter, social_signin_enabled
from numo9.platform.models import FeatureFlag

pytestmark = pytest.mark.django_db
CONFIG = "/_allauth/browser/v1/config"
REDIRECT = "/_allauth/browser/v1/auth/provider/redirect"

PROVIDERS: dict[str, Any] = {
    "google": {"APPS": [{"client_id": "g-id", "secret": "g-secret"}], "SCOPE": ["email"]},
    "microsoft": {
        "APPS": [{"client_id": "m-id", "secret": "m-secret", "settings": {"tenant": "common"}}],
        "SCOPE": ["email"],
    },
}


def switch(on: bool) -> None:
    FeatureFlag.objects.update_or_create(name=FLAG, defaults={"everyone": on})
    cache.clear()  # waffle caches flags


def providers(client: Client) -> list[str]:
    social = client.get(CONFIG).json()["data"].get("socialaccount", {})
    return sorted(p["id"] for p in social.get("providers", []))


def test_flag_is_off_by_default() -> None:
    # The migration creates it off (a flushed test database may not have the row: off as well).
    flag = FeatureFlag.objects.filter(name=FLAG).first()
    assert flag is None or flag.everyone is False
    assert not social_signin_enabled(Client().get(CONFIG).wsgi_request)


def test_migration_creates_the_flag_off() -> None:
    from importlib import import_module

    from django.apps import apps

    migration = import_module("numo9.accounts.migrations.0005_social_signin_flag")
    FeatureFlag.objects.filter(name=FLAG).delete()
    migration.create_flag(apps, None)
    assert FeatureFlag.objects.get(name=FLAG).everyone is False


@override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS)
def test_flag_off_hides_every_provider_and_refuses_the_redirect() -> None:
    client = Client()
    assert providers(client) == []
    response = client.post(
        REDIRECT,
        {"provider": "google", "process": "login", "callback_url": "/"},
    )
    # refused: back to the sign-in page with an error, never on to the provider
    assert response.status_code == 302
    assert response["Location"].startswith("http://localhost:3000/login?social=error")
    assert "google.com" not in response["Location"]


@override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS)
def test_flag_on_lists_google_and_microsoft() -> None:
    switch(True)
    client = Client()
    assert providers(client) == ["google", "microsoft"]
    response = client.post(
        REDIRECT, {"provider": "google", "process": "login", "callback_url": "/"}
    )
    assert response.status_code == 302
    assert response["Location"].startswith("https://accounts.google.com/")


def test_flag_on_without_credentials_lists_none() -> None:
    switch(True)
    assert providers(Client()) == []


def test_social_sign_in_never_signs_up() -> None:
    assert SocialAccountAdapter().is_open_for_signup(None, None) is False  # type: ignore[arg-type]
