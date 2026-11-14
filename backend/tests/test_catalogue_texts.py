"""Catalogue texts (U-01-T13): every product name and feature description has an i18n key with
an en-CA text and a fr-CA entry (empty = English placeholder until Phase 6); 0 hard-coded
strings — the API and exports show the translated texts, never a fallback code."""

from __future__ import annotations

import pytest
from django.utils import translation

from numo9.catalogue.models import FeatureKey, Product
from numo9.catalogue.texts import FEATURE_DESCRIPTIONS, PRODUCT_NAMES, text_for
from tools.i18n_catalogs import BACKEND_LOCALE_DIR, load_po

pytestmark = pytest.mark.django_db


def po(locale: str) -> dict[str, str]:
    path = BACKEND_LOCALE_DIR / locale / "LC_MESSAGES" / "django.po"
    return {entry.msgid: entry.msgstr[0] for entry in load_po(path)}


def test_every_seeded_key_has_a_text() -> None:
    names = set(Product.objects.values_list("name_i18n_key", flat=True))
    descriptions = set(FeatureKey.objects.values_list("description_i18n_key", flat=True))
    assert names - set(PRODUCT_NAMES) == set()
    assert descriptions - set(FEATURE_DESCRIPTIONS) == set()
    # and nothing stale: every text belongs to a seeded row
    assert set(PRODUCT_NAMES) == names
    assert set(FEATURE_DESCRIPTIONS) == descriptions


def test_texts_are_never_the_fallback() -> None:
    with translation.override("en-ca"):
        for feature in FeatureKey.objects.all():
            text = text_for(feature.description_i18n_key, feature.key)
            assert text != feature.key and text[0].isupper() and not text.endswith(".")
        for product in Product.objects.all():
            assert text_for(product.name_i18n_key, product.code) != product.code


@pytest.mark.parametrize("locale", ["en_CA", "fr_CA"])
def test_every_text_is_in_both_backend_catalogues(locale: str) -> None:
    catalogue = po(locale)
    with translation.override("en-ca"):
        msgids = {str(m) for m in [*PRODUCT_NAMES.values(), *FEATURE_DESCRIPTIONS.values()]}
    missing = msgids - set(catalogue)
    assert missing == set(), f"run make i18n: {sorted(missing)[:5]}"


def test_french_falls_back_to_english_until_phase_6() -> None:
    with translation.override("fr-ca"):
        assert text_for("catalogue.product.tax", "tax") == "Taxes"  # translated already
        reminder = text_for("catalogue.feature.accounting.invoice_reminders.write", "x")
    assert reminder == "Send invoice reminders before and after the due date"  # placeholder
