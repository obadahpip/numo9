"""Effective-date resolver (G-01-T08): which tax codes a document dated D may use.

- ``codes_available(side, date, organisation)`` — the code versions in force on ``date`` on that
  side, archived codes excluded: what pickers offer. An ended rate (MB RST 8 % to 30 Jun 2019,
  NS HST 15 % to 31 Mar 2025) is never offered on a later document.
- ``code_for(key, side, date)`` — the version of code ``key`` in force on ``date``;
  ``TaxCodeExpired`` when the code exists but none of its versions covers the date (it ended
  before or starts after), ``TaxCodeUnknown`` when there is no such code on that side.
- ``check_code(version, date)`` — validation of a stored line: the version must be in force on
  the document's date, else ``TaxCodeExpired`` naming the code and its range ("re-pick the code"
  when an old draft's date moves past a rate change); an archived code is refused too
  (``tax.code.archived``).

The organisation's table is installed on first use (``ensure_tax_table``).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db.models import Q, QuerySet
from django.utils.translation import gettext as _

from numo9.tenancy.context import current_org, org_context

from .models import TaxCode, TaxError
from .seed import ensure_tax_table


class TaxCodeExpired(TaxError):
    """The code isn't in force on the document's date."""


class TaxCodeUnknown(TaxError):
    """No such tax code on that side."""


def _organisation(organisation: Any) -> Any:
    organisation = organisation or current_org()
    if organisation is None:
        raise ValueError("Tax codes are read inside org_context() or for an organisation.")
    return organisation


def active_q(day: dt.date) -> Q:
    return Q(effective_from__lte=day) & (Q(effective_to__isnull=True) | Q(effective_to__gte=day))


def codes_available(side: str, day: dt.date, organisation: Any = None) -> QuerySet[TaxCode]:
    """Code versions in force on ``day`` for ``side``, archived ones excluded, by code."""
    organisation = _organisation(organisation)
    ensure_tax_table(organisation)
    with org_context(organisation):
        return (
            TaxCode.objects.filter(side=side, archived_at__isnull=True)
            .filter(active_q(day))
            .order_by("code")
        )


def _range(version: TaxCode) -> str:
    end = version.effective_to.isoformat() if version.effective_to else "…"
    return f"{version.effective_from.isoformat()} – {end}"


def check_code(version: TaxCode, day: dt.date) -> TaxCode:
    """``version`` if it is in force on ``day``; else ``TaxCodeExpired``."""
    if version.is_active_on(day):
        return version
    raise TaxCodeExpired(
        _(
            "%(code)s (%(name)s) is in force %(range)s, not on %(date)s: pick the code again for "
            "this date."
        ),
        code="tax.code.expired",
        params={
            "code": version.code,
            "name": version.name,
            "range": _range(version),
            "date": day.isoformat(),
        },
    )


def code_for(key: str, side: str, day: dt.date, organisation: Any = None) -> TaxCode:
    """The version of ``key`` in force on ``day`` (module docstring)."""
    organisation = _organisation(organisation)
    ensure_tax_table(organisation)
    with org_context(organisation):
        versions: list[TaxCode] = list(
            TaxCode.objects.filter(code=key, side=side).order_by("version")
        )
    if not versions:
        raise TaxCodeUnknown(
            _("There's no %(side)s tax code %(code)s."),
            code="tax.code.unknown",
            params={"side": side, "code": key},
        )
    for version in versions:
        if version.is_active_on(day):
            if version.archived_at is not None:
                raise TaxCodeExpired(
                    _("%(code)s is archived: restore it or pick another code."),
                    code="tax.code.archived",
                    params={"code": key},
                )
            return version
    return check_code(versions[-1], day)
