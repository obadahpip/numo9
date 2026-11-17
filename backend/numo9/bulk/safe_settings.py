"""Safe settings (V-03-T03): the organisation settings a practice may change for many
organisations at once — declared here, in code. Anything else is refused
(``bulk.unsafe_setting``); every value is validated before the preview.

- ``sales_terms`` (``type``, ``days``) — default due date of invoices: an A-05 terms type and
  0–365 days, or day 1–31 of a month;
- ``purchase_terms`` (``type``, ``days``) — default due date of bills, the same rules;
- ``time_format`` (``value``) — ``12h`` / ``24h`` on documents and emails;
- ``fiscal_year_end`` (``month``, ``day``) — a real day of that month, and **only for
  organisations without posted transactions** (otherwise the row is skipped:
  ``fye_has_posted``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext as _

from numo9.accounts.models import TimeFormat
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.orgsettings.models import (
    DAY_OF_MONTH_TERMS,
    MAX_TERM_DAYS,
    MONTH_DAYS,
    OrganisationSettings,
    TermsType,
)
from numo9.tenancy.models import Organisation


def _bad(message: str) -> Exception:
    return api_error(errors.BULK_BAD_VALUE, message=message)


def _int(value: Any, message: str) -> int:
    if isinstance(value, bool):
        raise _bad(message)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise _bad(message) from None


def _terms(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("type") not in TermsType.values:
        raise _bad(_("Choose how the due date is worked out."))
    days = _int(value.get("days"), _("Enter the number of days."))
    if value["type"] in DAY_OF_MONTH_TERMS:
        if not 1 <= days <= 31:
            raise _bad(_("Choose a day of the month from 1 to 31."))
    elif not 0 <= days <= MAX_TERM_DAYS:
        raise _bad(_("Enter 0 to %(max)s days.") % {"max": MAX_TERM_DAYS})
    return {"type": value["type"], "days": days}


def _time_format(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("value") not in TimeFormat.values:
        raise _bad(_("Choose 12-hour or 24-hour times."))
    return {"value": value["value"]}


def _fiscal_year_end(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _bad(_("Choose the month and day of the fiscal year end."))
    month = _int(value.get("month"), _("Choose the month of the fiscal year end."))
    day = _int(value.get("day"), _("Choose the day of the fiscal year end."))
    if month not in MONTH_DAYS or not 1 <= day <= MONTH_DAYS[month]:
        raise _bad(_("That month has no day %(day)d.") % {"day": day})
    return {"month": month, "day": day}


def _has_posted(organisation: Organisation) -> str | None:
    from numo9.ledger.models import LOCKED_STATUSES, JournalEntry

    posted = JournalEntry._base_manager.filter(
        organisation=organisation, status__in=LOCKED_STATUSES
    ).exists()
    return "fye_has_posted" if posted else None


@dataclass(frozen=True)
class SafeSetting:
    key: str
    fields: dict[str, str]  # value field → OrganisationSettings field
    clean: Callable[[Any], dict[str, Any]]
    guard: Callable[[Organisation], str | None] | None = None

    def read(self, settings: OrganisationSettings) -> dict[str, Any]:
        return {name: getattr(settings, field) for name, field in self.fields.items()}

    def write(self, settings: OrganisationSettings, value: dict[str, Any]) -> list[str]:
        changed = []
        for name, field in self.fields.items():
            if getattr(settings, field) != value[name]:
                setattr(settings, field, value[name])
                changed.append(field)
        return changed


SAFE_SETTINGS: dict[str, SafeSetting] = {
    setting.key: setting
    for setting in (
        SafeSetting(
            "sales_terms", {"type": "sales_terms_type", "days": "sales_terms_days"}, _terms
        ),
        SafeSetting(
            "purchase_terms",
            {"type": "purchase_terms_type", "days": "purchase_terms_days"},
            _terms,
        ),
        SafeSetting("time_format", {"value": "time_format"}, _time_format),
        SafeSetting(
            "fiscal_year_end",
            {"month": "fye_month", "day": "fye_day"},
            _fiscal_year_end,
            guard=_has_posted,
        ),
    )
}


def clean_settings(values: Any) -> dict[str, dict[str, Any]]:
    """The validated ``{key: value}`` of a settings bulk action; refuses anything not listed."""
    if not isinstance(values, dict) or not values:
        raise _bad(_("Choose at least one setting to change."))
    cleaned: dict[str, dict[str, Any]] = {}
    for key, value in values.items():
        setting = SAFE_SETTINGS.get(str(key))
        if setting is None:
            raise api_error(errors.BULK_UNSAFE_SETTING, name=str(key)[:100])
        cleaned[setting.key] = setting.clean(value)
    return cleaned
