"""G-02-T05 — registration-end awareness: a 15 Jul sale after a 30 Jun GST/HST stop defaults to
out of scope with the warning ``tax.pos.registration_stopped`` (also for a registration simply
ended and closed, with no stop event); an override that still charges HST keeps its code and
gets the warning; with the setting off the default stays and the warning remains."""

from __future__ import annotations

import datetime as dt

from numo9.tax.place_of_supply import (
    PST_UNREGISTERED,
    REGISTRATION_STOPPED,
    Registration,
    SupplyAddress,
    SupplyContext,
    resolve,
)

day = dt.date
STOPPED = Registration(
    "rt", "closed", day(2024, 1, 1), day(2026, 6, 30), ((day(2026, 7, 1), None),)
)
ENDED = Registration("rt", "closed", day(2024, 1, 1), day(2026, 6, 30))


def ctx(**over: object) -> SupplyContext:
    fields: dict[str, object] = {
        "side": "sales",
        "date": day(2026, 7, 15),
        "home_province": "ON",
        "registrations": (STOPPED,),
        "billing": SupplyAddress("CA", "ON"),
    }
    fields.update(over)
    return SupplyContext(**fields)  # type: ignore[arg-type]


def test_15_july_after_a_30_june_stop() -> None:
    for registration in (STOPPED, ENDED):
        found = resolve(ctx(registrations=(registration,)))
        assert found.code == "sales.out_of_scope"
        assert found.warnings == (REGISTRATION_STOPPED,)
        assert found.params["date"] == "2026-06-30"


def test_override_keeps_its_code_with_the_warning() -> None:
    found = resolve(ctx(line_override="sales.ON.standard"))
    assert (found.code, found.warnings) == ("sales.ON.standard", (REGISTRATION_STOPPED,))
    assert resolve(ctx(line_override="sales.out_of_scope")).warnings == ()


def test_setting_off_keeps_the_default_and_warns() -> None:
    found = resolve(ctx(out_of_scope_after_stop=False))
    assert (found.code, found.warnings) == ("sales.ON.standard", (REGISTRATION_STOPPED,))


def test_pst_warning_and_stop_warning_together() -> None:
    found = resolve(ctx(billing=SupplyAddress("CA", "BC"), line_override="sales.BC.gst"))
    assert found.warnings == (PST_UNREGISTERED, REGISTRATION_STOPPED)


def test_no_warning_while_registered_or_on_purchases() -> None:
    assert resolve(ctx(date=day(2026, 6, 30))).warnings == ()
    assert resolve(ctx(side="purchase")).warnings == ()
