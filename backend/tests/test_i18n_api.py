"""A-10-T14 — backend i18n: request locale (user → cookie → Accept-Language), gettext catalogues,
error messages as keys; API errors are localised."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.test import RequestFactory
from django.utils import translation
from rest_framework.test import APIClient

from numo9.accounts.models import Locale, User
from numo9.i18n import errors
from numo9.i18n.locale import locale_for, normalise_locale, override_for, request_locale
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole, Practice
from tools.compile_messages import compile_po
from tools.i18n_catalogs import BACKEND_LOCALE_DIR, load_po

pytestmark = pytest.mark.django_db

ORGANISATIONS = "/api/v1/organisations"
ME = "/api/v1/me/organisations"


def signed_in(locale: str) -> APIClient:
    user = User.objects.create_user(
        f"{uuid.uuid4().hex[:8]}@example.com", name="Dana", locale=locale
    )
    client = APIClient()
    client.force_login(user)  # session, as the web app signs in
    return client


# ---- API errors are localised ----------------------------------------------------------------


def test_field_error_in_french_for_a_french_user() -> None:
    response = signed_in(Locale.FR_CA).post(
        ORGANISATIONS, {"name": "X", "practice": str(uuid.uuid4())}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {
        "practice": [
            "Ce cabinet n’existe pas ou vous n’en êtes pas membre. Choisissez l’un de vos cabinets."
        ]
    }
    assert response["Content-Language"] == "fr-ca"


def test_same_error_in_english_for_an_english_user() -> None:
    practice = Practice.objects.create(name="Other firm")
    response = signed_in(Locale.EN_CA).post(
        ORGANISATIONS, {"name": "X", "practice": str(practice.public_id)}, format="json"
    )
    assert response.json() == {
        "practice": [
            "This practice doesn't exist or you're not a member. Choose one of your practices."
        ]
    }
    assert response["Content-Language"] == "en-ca"


def test_model_validation_message_in_french() -> None:
    response = signed_in(Locale.FR_CA).post(
        ORGANISATIONS, {"name": "X", "time_zone": "Mars/Olympus"}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"time_zone": ["Mars/Olympus n’est pas un fuseau horaire valide."]}


def test_request_errors_carry_a_stable_code_and_a_localised_message() -> None:
    anonymous = APIClient()
    english = anonymous.get(ME, HTTP_ACCEPT_LANGUAGE="en-CA").json()
    french = anonymous.get(ME, HTTP_ACCEPT_LANGUAGE="fr-CA,fr;q=0.9").json()
    assert english["code"] == french["code"] == "not_authenticated"
    assert english["detail"] == "Authentication credentials were not provided."
    assert french["detail"] != english["detail"]  # DRF's French catalogue (fr) via fr-ca fallback
    assert "authentification" in french["detail"].lower()


def test_tenant_404_and_400_are_localised_with_codes() -> None:
    client = signed_in(Locale.FR_CA)
    not_found = client.get(f"/api/v1/o/{uuid.uuid4()}/ctx/")
    assert not_found.status_code == 404
    assert not_found.json()["code"] == "not_found"
    assert not_found.json()["detail"] != "Not found."

    org = Organisation.objects.create(name="A")
    other = Organisation.objects.create(name="B")
    mismatch = client.get(f"/api/v1/o/{org.public_id}/ctx/", HTTP_X_NUMO9_ORG=str(other.public_id))
    assert mismatch.status_code == 400
    assert mismatch.json() == {
        "detail": "L’organisation de l’adresse et celle de l’en-tête X-Numo9-Org diffèrent. "
        "Envoyez une seule organisation, ou la même dans les deux.",
        "code": "tenancy.org_header_mismatch",
    }


def test_the_users_choice_beats_the_browser_language() -> None:
    client = signed_in(Locale.EN_CA)
    response = client.post(
        ORGANISATIONS,
        {"name": "X", "practice": str(uuid.uuid4())},
        format="json",
        HTTP_ACCEPT_LANGUAGE="fr-CA",
    )
    assert response.json()["practice"][0].startswith("This practice")


def test_language_is_reset_after_the_request() -> None:
    signed_in(Locale.FR_CA).get(ME)
    assert translation.get_language() in ("en-ca", None)


# ---- request locale resolution ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("fr-CA", "fr-ca"),
        ("fr_CA", "fr-ca"),
        ("fr", "fr-ca"),
        ("FR-fr", "fr-ca"),
        ("en-US", "en-ca"),
        ("de", None),
        ("", None),
        (None, None),
    ],
)
def test_normalise_locale(code: str | None, expected: str | None) -> None:
    assert normalise_locale(code) == expected


@pytest.mark.parametrize(
    ("cookie", "accept", "expected"),
    [
        (None, None, "en-ca"),
        ("fr-CA", "en-US", "fr-ca"),  # the web app's cookie (A-10-T13) beats the browser
        (None, "de-DE,fr;q=0.8,en;q=0.5", "fr-ca"),
        (None, "fr;q=0,en", "en-ca"),
        ("xx", "es", "en-ca"),
    ],
)
def test_request_locale_for_signed_out_requests(
    cookie: str | None, accept: str | None, expected: str
) -> None:
    request = RequestFactory().get("/", HTTP_ACCEPT_LANGUAGE=accept or "")
    if cookie:
        request.COOKIES["numo9_locale"] = cookie
    request.user = SimpleNamespace(is_authenticated=False)  # type: ignore[assignment]
    assert request_locale(request) == expected


def test_locale_for_output_without_a_request_user_then_organisation() -> None:
    org = Organisation.objects.create(name="Érable Québec", locale=Locale.FR_CA)
    english_user = User.objects.create_user("en@example.com", name="En", locale=Locale.EN_CA)
    assert locale_for(user=english_user, organisation=org) == "en-ca"
    assert locale_for(organisation=org) == "fr-ca"
    assert locale_for() == "en-ca"
    with override_for(organisation=org):
        assert str(errors.UNKNOWN_PRACTICE.message).startswith("Ce cabinet")


def test_organisation_locale_is_exposed_and_settable() -> None:
    client = signed_in(Locale.EN_CA)
    created = client.post(
        ORGANISATIONS, {"name": "Érable Québec", "locale": "fr-ca"}, format="json"
    )
    assert created.status_code == 201
    assert created.json()["locale"] == "fr-ca"
    assert Organisation.objects.get(name="Érable Québec").locale == "fr-ca"
    invalid = client.post(ORGANISATIONS, {"name": "X", "locale": "de-de"}, format="json")
    assert invalid.status_code == 400


def test_organisation_locale_defaults_to_english() -> None:
    org = Organisation.objects.create(name="Plain")
    OrganisationMember.objects.create(
        organisation=org,
        user=User.objects.create_user("o@example.com", name="O"),
        role=OrganisationRole.OWNER,
    )
    assert org.locale == "en-ca"


# ---- error catalogue: messages as keys -------------------------------------------------------


def test_every_catalogue_error_has_a_dotted_key_and_a_french_translation() -> None:
    fr = {
        entry.msgid: entry.msgstr[0]
        for entry in load_po(BACKEND_LOCALE_DIR / "fr_CA" / "LC_MESSAGES" / "django.po")
    }
    assert errors.CATALOGUE, "catalogue is empty"
    for code, error in errors.CATALOGUE.items():
        assert re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", code)
        with translation.override("en-ca"):
            msgid = str(error.message)
        assert msgid in fr, f"{code}: message missing from fr_CA/django.po (run make i18n)"
        assert fr[msgid], f"{code}: no French translation yet"


def test_define_rejects_bad_and_duplicate_codes() -> None:
    with pytest.raises(ValueError, match="dotted"):
        errors.define("NoDots", errors.UNKNOWN_PRACTICE.message)
    with pytest.raises(ValueError, match="twice"):
        errors.define("tenancy.unknown_practice", errors.UNKNOWN_PRACTICE.message)


def test_error_detail_and_api_error_carry_the_key() -> None:
    detail = errors.error_detail(errors.UNKNOWN_PRACTICE)
    assert detail.code == "tenancy.unknown_practice"
    exc = errors.api_error(errors.ORG_HEADER_MISMATCH)
    assert exc.status_code == 400
    assert exc.get_codes() == "tenancy.org_header_mismatch"


# ---- compiled catalogues ------------------------------------------------------------------------


def test_compile_messages_matches_gnu_mo_format(tmp_path: Path) -> None:
    import gettext

    def entry(source: str, target: str, extra: str = "") -> str:
        # One sample catalogue entry.
        return f'{extra}msgid "{source}"\nmsgstr "{target}"\n\n'

    one, many = "%(n)s line", "%(n)s lines"
    po = (
        'msgid ""\nmsgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Plural-Forms: nplurals=2; plural=(n > 1);\\n"\n\n'
        + entry("Save", "Enregistrer")
        + entry("Draft", "Brouillon?", "#, fuzzy\n")
        + entry("Untranslated", "")
        + entry("Post", "Comptabiliser", 'msgctxt "button"\n')
        + f'msgid "{one}"\nmsgid_plural "{many}"\n'
        + 'msgstr[0] "%(n)s ligne"\nmsgstr[1] "%(n)s lignes"\n'
    )
    mo = tmp_path / "django.mo"
    mo.write_bytes(compile_po(po))
    catalogue = gettext.GNUTranslations(mo.open("rb"))
    # Aliases: `makemessages` would collect literal gettext(...) calls as project strings.
    lookup, lookup_ctx, lookup_plural = catalogue.gettext, catalogue.pgettext, catalogue.ngettext
    assert lookup("Save") == "Enregistrer"
    assert lookup("Draft") == "Draft"  # fuzzy entries are not used
    assert lookup("Untranslated") == "Untranslated"
    assert lookup_ctx("button", "Post") == "Comptabiliser"
    assert lookup_plural("%(n)s line", "%(n)s lines", 2) == "%(n)s lignes"
    assert lookup_plural("%(n)s line", "%(n)s lines", 1) == "%(n)s ligne"


def test_committed_catalogues_compile_and_are_current() -> None:
    from tools.compile_messages import main

    assert main(["--check"]) == 0  # conftest compiled them for this session
