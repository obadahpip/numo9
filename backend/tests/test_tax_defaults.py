"""G-01-T09 — default purchase code per expense account = the home-province purchase code.

Acceptance: a new ON organisation's expense accounts default to "HST 13 % (Ontario) on
purchases"; an expense account without a key gets the home-province code; the meals account its
50 % ITC variant; exempt accounts stay exempt; the helper re-keys the chart when the province
changes (QC → GST + QST on purchases); sales lines never get a purchase default.
"""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.orgsettings.service import get_settings
from numo9.tax.defaults import apply_province_defaults, default_code, home_province
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

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


def test_new_on_org_expense_accounts_default_to_hst_13(org: Organisation) -> None:
    with org_context(org):
        assert home_province(org) == "ON"
        expenses = Account.objects.filter(type="expense", default_tax_key__startswith="purchase.ON")
        assert expenses.count() >= 20
        for item in expenses.exclude(code="6010"):
            found = default_code(item, "purchase", DAY)
            assert found is not None and found.name == "HST 13 % (Ontario) on purchases", item
        meals = default_code(Account.objects.get(code="6010"), "purchase", DAY)
        assert meals is not None and meals.code == "purchase.ON.standard.itc50"
        bank_charges = default_code(Account.objects.get(code="6030"), "purchase", DAY)
        assert bank_charges is not None and bank_charges.type == "exempt"
        assert default_code(Account.objects.get(code="6080"), "sales", DAY) is None
        custom = account(org, "6999", "Studio props")  # no key
        assert default_code(custom, "purchase", DAY).code == "purchase.ON.standard"  # type: ignore[union-attr]


def test_province_change_rekeys_the_chart(org: Organisation) -> None:
    with org_context(org):
        custom = account(org, "6999", "Studio props")
    changed = apply_province_defaults(org, "QC")
    with org_context(org):
        assert changed > 20
        office = Account.objects.get(code="6080")
        assert office.default_tax_key == "purchase.QC.standard"
        assert Account.objects.get(code="6010").default_tax_key == "purchase.QC.standard.itc50"
        assert Account.objects.get(code="6030").default_tax_key == "purchase.exempt"
        assert Account.objects.get(code="4000").default_tax_key == "sales.QC.standard"
        custom.refresh_from_db()
        assert custom.default_tax_key == "purchase.QC.standard"
        found = default_code(office, "purchase", DAY)
        assert found is not None and [p.component.key for p in found.components.all()] == [
            "gst",
            "qst",
        ]
    assert apply_province_defaults(org, "QC") == 0
