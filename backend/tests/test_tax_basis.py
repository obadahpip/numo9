"""G-06-T05 — tax basis change guard: a reason is required; a change during the fiscal year
warns (returns already filed keep their basis); the change is audited with the person, reason and
mid-year flag; reports use the organisation's basis by default and label it, or a per-report
override labelled as such ("Basis: Cash (organisation default)").
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.core.exceptions import ValidationError

from numo9.audit.models import AuditEvent
from numo9.orgsettings.fiscal import fiscal_year
from numo9.orgsettings.service import get_settings
from numo9.tax.settings import (
    basis_change_check,
    basis_label,
    change_basis,
    report_basis,
    tax_settings,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db
D = dt.date


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(organisation):
        settings = get_settings(organisation)
        settings.fye_month, settings.fye_day = 3, 31  # year end 31 March
        settings.save()
    return organisation


def test_fiscal_year() -> None:
    class S:
        fye_month, fye_day = 3, 31

    assert fiscal_year(S, D(2026, 6, 15)) == (D(2026, 4, 1), D(2027, 3, 31))
    assert fiscal_year(S, D(2026, 3, 31)) == (D(2025, 4, 1), D(2026, 3, 31))
    S.fye_month, S.fye_day = 2, 29
    assert fiscal_year(S, D(2026, 3, 1)) == (D(2026, 3, 1), D(2027, 2, 28))
    assert fiscal_year(S, D(2028, 2, 29)) == (D(2027, 3, 1), D(2028, 2, 29))


def test_reason_required(org: Organisation) -> None:
    owner = people(org)["owner"]
    with org_context(org), pytest.raises(ValidationError) as caught:
        change_basis(org, "cash", "too short", user=owner, today=D(2026, 6, 15))
    assert caught.value.error_dict["reason"][0].code == "tax.settings.basis_reason_required"
    with org_context(org):
        assert tax_settings(org).basis == "accrual"


def test_mid_year_warns_and_is_audited(org: Organisation) -> None:
    owner = people(org)["owner"]
    with org_context(org):
        check = basis_change_check(org, "cash", D(2026, 6, 15))
        assert check["mid_year"] is True and "2026-04-01" in check["warning"]
        assert basis_change_check(org, "cash", D(2026, 4, 1))["mid_year"] is False
        assert basis_change_check(org, "accrual", D(2026, 6, 15))["changes"] is False
        row = change_basis(
            org, "cash", "Switched on the accountant's advice", user=owner, today=D(2026, 6, 15)
        )
        assert row.basis == "cash"
        event = AuditEvent.objects.get(action="tax.taxsettings.basis_changed")
        assert event.actor_user_id == owner.pk
        assert event.changes == {"basis": ["accrual", "cash"]}
        assert event.meta["reason"] == "Switched on the accountant's advice"
        assert event.meta["mid_year"] is True


def test_reports_default_and_override_labels(org: Organisation) -> None:
    owner = people(org)["owner"]
    with org_context(org):
        change_basis(org, "cash", "Small business: cash basis", user=owner, today=D(2026, 4, 1))
        assert report_basis(org) == ("cash", True)
        assert basis_label(org) == "Basis: Cash (organisation default)"
        assert report_basis(org, "accrual") == ("accrual", False)
        assert basis_label(org, "accrual") == "Basis: Accrual (this report)"
        assert report_basis(org, "nonsense") == ("cash", True)
