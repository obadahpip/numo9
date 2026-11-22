"""G-01-T06 — TaxCalculator: exclusive / inclusive, per-component amounts, claimable vs cost,
residual cent; every 2026 provincial combination to the cent; property round trips.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db.models import Q
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.tax.calculator import calculate, cents
from numo9.tax.models import TaxCode
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
P = Decimal
DAY = dt.date(2026, 6, 15)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Tax matrix Inc.")
    load_template(organisation, "ON")
    return organisation


def code(side: str, prov: str) -> TaxCode:
    """The province's standard code version in force on 15 Jun 2026."""
    found: TaxCode = (
        TaxCode.objects.filter(code=f"{side}.{prov}.standard", effective_from__lte=DAY)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=DAY))
        .get()
    )
    return found


#: 100.00 before tax in 2026: per-component tax and the gross.
EXCLUSIVE_100 = {
    "AB": (["5.00"], "105.00"),
    "BC": (["5.00", "7.00"], "112.00"),
    "MB": (["5.00", "7.00"], "112.00"),
    "NB": (["15.00"], "115.00"),
    "NL": (["15.00"], "115.00"),
    "NS": (["14.00"], "114.00"),
    "NT": (["5.00"], "105.00"),
    "NU": (["5.00"], "105.00"),
    "ON": (["13.00"], "113.00"),
    "PE": (["15.00"], "115.00"),
    "QC": (["5.00", "9.98"], "114.98"),
    "SK": (["5.00", "6.00"], "111.00"),
    "YT": (["5.00"], "105.00"),
}

#: 100.00 including tax in 2026: the net and per-component tax.
INCLUSIVE_100 = {
    "AB": ("95.24", ["4.76"]),
    "BC": ("89.29", ["4.46", "6.25"]),
    "MB": ("89.29", ["4.46", "6.25"]),
    "NB": ("86.96", ["13.04"]),
    "NL": ("86.96", ["13.04"]),
    "NS": ("87.72", ["12.28"]),
    "NT": ("95.24", ["4.76"]),
    "NU": ("95.24", ["4.76"]),
    "ON": ("88.50", ["11.50"]),
    "PE": ("86.96", ["13.04"]),
    "QC": ("86.97", ["4.35", "8.68"]),
    "SK": ("90.09", ["4.50", "5.41"]),
    "YT": ("95.24", ["4.76"]),
}


@pytest.mark.parametrize("prov", sorted(EXCLUSIVE_100))
@pytest.mark.parametrize("side", ["sales", "purchase"])
def test_every_province_exclusive_and_inclusive(org: Organisation, prov: str, side: str) -> None:
    with org_context(org):
        tax_code = code(side, prov)
        out = calculate(tax_code, P("100.00"))
        assert [f"{c.amount:.2f}" for c in out.components] == EXCLUSIVE_100[prov][0]
        assert f"{out.gross:.2f}" == EXCLUSIVE_100[prov][1]
        back = calculate(tax_code, P("100.00"), inclusive=True)
        net, taxes = INCLUSIVE_100[prov]
        assert (f"{back.net:.2f}", [f"{c.amount:.2f}" for c in back.components]) == (net, taxes)
        assert back.gross == P("100.00")


def test_purchase_split_claimable_and_cost(org: Organisation) -> None:
    with org_context(org):
        bc = calculate(code("purchase", "BC"), P("100.00"))
        assert [(c.key, c.claimable, c.cost) for c in bc.components] == [
            ("gst", P("5.00"), P("0.00")),
            ("pst_bc", P("0.00"), P("7.00")),
        ]
        assert (bc.claimable, bc.cost) == (P("5.00"), P("7.00"))
        qc = calculate(code("purchase", "QC"), P("100.00"))
        assert (qc.claimable, qc.cost) == (P("14.98"), P("0.00"))  # GST ITC + QST ITR
        sales = calculate(code("sales", "BC"), P("100.00"))
        assert (sales.claimable, sales.cost) == (P("0.00"), P("0.00"))


def test_edge_cases(org: Organisation) -> None:
    with org_context(org):
        on = code("purchase", "ON")
        meals = Account.objects.get(code="6010")
        half = calculate(on, P("10.01"), account=meals)  # 50 % ITC on HST 13 % of 10.01
        assert (half.tax, half.claimable, half.cost) == (P("1.30"), P("0.65"), P("0.65"))
        tiny = calculate(on, P("0.01"), inclusive=True)
        assert (tiny.net, tiny.tax) == (P("0.01"), P("0.00"))
        assert calculate(None, P("12.34")).gross == P("12.34")
        exempt = TaxCode.objects.get(code="sales.exempt")
        assert calculate(exempt, P("50"), inclusive=True).tax == P("0.00")
        refund = calculate(on, P("-113.00"), inclusive=True)
        assert (refund.net, refund.tax) == (P("-100.00"), P("-13.00"))


def test_rate_change_day_uses_the_version_given(org: Organisation) -> None:
    with org_context(org):
        old, new = TaxCode.objects.filter(code="sales.NS.standard").order_by("version")
        assert calculate(old, P("100")).tax == P("15.00")
        assert calculate(new, P("100")).tax == P("14.00")
        assert new.is_active_on(dt.date(2025, 4, 1)) and not old.is_active_on(dt.date(2025, 4, 1))


money = st.decimals(min_value=P("0.01"), max_value=P("999999.99"), places=2)


@settings(
    max_examples=200, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(amount=money, prov=st.sampled_from(sorted(EXCLUSIVE_100)))
def test_property_round_trips(org: Organisation, amount: Decimal, prov: str) -> None:
    with org_context(org):
        tax_code = code("purchase", prov)
        links = list(tax_code.components.select_related("component", "tax_code"))
        forward = calculate(tax_code, amount, links=links)
        # excl → incl → excl: the inclusive net is the original net
        assert calculate(tax_code, forward.gross, inclusive=True, links=links).net == amount
        # incl → excl → incl: net + tax is always the gross; exclusive from the net agrees
        backward = calculate(tax_code, amount, inclusive=True, links=links)
        assert backward.net + backward.tax == amount
        again = calculate(tax_code, backward.net, links=links)
        assert abs(again.gross - amount) <= P("0.01")
        assert all(c.claimable + c.cost == c.amount for c in forward.components)
        assert cents(forward.net) == forward.net
