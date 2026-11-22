"""Place-of-supply resolver (G-02-T02): the decision table in docs/specs/tax-place-of-supply.md,
case by case. Pure function — no database."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.tax.place_of_supply import (
    MISSING_PROVINCE,
    PST_UNREGISTERED,
    SOURCE_ACCOUNT,
    SOURCE_CONTACT,
    SOURCE_ITEM,
    SOURCE_NONE,
    SOURCE_OVERRIDE,
    SOURCE_PLACE,
    Registration,
    SupplyAddress,
    SupplyContext,
    resolve,
)

DAY = dt.date(2026, 7, 15)
CA = SupplyAddress
US = SupplyAddress("US", "")
QST = Registration("qst", effective_from=dt.date(2020, 1, 1))
PST_BC = Registration("pst_bc")
PST_SK = Registration("pst_sk")
RST_MB = Registration("rst_mb")


def sale(
    province: str = "",
    *,
    regs: tuple[Registration, ...] = (),
    home: str = "ON",
    billing: SupplyAddress | None = None,
    **kw: Any,
) -> SupplyContext:
    if billing is None and province:
        billing = CA("CA", province)
    return SupplyContext(
        "sales", DAY, home_province=home, registrations=regs, billing=billing, **kw
    )


SALES_TABLE = [
    # province, registrations, code, explanation
    ("ON", (), "sales.ON.standard", "tax.pos.hst"),
    ("NS", (), "sales.NS.standard", "tax.pos.hst"),
    ("NB", (), "sales.NB.standard", "tax.pos.hst"),
    ("NL", (), "sales.NL.standard", "tax.pos.hst"),
    ("PE", (), "sales.PE.standard", "tax.pos.hst"),
    ("AB", (), "sales.AB.standard", "tax.pos.gst"),
    ("NT", (), "sales.NT.standard", "tax.pos.gst"),
    ("NU", (), "sales.NU.standard", "tax.pos.gst"),
    ("YT", (), "sales.YT.standard", "tax.pos.gst"),
    ("BC", (PST_BC,), "sales.BC.standard", "tax.pos.gst_pst"),
    ("BC", (), "sales.BC.gst", "tax.pos.gst_unregistered_pst"),
    ("SK", (PST_SK,), "sales.SK.standard", "tax.pos.gst_pst"),
    ("SK", (PST_BC,), "sales.SK.gst", "tax.pos.gst_unregistered_pst"),
    ("MB", (RST_MB,), "sales.MB.standard", "tax.pos.gst_pst"),
    ("MB", (), "sales.MB.gst", "tax.pos.gst_unregistered_pst"),
    ("QC", (QST,), "sales.QC.standard", "tax.pos.gst_qst"),
    ("QC", (), "sales.QC.gst", "tax.pos.gst_unregistered_qst"),
]


@pytest.mark.parametrize(("province", "regs", "code", "explanation"), SALES_TABLE)
def test_sales_decision_table(
    province: str, regs: tuple[Registration, ...], code: str, explanation: str
) -> None:
    result = resolve(sale(province, regs=regs))
    assert (result.code, result.explanation, result.source) == (code, explanation, SOURCE_PLACE)
    assert result.province == province and result.params == {"province": province}
    assert not result.flags and result.auto


def test_ontario_customer_gets_hst() -> None:
    assert resolve(sale("ON")).code == "sales.ON.standard"


def test_us_customer_is_zero_rated_export() -> None:
    result = resolve(sale(billing=US))
    assert (result.code, result.explanation, result.params) == (
        "sales.zero_rated",
        "tax.pos.export",
        {"country": "US"},
    )


def test_us_customer_with_canadian_ship_to_is_taxed_in_the_ship_to_province() -> None:
    result = resolve(sale(billing=US, ship_to=CA("CA", "ON")))
    assert result.code == "sales.ON.standard"


def test_ship_to_wins_over_billing() -> None:
    assert resolve(sale("AB", ship_to=CA("CA", "QC"), regs=(QST,))).code == "sales.QC.standard"


def test_ship_to_without_a_province_falls_back_to_billing() -> None:
    assert resolve(sale("AB", ship_to=CA("CA", ""))).code == "sales.AB.standard"


def test_missing_province_falls_back_to_the_home_province_with_a_flag() -> None:
    result = resolve(sale(home="AB"))
    assert result.code == "sales.AB.standard" and result.flags == {MISSING_PROVINCE}


def test_no_province_anywhere_uses_the_account_default_then_nothing() -> None:
    assert resolve(sale(home="", account_default="sales.exempt")).source == SOURCE_ACCOUNT
    result = resolve(sale(home=""))
    assert (result.code, result.source, result.flags) == (
        "",
        SOURCE_NONE,
        frozenset({MISSING_PROVINCE}),
    )


def test_registration_must_be_active_on_the_date() -> None:
    ended = Registration("qst", effective_to=dt.date(2026, 6, 30))
    pending = Registration("qst", status="pending")
    future = Registration("qst", effective_from=dt.date(2026, 8, 1))
    for reg in (ended, pending, future):
        assert resolve(sale("QC", regs=(reg,))).code == "sales.QC.gst"


@pytest.mark.parametrize(
    ("field", "value", "source"),
    [
        ("line_override", "sales.exempt", SOURCE_OVERRIDE),
        ("item_code", "sales.zero_rated", SOURCE_ITEM),
        ("contact_default", "sales.out_of_scope", SOURCE_CONTACT),
    ],
)
def test_precedence_above_the_resolver(field: str, value: str, source: str) -> None:
    overrides: dict[str, Any] = {field: value}
    result = resolve(sale("ON", **overrides))
    assert (result.code, result.source) == (value, source)


def test_precedence_order() -> None:
    context = sale(
        "ON",
        line_override="sales.exempt",
        item_code="sales.zero_rated",
        contact_default="sales.out_of_scope",
        account_default="sales.AB.standard",
    )
    assert resolve(context).source == SOURCE_OVERRIDE
    assert not resolve(context).auto
    context = sale("ON", item_code="sales.zero_rated", contact_default="sales.out_of_scope")
    assert resolve(context).source == SOURCE_ITEM
    # The resolver beats the account default on sales.
    assert resolve(sale("ON", account_default="sales.AB.standard")).code == "sales.ON.standard"


def test_codes_of_the_other_side_are_ignored() -> None:
    result = resolve(sale("ON", line_override="purchase.ON.standard", item_code="purchase.exempt"))
    assert (result.code, result.source) == ("sales.ON.standard", SOURCE_PLACE)


def purchase(
    province: str = "", *, home: str = "ON", billing: SupplyAddress | None = None, **kw: Any
) -> SupplyContext:
    if billing is None and province:
        billing = CA("CA", province)
    return SupplyContext("purchase", DAY, home_province=home, billing=billing, **kw)


def test_purchase_account_default_comes_before_the_supplier_province() -> None:
    result = resolve(purchase("BC", account_default="purchase.ON.standard.itc50"))
    assert (result.code, result.source) == ("purchase.ON.standard.itc50", SOURCE_ACCOUNT)


def test_purchase_from_the_supplier_province() -> None:
    result = resolve(purchase("ON"))
    assert (result.code, result.explanation) == (
        "purchase.ON.standard",
        "tax.pos.supplier_province",
    )


def test_purchase_from_abroad_is_out_of_scope() -> None:
    assert resolve(purchase(billing=US)).code == "purchase.out_of_scope"


def test_purchase_supplier_without_address_uses_home_province() -> None:
    result = resolve(purchase(home="MB"))
    assert result.code == "purchase.MB.standard" and result.flags == {MISSING_PROVINCE}


def test_purchase_ignores_provincial_registrations() -> None:
    assert resolve(purchase("BC", registrations=(PST_BC,))).code == "purchase.BC.standard"


def test_the_resolver_is_deterministic() -> None:
    context = sale("QC", regs=(QST,))
    assert resolve(context) == resolve(context)


def test_unknown_side_is_refused() -> None:
    with pytest.raises(ValueError):
        resolve(SupplyContext("other", DAY))


# ---- PST-registration warning (G-02-T04) -------------------------------------------------------


@pytest.mark.parametrize("province", ["BC", "SK", "MB"])
def test_taxable_sale_into_a_pst_province_unregistered_warns(province: str) -> None:
    result = resolve(sale(province))
    assert result.warnings == (PST_UNREGISTERED,)
    assert result.code == f"sales.{province}.gst"


@pytest.mark.parametrize(("province", "reg"), [("BC", PST_BC), ("SK", PST_SK), ("MB", RST_MB)])
def test_registered_for_the_provincial_tax_no_warning(province: str, reg: Registration) -> None:
    assert resolve(sale(province, regs=(reg,))).warnings == ()


@pytest.mark.parametrize("province", ["ON", "AB", "QC", "NS"])
def test_no_pst_warning_outside_pst_provinces(province: str) -> None:
    assert resolve(sale(province)).warnings == ()


def test_no_warning_for_exports_purchases_or_non_taxable_lines() -> None:
    assert resolve(sale(billing=US)).warnings == ()
    assert resolve(purchase("BC")).warnings == ()
    assert resolve(sale("BC", taxable=False)).warnings == ()


def test_warning_holds_with_an_override_and_via_ship_to() -> None:
    assert resolve(sale("BC", line_override="sales.exempt")).warnings == (PST_UNREGISTERED,)
    assert resolve(sale("ON", ship_to=CA("CA", "BC"))).warnings == (PST_UNREGISTERED,)
    assert resolve(sale(home="BC")).warnings == (PST_UNREGISTERED,)


def test_wrong_province_registration_does_not_count() -> None:
    assert resolve(sale("BC", regs=(PST_SK,))).warnings == (PST_UNREGISTERED,)
