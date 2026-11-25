"""G-03b-T06 — after a GST/HST stop, new sales lines default to out of scope (every default — the
place of supply, an item or contact code; never a line override), with the explanation
``tax.pos.registration_stopped``; configurable (tax setting ``out_of_scope_after_stop``); before
the stop, after a restart, and on purchases nothing changes."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.tax.place_of_supply import (
    REGISTRATION_STOPPED,
    Registration,
    SupplyAddress,
    SupplyContext,
    resolve,
)
from numo9.tax.settings import tax_settings
from numo9.tax.stop_restart import restart, stop
from numo9.tax.supply_context import build_context
from numo9.tenancy.context import org_context
from tests.stop_helpers import TODAY, quarterly

day = dt.date
STOPPED = Registration(
    "rt", "closed", day(2024, 1, 1), day(2026, 6, 30), ((day(2026, 7, 1), None),)
)
ON = SupplyAddress("CA", "ON")


def ctx(**over: Any) -> SupplyContext:
    fields: dict[str, Any] = {
        "side": "sales",
        "date": day(2026, 7, 15),
        "home_province": "ON",
        "registrations": (STOPPED,),
        "billing": ON,
    }
    fields.update(over)
    return SupplyContext(**fields)


def test_sales_after_the_stop_default_to_out_of_scope() -> None:
    found = resolve(ctx())
    assert (found.code, found.explanation) == ("sales.out_of_scope", REGISTRATION_STOPPED)
    assert found.params["date"] == "2026-06-30" and found.auto
    assert resolve(ctx(item_code="sales.ON.standard")).code == "sales.out_of_scope"


def test_kept_before_the_stop_for_overrides_purchases_and_when_off() -> None:
    assert resolve(ctx(date=day(2026, 6, 30))).code == "sales.ON.standard"
    assert resolve(ctx(line_override="sales.ON.standard")).code == "sales.ON.standard"
    assert resolve(ctx(side="purchase")).code == "purchase.ON.standard"
    assert resolve(ctx(out_of_scope_after_stop=False)).code == "sales.ON.standard"
    restarted = Registration(
        "rt", "active", day(2024, 1, 1), None, ((day(2026, 7, 1), day(2026, 12, 31)),)
    )
    assert resolve(ctx(registrations=(restarted,))).code == "sales.out_of_scope"
    assert (
        resolve(ctx(registrations=(restarted,), date=day(2027, 1, 2))).code == "sales.ON.standard"
    )


@pytest.mark.django_db
def test_wired_into_the_editor_context() -> None:
    reg, user = quarterly()
    org = reg.organisation
    stop(reg, day(2026, 6, 30), "deregistration", user=user, today=TODAY)
    with org_context(org):
        context = build_context("sales", day(2026, 7, 15), org)
        assert resolve(context).code == "sales.out_of_scope"
        row = tax_settings(org)
        row.out_of_scope_after_stop = False
        row.save()
        assert build_context("sales", day(2026, 7, 15), org).out_of_scope_after_stop is False
    restart(reg, day(2027, 1, 1), "quarterly", user=user, today=TODAY)
    with org_context(org):
        row.out_of_scope_after_stop = True
        row.save()
        assert resolve(build_context("sales", day(2026, 8, 1), org)).code == "sales.out_of_scope"
        later = resolve(build_context("sales", day(2027, 2, 1), org))
        assert later.code != "sales.out_of_scope"
