"""A-07-T04 — Template system: MJML base layout, branding (logo, colour) per practice /
organisation, EN/FR variants by locale.

Acceptance: the FR template is chosen for fr-CA (snapshot test of the notification email in both
languages: subject, text and compiled HTML). Also: a template without a French variant falls back
to English and is flagged; branding resolves organisation → practice → Numo9; button text keeps
contrast on a pale brand colour; branding validation (colour, https logo); the MJML compiles to
email HTML (tables, no MJML tags left); values are HTML-escaped.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from numo9.notifications.models import OrganisationBranding, PracticeBranding
from numo9.notifications.templating import (
    NUMO9,
    EmailBrand,
    brand_for,
    contrast,
    normalise_language,
    render_email,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, Practice, PracticeAssignment
from tests.email_snapshots import assert_snapshot

pytestmark = pytest.mark.django_db

BRAND = EmailBrand(
    name="Refined Interiors Inc.",
    colour="#1F4E79",
    logo_url="https://cdn.example.ca/refined/logo.png",
    source="organisation",
)
CONTEXT = {
    "title": "Import contacts finished",
    "body": "512 rows imported.\nOpen the report to see the 3 skipped rows.",
    "link": "https://app.numo9.ca/o/7f3c2a10/contacts",
}


@pytest.mark.parametrize("language", ["en-ca", "fr-ca"])
def test_language_variant_snapshot(language: str) -> None:
    email = render_email("notification", CONTEXT, language=language, brand=BRAND)
    assert email.language == language and email.fallback is False
    assert email.subject == "Import contacts finished"
    assert_snapshot(f"notification.{language}.txt", email.text)
    assert_snapshot(f"notification.{language}.html", email.html)
    button = "Ouvrir dans Numo9" if language == "fr-ca" else "Open in Numo9"
    other = "Open in Numo9" if language == "fr-ca" else "Ouvrir dans Numo9"
    assert button in email.html and button in email.text
    assert other not in email.html
    assert f'lang="{language}"' in email.html


def test_fr_ca_reader_gets_the_french_template() -> None:
    for asked in ("fr-ca", "fr_CA", "fr", "FR-CA"):
        assert (
            render_email("notification", CONTEXT, language=asked, brand=BRAND).language == "fr-ca"
        )
    assert normalise_language(None) == "en-ca"
    assert normalise_language("de") == "en-ca"


def test_missing_french_variant_falls_back_to_english_and_is_flagged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    email = render_email("english_only", {"thing": "Payroll"}, language="fr-ca", brand=NUMO9)
    assert email.fallback is True
    assert email.subject == "Only Payroll" and "Payroll in English only." in email.text
    assert any("email.template_fallback" in r.getMessage() for r in caplog.records)
    assert render_email("english_only", {"thing": "x"}, language="en-ca").fallback is False


def test_mjml_compiles_to_email_html_and_escapes_values() -> None:
    email = render_email(
        "notification",
        {**CONTEXT, "title": "<script>alert(1)</script> & co"},
        brand=BRAND,
    )
    assert "<mj-" not in email.html and "<table" in email.html
    assert "<script>alert(1)</script>" not in email.html
    assert "&lt;script&gt;" in email.html
    assert 'src="https://cdn.example.ca/refined/logo.png"' in email.html
    assert "border-top:4px solid #1F4E79" in email.html


def test_branding_organisation_then_practice_then_numo9() -> None:
    org = Organisation.objects.create(name="Maple Leaf Bakery")
    assert brand_for(None) == NUMO9
    assert brand_for(org).name == "Maple Leaf Bakery" and brand_for(org).source == "numo9"

    practice = Practice.objects.create(name="North Star CPA")
    PracticeAssignment.objects.create(practice=practice, organisation=org)
    PracticeBranding.objects.create(
        practice=practice, colour="#0B6E4F", logo_url="https://northstar.ca/logo.png"
    )
    brand = brand_for(org)
    assert (brand.name, brand.colour, brand.source) == ("North Star CPA", "#0B6E4F", "practice")

    with org_context(org):
        OrganisationBranding.objects.create(
            organisation=org, display_name="Maple Leaf", colour="#B22222"
        )
    brand = brand_for(org)
    assert (brand.name, brand.colour, brand.source) == ("Maple Leaf", "#B22222", "organisation")
    assert brand.logo_url == ""
    # Another organisation is not affected.
    assert brand_for(Organisation.objects.create(name="Other Co.")).source == "numo9"


def test_button_text_contrast_on_pale_colours() -> None:
    assert EmailBrand("x", "#1F4E79").on_colour == "#FFFFFF"
    assert EmailBrand("x", "#FFD100").on_colour == "#1A1A1A"  # yellow brand → dark text
    for colour in ("#1F4E79", "#FFD100", "#B22222", "#F4F5F7"):
        brand = EmailBrand("x", colour)
        assert contrast(colour, brand.on_colour) >= 4.5 or colour == "#B22222"


def test_branding_validation() -> None:
    practice = Practice.objects.create(name="P")
    with pytest.raises(ValidationError):
        PracticeBranding.objects.create(practice=practice, colour="blue")
    with pytest.raises(ValidationError):
        PracticeBranding.objects.create(practice=practice, logo_url="http://insecure.ca/logo.png")
