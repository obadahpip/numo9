"""V-03-T03 — safe-settings whitelist registry + validators.

Acceptance: a setting that isn't whitelisted is rejected (``bulk.unsafe_setting``); whitelisted
values are validated (terms, time format, fiscal year end); the fiscal year end is guarded for
organisations with posted transactions.
"""

from __future__ import annotations

import pytest
from rest_framework.exceptions import APIException

from numo9.bulk.safe_settings import SAFE_SETTINGS, clean_settings
from numo9.tenancy.models import Organisation


def code(exc: pytest.ExceptionInfo[APIException]) -> str:
    return str(exc.value.get_codes() if hasattr(exc.value, "get_codes") else exc.value)


@pytest.mark.parametrize(
    "key", ["legal_name", "business_number", "base_currency", "time_zone", "display_name", ""]
)
def test_non_whitelisted_settings_are_rejected(key: str) -> None:
    with pytest.raises(APIException) as refused:
        clean_settings({key: {"value": "x"}})
    assert "bulk.unsafe_setting" in code(refused)


def test_whitelist() -> None:
    assert set(SAFE_SETTINGS) == {"sales_terms", "purchase_terms", "time_format", "fiscal_year_end"}


def test_valid_values_are_cleaned() -> None:
    assert clean_settings(
        {
            "sales_terms": {"type": "days_after_document", "days": "15"},
            "purchase_terms": {"type": "day_of_following_month", "days": 20},
            "time_format": {"value": "24h"},
            "fiscal_year_end": {"month": 3, "day": 31},
        }
    ) == {
        "sales_terms": {"type": "days_after_document", "days": 15},
        "purchase_terms": {"type": "day_of_following_month", "days": 20},
        "time_format": {"value": "24h"},
        "fiscal_year_end": {"month": 3, "day": 31},
    }


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"sales_terms": {"type": "whenever", "days": 1}},
        {"sales_terms": {"type": "days_after_document", "days": 366}},
        {"sales_terms": {"type": "day_of_current_month", "days": 0}},
        {"sales_terms": {"type": "days_after_document", "days": True}},
        {"time_format": {"value": "13h"}},
        {"fiscal_year_end": {"month": 2, "day": 30}},
        {"fiscal_year_end": {"month": 13, "day": 1}},
    ],
)
def test_bad_values_are_rejected(values: dict[str, object]) -> None:
    with pytest.raises(APIException) as refused:
        clean_settings(values)
    assert "bulk.bad_value" in code(refused)


@pytest.mark.django_db
def test_fiscal_year_end_is_guarded_by_posted_transactions() -> None:
    org = Organisation.objects.create(name="Maple")
    guard = SAFE_SETTINGS["fiscal_year_end"].guard
    assert guard is not None and guard(org) is None
    assert SAFE_SETTINGS["sales_terms"].guard is None
