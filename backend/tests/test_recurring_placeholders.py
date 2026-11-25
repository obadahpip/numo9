"""D-04-T03 — placeholder renderer: locale-aware month names, single pass, ICU-safe."""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.sales.placeholders import month_name, render, unknown

START, END = dt.date(2026, 10, 1), dt.date(2026, 10, 31)


@pytest.mark.parametrize(
    ("locale", "month"), [("en-CA", "October"), ("fr-CA", "octobre"), (None, "October")]
)
def test_month(locale: str | None, month: str) -> None:
    assert render("{{month}}", START, END, locale) == month
    assert month_name(10, locale) == month


def test_all_placeholders() -> None:
    text = "Retainer {{ month }} {{year}} ({{period_start}} – {{PERIOD_END}})"
    assert render(text, START, END, "en-CA") == "Retainer October 2026 (1 Oct 2026 – 31 Oct 2026)"
    assert render(text, START, END, "fr-CA") == "Retainer octobre 2026 (1 oct. 2026 – 31 oct. 2026)"
    assert (
        render("février {{month}}", dt.date(2026, 2, 1), dt.date(2026, 2, 28), "fr-CA")
        == "février février"
    )


def test_icu_safe_and_unknown() -> None:
    text = "It's {plural, one {#}} {{monthly}} {{month}} '{{year}}'"
    assert render(text, START, END, "en-CA") == "It's {plural, one {#}} {{monthly}} October '2026'"
    assert unknown(text) == ["monthly"]
    assert render("", START, END) == "" and render("no braces", START, END) == "no braces"
