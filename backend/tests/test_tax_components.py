"""G-01-T02 — tax authorities and effective-dated tax components.

Acceptance: the migration creates both tables (RLS on); a component keeps rate numeric(7,4),
effective range, recoverable flag and control accounts; overlapping effective ranges for the same
component are rejected (model check and database exclusion constraint); consecutive versions are
accepted; a range that ends before it starts is refused.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from numo9.tax.models import TaxComponent, TaxError
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account
from tests.tax_helpers import authority, component

pytestmark = pytest.mark.django_db
D = dt.date


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def test_component_fields(org: Organisation) -> None:
    with org_context(org):
        payable = account(org, "2100", "GST/HST payable", subtype="sales_tax_control")
        qst = component(
            org,
            "qst",
            "9.975",
            D(2013, 1, 1),
            authority=authority(org, "RQ", "Revenu Québec"),
            name="QST",
            control_account_sales=payable,
        )
        fresh = TaxComponent.objects.get(pk=qst.pk)
    assert fresh.rate == Decimal("9.9750") and fresh.authority.code == "RQ"
    assert fresh.recoverable and fresh.side == "both" and fresh.effective_to is None
    assert fresh.control_account_sales == payable and str(fresh) == "QST 9.975 %"
    assert fresh.is_active_on(D(2026, 1, 1)) and not fresh.is_active_on(D(2012, 12, 31))


def test_overlapping_versions_rejected(org: Organisation) -> None:
    with org_context(org):
        component(org, "hst_ns", "15", D(2010, 7, 1), D(2025, 3, 31))
        component(org, "hst_ns", "14", D(2025, 4, 1))  # consecutive: accepted
        with pytest.raises(TaxError) as caught:
            component(org, "hst_ns", "13", D(2025, 3, 31), D(2025, 4, 1))
        assert caught.value.code == "tax.component.overlap"
        with pytest.raises(TaxError):
            component(org, "hst_ns", "16", D(2030, 1, 1))  # inside the open-ended version
        assert TaxComponent.objects.filter(key="hst_ns").count() == 2


def test_database_refuses_overlap_too(org: Organisation) -> None:
    with org_context(org):
        first = component(org, "gst", "5", D(2008, 1, 1))
        clash = TaxComponent(
            organisation=org,
            authority=first.authority,
            key="gst",
            kind="gst",
            rate=Decimal("6"),
            effective_from=D(2020, 1, 1),
            name_i18n={"en-ca": "GST"},
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            # past the model check: the exclusion constraint is the last line of defence
            super(TaxComponent, clash).save()


def test_same_key_in_two_organisations_is_fine(org: Organisation) -> None:
    other = Organisation.objects.create(name="Other Ltd.")
    with org_context(org):
        component(org, "gst", "5", D(2008, 1, 1))
    with org_context(other):
        component(other, "gst", "5", D(2008, 1, 1))
        assert TaxComponent.objects.count() == 1


def test_range_must_not_end_before_it_starts(org: Organisation) -> None:
    with org_context(org), pytest.raises(TaxError) as caught:
        component(org, "pst_bc", "7", D(2020, 1, 1), D(2019, 1, 1))
    assert caught.value.code == "tax.component.range_invalid"
