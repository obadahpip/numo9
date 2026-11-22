"""G-01-T05 — partial recovery: itc_restriction_pct on the account and on the tax code; resolution
line › account › code › component override › 100 %.

Acceptance: the Meals account (50 %) resolves 50 % for an HST line; the line's own % wins; a code's
50 % applies on any account without its own %; PST is never claimable; the template gives the meals
account 50 % and the .itc50 codes 50 %.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.tax.models import TaxCode, TaxCodeComponent
from numo9.tax.recovery import claimable_pct
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
P = Decimal


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


def _link(code: str, position: int = 1) -> TaxCodeComponent:
    found = TaxCode.objects.filter(code=code).order_by("-version").first()
    assert found is not None
    link: TaxCodeComponent = found.components.get(position=position)
    return link


def test_meals_account_resolves_50_for_an_hst_line(org: Organisation) -> None:
    with org_context(org):
        meals = Account.objects.get(code="6010")
        office = Account.objects.get(code="6080")
        hst = _link("purchase.ON.standard")
        assert meals.itc_restriction_pct == P("50.00") and office.itc_restriction_pct is None
        assert claimable_pct(hst, account=meals) == P("50")
        assert claimable_pct(hst, account=office) == P("100")
        assert claimable_pct(hst, account=meals, line_pct=P("25")) == P("25")
        assert claimable_pct(hst, account=office, line_pct=P("0")) == P("0")


def test_code_level_restriction(org: Organisation) -> None:
    with org_context(org):
        itc50 = TaxCode.objects.get(code="purchase.ON.standard.itc50")
        assert itc50.itc_restriction_pct == P("50.00")
        link = itc50.components.get()
        assert link.recoverable_pct is None  # on the code, not on the component
        office = Account.objects.get(code="6080")
        assert claimable_pct(link, account=office) == P("50")
        office.itc_restriction_pct = P("80")
        assert claimable_pct(link, account=office) == P("80")  # account › code


def test_pst_never_claimable(org: Organisation) -> None:
    with org_context(org):
        meals = Account.objects.get(code="6010")
        gst, pst = _link("purchase.BC.standard", 1), _link("purchase.BC.standard", 2)
        assert claimable_pct(gst, account=meals) == P("50")
        assert claimable_pct(pst, account=meals, line_pct=P("100")) == P("0")


def test_component_override_is_the_last_fallback(org: Organisation) -> None:
    with org_context(org):
        link = _link("purchase.QC.standard", 2)  # QST
        link.recoverable_pct = P("75")
        assert claimable_pct(link) == P("75")
        link.tax_code.itc_restriction_pct = P("40")
        assert claimable_pct(link) == P("40")
