"""A-02-T15 — i18n keys EN/FR for all auth emails and screens.

Backend side (the screens' French catalogue is checked by the CI missing-key gate and the
frontend i18n tests): every authentication email goes in the language of the account it is
about — a French-speaking user's verification, password-reset and invitation emails are
French, an English-speaking user's English, whatever the language of the browser that
triggered them; Numo9's own auth messages (lockout, breached password, sign-up form) have their
French text.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.test import Client
from django.utils import translation

from numo9.accounts.adapter import AccountAdapter
from numo9.accounts.validators import BreachedPasswordValidator
from tests.auth_helpers import post

pytestmark = pytest.mark.django_db


def test_password_reset_email_in_the_account_language() -> None:
    from tests.auth_helpers import make_user

    make_user("francine@maple.ca", locale="fr-ca")
    make_user("dana@maple.ca", locale="en-ca")
    english_browser = Client(HTTP_ACCEPT_LANGUAGE="en-CA")
    post(english_browser, "/auth/password/request", {"email": "francine@maple.ca"})
    french_browser = Client(HTTP_ACCEPT_LANGUAGE="fr-CA")
    post(french_browser, "/auth/password/request", {"email": "dana@maple.ca"})
    francine, dana = mail.outbox
    assert francine.to == ["francine@maple.ca"] and dana.to == ["dana@maple.ca"]
    assert francine.subject == "Numo9 · Réinitialisez votre mot de passe"
    assert "Ouvrez ce lien dans l’heure" in francine.body
    assert dana.subject == "Numo9 · Reset your password"
    assert "Open this link within 1 hour" in dana.body and "mot de passe" not in dana.body


def test_verification_email_follows_the_signup_language() -> None:
    browser = Client(HTTP_ACCEPT_LANGUAGE="fr-CA")
    answer = post(
        browser,
        "/auth/signup",
        {
            "email": "louis@erable.ca",
            "password": "correct horse battery 42",
            "name": "Louis Tremblay",
            "path": "organisation",
            "organisation_name": "Érable Inc.",
            "locale": "fr-ca",
        },
    )
    assert answer.status_code in (200, 401), answer.content
    [verification] = mail.outbox
    assert verification.to == ["louis@erable.ca"]
    assert verification.subject == "Numo9 · Vérifiez votre adresse courriel"
    assert "terminer la configuration de votre compte Numo9" in verification.body


def test_numo9_auth_messages_have_french() -> None:
    with translation.override("fr-ca"):
        assert "verrouillé" in str(AccountAdapter.error_messages["too_many_login_attempts"])
        assert "vérification" in str(AccountAdapter.error_messages["captcha_required"])
        assert "fuite de données" in BreachedPasswordValidator().get_help_text()
