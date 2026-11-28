"""K-09-T27 — i18n of the rules: every rule's name, description, explanation template and
parameter labels exist in English and in Canadian French (fr-CA differs from the English and keeps
the template's placeholders), so a finding reads in the person's language.
"""

from __future__ import annotations

import re

import pytest
from django.utils import translation

from numo9.assurance.rules.base import registry

PLACEHOLDER = re.compile(r"%\((\w+)\)s")
# Words that are the same in both languages.
SAME = {"Date", "Description", "Total", "Info", "Actions"}


@pytest.mark.parametrize("code", registry.codes())
def test_rule_texts_are_translated(code: str) -> None:
    rule = registry.get(code)
    texts = {
        "name": rule.name,
        "description": rule.description,
        "explanation": rule.explanation,
        **{f"param {n}": p.label for n, p in rule.params.items()},
    }
    for key, text in texts.items():
        with translation.override("en-ca"):
            english = str(text)
        with translation.override("fr-ca"):
            french = str(text)
        assert english.strip(), f"{code} {key}: no English text"
        assert french.strip() and (french != english or english in SAME), (
            f"{code} {key}: not translated to French ({english!r})"
        )
        assert sorted(PLACEHOLDER.findall(french)) == sorted(PLACEHOLDER.findall(english)), (
            f"{code} {key}: placeholders differ"
        )
