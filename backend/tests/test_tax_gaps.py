"""G-01-T17 — gap tests for the tax engine (xero_teardown §2.3, §6.9).

- gap-07: the sales tax picker (API) never offers purchase codes, and the reverse.
- gap-08: an expired rate isn't offered on a later date and is refused there; effective dates.
- gap-45: expense accounts default to the province rate (not Exempt); zero-rated ≠ exempt ≠ out
  of scope; partial ITC (50 % meals) posts half to the expense.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.test import Client

from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.orgsettings.service import get_settings
from numo9.tax.calculator import calculate
from numo9.tax.defaults import default_code
from numo9.tax.models import TaxCode
from numo9.tax.posting import map_tax
from numo9.tax.resolver import TaxCodeExpired, check_code
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db
DAY = dt.date(2026, 6, 15)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(organisation):
        settings = get_settings(organisation)
        settings.physical_province = "ON"
        settings.save()
    load_template(organisation, "ON")
    return organisation


def _client(org: Organisation) -> Client:
    client = Client()
    client.force_login(people(org)["owner"])
    return client


@pytest.mark.gap("gap-07")
def test_gap_07_pickers_filtered_by_side(org: Organisation) -> None:
    client = _client(org)
    for side in ("sales", "purchase"):
        rows = client.get(f"/api/v1/o/{org.public_id}/tax/codes?side={side}&date=2026-06-15").json()
        assert rows["results"] and {r["side"] for r in rows["results"]} == {side}


@pytest.mark.gap("gap-08")
def test_gap_08_expired_rates_hidden_and_refused(org: Organisation) -> None:
    client = _client(org)
    rows = client.get(f"/api/v1/o/{org.public_id}/tax/codes?side=sales&date=2026-06-15").json()
    names = {r["name"] for r in rows["results"]}
    assert "GST 5 % + RST 8 % (Manitoba) on sales" not in names
    assert "HST 15 % (Nova Scotia) on sales" not in names
    with org_context(org):
        old = TaxCode.objects.get(code="sales.MB.standard", version=1)
        with pytest.raises(TaxCodeExpired):
            check_code(old, DAY)
        assert check_code(old, dt.date(2018, 1, 1)) == old


@pytest.mark.gap("gap-45")
def test_gap_45_defaults_types_and_partial_itc(org: Organisation) -> None:
    with org_context(org):
        office = Account.objects.get(code="6080")
        found = default_code(office, "purchase", DAY)
        assert found is not None and found.type == "taxable" and found.province == "ON"
        types = set(TaxCode.objects.filter(side="sales").values_list("type", flat=True))
        assert {"taxable", "zero_rated", "exempt", "out_of_scope"} <= types
        meals = Account.objects.get(code="6010")
        tax = calculate(default_code(meals, "purchase", DAY), Decimal("100.00"), account=meals)
        mapped = map_tax(tax)
        assert (mapped.to_line, [p.amount for p in mapped.postings]) == (
            Decimal("6.50"),
            [Decimal("6.50")],
        )
