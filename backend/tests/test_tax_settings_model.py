"""G-06-T02 — TaxSettings: one row per organisation with the basis (accrual by default),
rounding mode, quick-method election (dated) and default codes per account type (validated
against this organisation's codes on the right side); every change audited.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from numo9.audit.models import AuditEvent
from numo9.tax.models import TaxSettings
from numo9.tax.seed import ensure_tax_table
from numo9.tax.settings import tax_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(organisation):
        ensure_tax_table(organisation)
    return organisation


def codes(error: ValidationError) -> set[str]:
    return {e.code for items in error.error_dict.values() for e in items if e.code}


def test_defaults_and_one_per_organisation(org: Organisation) -> None:
    with org_context(org):
        row = tax_settings(org)
        assert (row.basis, row.rounding_mode, row.quick_method, row.default_codes) == (
            "accrual",
            "line",
            False,
            {},
        )
        assert tax_settings(org).pk == row.pk
        with pytest.raises(IntegrityError), transaction.atomic():
            TaxSettings(organisation=org).save()


def test_default_codes_validated_and_read(org: Organisation) -> None:
    with org_context(org):
        row = tax_settings(org)
        row.default_codes = {
            "sales": {"revenue": "sales.ON.standard"},
            "purchase": {"expense": "purchase.ON.standard"},
        }
        row.full_clean()
        row.save()
        assert row.default_code("purchase", "expense") == "purchase.ON.standard"
        assert row.default_code("sales", "asset") == ""
        for bad, code in (
            ({"sales": {"revenue": "purchase.ON.standard"}}, "tax.code.unknown"),  # wrong side
            ({"sales": {"expense": "sales.ON.standard"}}, "tax.settings.default_codes_invalid"),
            ({"payroll": {}}, "tax.settings.default_codes_invalid"),
            ({"purchase": {"expense": "nope"}}, "tax.code.unknown"),
        ):
            row.default_codes = bad
            with pytest.raises(ValidationError) as caught:
                row.full_clean()
            assert code in codes(caught.value), bad


def test_quick_method_needs_a_date_and_changes_are_audited(org: Organisation) -> None:
    with org_context(org):
        row = tax_settings(org)
        row.quick_method = True
        with pytest.raises(ValidationError) as caught:
            row.full_clean()
        assert "tax.settings.quick_method_date" in codes(caught.value)
        row.quick_method_from = dt.date(2026, 1, 1)
        row.basis = "cash"
        row.full_clean()
        row.save()
        changes = [
            e.changes
            for e in AuditEvent.objects.filter(
                object_type="tax.TaxSettings", object_id=str(row.public_id)
            ).order_by("pk")
        ]
        assert changes[-1]["basis"] == ["accrual", "cash"]
        assert changes[-1]["quick_method"] == [False, True]


def test_invalid_choices_refused_by_the_database(org: Organisation) -> None:
    with org_context(org):
        row = tax_settings(org)
        with pytest.raises(IntegrityError), transaction.atomic():
            TaxSettings._base_manager.filter(pk=row.pk).update(basis="weekly")
