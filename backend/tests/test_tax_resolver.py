"""G-01-T08 — effective-date resolver: only codes in force are offered; expired codes are refused.

Acceptance: MB RST 8 % is not offered and is rejected on a 2026 document (TaxCodeExpired), but is
offered in 2018; NS switches from 15 % to 14 % on 1 Apr 2025; sales pickers never return purchase
codes; archived codes are hidden; an unknown code is named.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from numo9.ledger.template import load_template
from numo9.tax.models import TaxCode
from numo9.tax.resolver import TaxCodeExpired, TaxCodeUnknown, check_code, code_for, codes_available
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
D = dt.date


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Prairie Goods Ltd.")
    load_template(organisation, "MB")
    return organisation


def _rates(version: TaxCode) -> list[Decimal]:
    return [p.component.rate for p in version.components.order_by("position")]


def test_mb_rst_8_not_offered_and_rejected_in_2026(org: Organisation) -> None:
    with org_context(org):
        offered = codes_available("sales", D(2026, 6, 15))
        mb = [c for c in offered if c.code == "sales.MB.standard"]
        assert len(mb) == 1 and _rates(mb[0]) == [Decimal("5.0000"), Decimal("7.0000")]
        old = TaxCode.objects.get(code="sales.MB.standard", version=1)
        assert old not in offered
        with pytest.raises(TaxCodeExpired) as caught:
            check_code(old, D(2026, 6, 15))
        assert caught.value.code == "tax.code.expired"
        assert "2013-07-01 – 2019-06-30" in caught.value.messages[0]
        in_2018 = codes_available("sales", D(2018, 3, 1))
        assert old in in_2018
        assert code_for("sales.MB.standard", "sales", D(2018, 3, 1)) == old


def test_ns_rate_change_day(org: Organisation) -> None:
    with org_context(org):
        before = code_for("sales.NS.standard", "sales", D(2025, 3, 31))
        after = code_for("sales.NS.standard", "sales", D(2025, 4, 1))
        assert (_rates(before), _rates(after)) == ([Decimal("15.0000")], [Decimal("14.0000")])


def test_sides_never_mix_and_archived_hidden(org: Organisation) -> None:
    with org_context(org):
        sales = codes_available("sales", D(2026, 1, 1))
        assert sales and all(c.side == "sales" for c in sales)
        assert all(c.code.startswith("sales.") for c in sales)
        exempt = TaxCode.objects.get(code="sales.exempt")
        exempt.archived_at = timezone.now()
        exempt.save()
        assert exempt not in codes_available("sales", D(2026, 1, 1))
        with pytest.raises(TaxCodeExpired):
            code_for("sales.exempt", "sales", D(2026, 1, 1))


def test_unknown_and_not_yet_in_force(org: Organisation) -> None:
    with org_context(org):
        with pytest.raises(TaxCodeUnknown) as caught:
            code_for("sales.ON.standard", "purchase", D(2026, 1, 1))
        assert caught.value.code == "tax.code.unknown"
        with pytest.raises(TaxCodeExpired):
            code_for("sales.SK.standard", "sales", D(2016, 1, 1))  # before 6 % PST


def test_installed_on_first_use() -> None:
    bare = Organisation.objects.create(name="No chart")
    assert codes_available("purchase", D(2026, 1, 1), organisation=bare).count() > 0
