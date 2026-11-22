"""G-01-T03 — tax codes and their components.

Acceptance: a sales code with a purchase-only component is rejected; codes keep name, code, side,
type, province and active range; versions of a code don't overlap; zero-rated codes hold only
0 % components, exempt / out-of-scope codes none, a taxable code at least one; a component must
be in force over the whole version; the recoverable % falls back to the component's rule.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.tax.codes import define_code
from numo9.tax.models import TaxCode, TaxCodeComponent, TaxError
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.tax_helpers import component

pytestmark = pytest.mark.django_db
D = dt.date


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def test_sales_code_with_purchase_only_component_rejected(org: Organisation) -> None:
    with org_context(org):
        recovery = component(org, "qst_itr", "9.975", D(2013, 1, 1), side="purchase", kind="qst")
        with pytest.raises(TaxError) as caught:
            define_code(
                org,
                code="sales.QC.bad",
                name="Bad",
                side="sales",
                type="taxable",
                effective_from=D(2026, 1, 1),
                components=[recovery],
            )
        assert caught.value.code == "tax.code.component_side"
        assert not TaxCode.objects.exists()  # all or nothing
        made = define_code(
            org,
            code="purchase.QC.ok",
            name="QST on purchases",
            side="purchase",
            type="taxable",
            effective_from=D(2026, 1, 1),
            components=[recovery],
        )
        assert made.components.get().component == recovery


def test_code_fields_versions_and_overlap(org: Organisation) -> None:
    with org_context(org):
        hst15 = component(org, "hst_ns", "15", D(2010, 7, 1), D(2025, 3, 31))
        hst14 = component(org, "hst_ns", "14", D(2025, 4, 1))
        v1 = define_code(
            org,
            code="sales.NS.standard",
            name="HST 15 % (Nova Scotia)",
            side="sales",
            type="taxable",
            province="ns",
            effective_from=D(2010, 7, 1),
            effective_to=D(2025, 3, 31),
            components=[hst15],
        )
        v2 = define_code(
            org,
            code="sales.NS.standard",
            name="HST 14 % (Nova Scotia)",
            side="sales",
            type="taxable",
            province="NS",
            effective_from=D(2025, 4, 1),
            components=[hst14],
        )
        assert (v1.version, v2.version, v1.province) == (1, 2, "NS")
        assert v1.is_active_on(D(2025, 3, 31)) and not v1.is_active_on(D(2025, 4, 1))
        with pytest.raises(TaxError) as caught:
            define_code(
                org,
                code="sales.NS.standard",
                name="Clash",
                side="sales",
                type="taxable",
                effective_from=D(2026, 1, 1),
                components=[hst14],
            )
        assert caught.value.code == "tax.code.overlap"


@pytest.mark.parametrize(
    ("kind", "rate", "code"),
    [
        ("zero_rated", "5", "tax.code.zero_rate"),
        ("exempt", "0", "tax.code.components_not_allowed"),
        ("out_of_scope", "0", "tax.code.components_not_allowed"),
    ],
)
def test_type_rules(org: Organisation, kind: str, rate: str, code: str) -> None:
    with org_context(org):
        part = component(org, f"gst_{kind}", rate, D(1991, 1, 1), kind="gst")
        with pytest.raises(TaxError) as caught:
            define_code(
                org,
                code=f"sales.{kind}",
                name=kind,
                side="sales",
                type=kind,
                effective_from=D(2026, 1, 1),
                components=[part],
            )
        assert caught.value.code == code


def test_taxable_needs_a_component_and_exempt_needs_none(org: Organisation) -> None:
    with org_context(org):
        with pytest.raises(TaxError) as caught:
            define_code(
                org, code="x", name="x", side="sales", type="taxable", effective_from=D(2026, 1, 1)
            )
        assert caught.value.code == "tax.code.components_required"
        exempt = define_code(
            org,
            code="sales.exempt",
            name="Exempt",
            side="sales",
            type="exempt",
            effective_from=D(1991, 1, 1),
        )
        assert exempt.components.count() == 0


def test_component_must_cover_the_version(org: Organisation) -> None:
    with org_context(org):
        rst8 = component(org, "rst_mb", "8", D(2013, 7, 1), D(2019, 6, 30), kind="pst")
        with pytest.raises(TaxError) as caught:
            define_code(
                org,
                code="sales.MB.standard",
                name="GST + RST",
                side="sales",
                type="taxable",
                effective_from=D(2013, 7, 1),
                components=[rst8],  # open-ended version, component ends in 2019
            )
        assert caught.value.code == "tax.code.component_range"


def test_recoverable_pct_override_and_fallback(org: Organisation) -> None:
    with org_context(org):
        hst = component(org, "hst_on", "13", D(2010, 7, 1))
        pst = component(org, "pst_bc", "7", D(2013, 4, 1), recoverable=False, kind="pst")
        meals = define_code(
            org,
            code="purchase.ON.meals",
            name="HST meals",
            side="purchase",
            type="taxable",
            effective_from=D(2026, 1, 1),
            components=[(hst, Decimal("50"))],
        )
        bc = define_code(
            org,
            code="purchase.BC.standard",
            name="GST + PST",
            side="purchase",
            type="taxable",
            effective_from=D(2026, 1, 1),
            components=[pst],
        )
        assert meals.components.get().effective_recoverable_pct == Decimal("50")
        assert bc.components.get().effective_recoverable_pct == Decimal("0")
        assert TaxCodeComponent.objects.count() == 2
