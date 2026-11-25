"""E-07-T03 — the chart template has the early-payment discount accounts: 4020 Sales discounts
given (contra revenue, GIFI 8000) and 5050 Purchase discounts received (contra purchases, GIFI
8320), both system accounts; a chart loaded before them gets them when first needed."""

from __future__ import annotations

import pytest

from numo9.ledger.models import Account, SystemRole
from numo9.ledger.template import (
    discount_account,
    get_template,
    load_template,
    unmapped_gifi_count,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("province", ["ON", "QC", "BC", "AB"])
def test_every_chart_has_both_discount_accounts(province: str) -> None:
    org = Organisation.objects.create(name=f"{province} Ltd.")
    with org_context(org):
        load_template(org, province)
        sales = Account.objects.get(system_role=SystemRole.SALES_DISCOUNTS)
        purchases = Account.objects.get(system_role=SystemRole.PURCHASE_DISCOUNTS)
        assert (sales.code, sales.type, sales.subtype) == ("4020", "revenue", "revenue")
        assert (purchases.code, purchases.type, purchases.subtype) == (
            "5050",
            "expense",
            "cost_of_sales",
        )
        assert sales.gifi is not None and sales.gifi.code == "8000"
        assert purchases.gifi is not None and purchases.gifi.code == "8320"
        assert sales.default_tax_key == purchases.default_tax_key == ""
        assert unmapped_gifi_count(org) == 0
        assert discount_account(org, "sales") == sales
        assert discount_account(org, "purchase") == purchases


def test_a_chart_without_them_gets_them_when_needed() -> None:
    """A chart from before the template had them (here: built by hand) gets the account."""
    from tests.ledger_helpers import account

    org = Organisation.objects.create(name="Old Chart Ltd.")
    with org_context(org):
        account(org, "4000", "Sales", subtype="revenue")
        assert not Account.objects.filter(system_role="purchase_discounts").exists()
        made = discount_account(org, "purchase")
    assert made.system_role == "purchase_discounts" and made.code == "5050"
    assert get_template().row_for_role("sales_discounts") is not None
