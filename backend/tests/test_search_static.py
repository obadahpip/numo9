"""A-09-T04 — static providers: settings pages (with synonyms "lock date", "BN", "fiscal
year"), the reports catalogue and navigation — in the request's language.

Acceptance: "lock date" → the lock dates settings page; "BN" → tax registrations; "fiscal year"
→ general settings; prefixes and accents work ("annee fin"); French synonyms too; an exact title
or synonym ranks first; later modules can register entries.
"""

from __future__ import annotations

from django.utils import translation

from numo9.search.static import (
    NAVIGATION,
    REPORTS,
    SETTINGS,
    StaticEntry,
    match_static,
    register_static,
    static_entries,
)


def keys(query: str) -> list[str]:
    return [entry.key for entry in match_static(query)]


def test_synonyms_open_the_right_settings_page() -> None:
    assert keys("lock date")[0] == "settings.lock_dates"
    assert keys("BN")[0] == "settings.registrations"
    assert keys("fiscal year")[0] == "settings.general"
    assert keys("lock dat")[0] == "settings.lock_dates"  # prefixes
    assert "settings.general" in keys("annee fin")  # accents ignored
    assert keys("verrouillage") == ["settings.lock_dates"]


def test_groups_cover_settings_reports_navigation() -> None:
    groups = {entry.group for entry in static_entries()}
    assert groups == {SETTINGS, REPORTS, NAVIGATION}
    assert keys("chart")[0] == "nav.chart_of_accounts"


def test_titles_follow_the_language() -> None:
    entry = next(e for e in static_entries() if e.key == "settings.lock_dates")
    with translation.override("en-ca"):
        assert str(entry.title) == "Lock dates"
    assert match_static("") == []


def test_modules_register_their_own_entries() -> None:
    register_static(
        StaticEntry("reports.aged_receivables", REPORTS, "Aged receivables", "reports/ar")
    )
    try:
        assert keys("aged")[0] == "reports.aged_receivables"
    finally:
        from numo9.search import static

        static._entries.pop("reports.aged_receivables", None)
