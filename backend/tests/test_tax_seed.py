"""G-01-T04 — the Canadian sales-tax table: 13 jurisdictions × 2 sides, historical rows,
zero-rated / exempt / out-of-scope codes, installed with the chart and idempotent.

Acceptance (fixture test): the seed loads; every province and territory has a sales and a purchase
code; NS HST 15 % ends 31 Mar 2025 and 14 % follows; MB RST 8 % ends 30 Jun 2019 and 7 % follows;
the zero-rated / exempt / out-of-scope codes exist on both sides; components post to the
organisation's control accounts (PST never recoverable); installing twice changes nothing.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.ledger.template import load_template
from numo9.tax.models import TaxAuthority, TaxCode, TaxComponent
from numo9.tax.seed import install_tax_table, link_control_accounts, load_tax_seed
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = [pytest.mark.django_db, pytest.mark.data_validation]
D = dt.date
JURISDICTIONS = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")  # installs the table through the chart hook
    return organisation


def test_13_jurisdictions_on_both_sides(org: Organisation) -> None:
    with org_context(org):
        for side in ("sales", "purchase"):
            provinces = set(
                TaxCode.objects.filter(side=side, code=f"{side}.ON.standard").values_list(
                    "province", flat=True
                )
            ) | set(
                TaxCode.objects.filter(side=side, code__endswith=".standard").values_list(
                    "province", flat=True
                )
            )
            assert provinces == JURISDICTIONS, side
            for kind in ("zero_rated", "exempt", "out_of_scope"):
                assert TaxCode.objects.filter(code=f"{side}.{kind}", type=kind).exists()
        assert set(TaxAuthority.objects.values_list("code", flat=True)) == {
            "CRA",
            "RQ",
            "BC",
            "MB",
            "SK",
        }


def test_historical_rows(org: Organisation) -> None:
    with org_context(org):
        ns = {
            (c.rate, c.effective_from, c.effective_to)
            for c in TaxComponent.objects.filter(key="hst_ns")
        }
        assert ns == {
            (Decimal("15.0000"), D(2010, 7, 1), D(2025, 3, 31)),
            (Decimal("14.0000"), D(2025, 4, 1), None),
        }
        mb = TaxCode.objects.filter(code="sales.MB.standard").order_by("version")
        assert [(c.effective_to, [p.component.rate for p in c.components.all()]) for c in mb] == [
            (D(2019, 6, 30), [Decimal("5.0000"), Decimal("8.0000")]),
            (None, [Decimal("5.0000"), Decimal("7.0000")]),
        ]
        qc = TaxCode.objects.get(code="purchase.QC.standard")
        assert [p.component.key for p in qc.components.all()] == ["gst", "qst"]


def test_control_accounts_and_recoverability(org: Organisation) -> None:
    with org_context(org):
        hst = TaxComponent.objects.get(key="hst_on")
        assert hst.control_account_sales.system_role == "gst_hst_payable"
        assert hst.control_account_purchase.system_role == "itc_receivable"
        pst = TaxComponent.objects.get(key="pst_bc")
        assert not pst.recoverable and pst.control_account_purchase is None
        meals = TaxCode.objects.get(code="purchase.ON.standard.itc50")
        assert meals.components.get().effective_recoverable_pct == Decimal("50")
        bc_meals = TaxCode.objects.get(code="purchase.BC.standard.itc50")
        assert [p.effective_recoverable_pct for p in bc_meals.components.all()] == [
            Decimal("50"),
            Decimal("0"),
        ]


def test_every_template_tax_key_has_a_code(org: Organisation) -> None:
    from numo9.ledger.models import Account

    with org_context(org):
        keys = set(
            Account.objects.exclude(default_tax_key="").values_list("default_tax_key", flat=True)
        )
        codes = set(TaxCode.objects.values_list("code", flat=True))
    assert keys and keys <= codes


def test_idempotent_and_linked_later() -> None:
    bare = Organisation.objects.create(name="No chart yet")
    assert install_tax_table(bare) is True
    assert install_tax_table(bare) is False
    with org_context(bare):
        assert TaxCode.objects.count() == len(load_tax_seed()["codes"])
        assert TaxComponent.objects.get(key="gst").control_account_sales is None
    load_template(bare, "QC")  # the chart arrives later: components get its accounts
    with org_context(bare):
        assert TaxComponent.objects.get(key="qst").control_account_sales is not None
    assert link_control_accounts(bare) == 0
