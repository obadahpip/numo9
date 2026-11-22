"""G-01-T10 — versioning: editing a code's components creates a new version from a date; the
old version is closed the day before and never changes.

Acceptance: a line that stored the old version recalculates unchanged after the edit; the new
version applies from its date; a version's components can't be edited or removed in place; a
revision date outside the version in force is refused.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.ledger.template import load_template
from numo9.tax.calculator import calculate
from numo9.tax.codes import revise_code
from numo9.tax.models import TaxCode, TaxError
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.tax_helpers import component

pytestmark = pytest.mark.django_db
D = dt.date
P = Decimal


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


def test_old_documents_recalculate_unchanged(org: Organisation) -> None:
    with org_context(org):
        v1 = code_for("purchase.ON.standard", "purchase", D(2026, 6, 15))
        stored = v1.pk  # what a posted line keeps
        before = calculate(v1, P("100.00"))
        surtax = component(
            org, "hst_on_2027", "14", D(2027, 1, 1), kind="hst", name="HST (ON) 14 %"
        )
        v2 = revise_code(
            v1, effective_from=D(2027, 1, 1), components=[surtax], name="HST 14 % (ON) on purchases"
        )
        old = TaxCode.objects.get(pk=stored)
        assert (old.version, old.effective_to, v2.version, v2.effective_from) == (
            1,
            D(2026, 12, 31),
            2,
            D(2027, 1, 1),
        )
        after = calculate(old, P("100.00"))
        assert (after.tax, [c.key for c in after.components]) == (before.tax, ["hst_on"])
        assert calculate(v2, P("100.00")).tax == P("14.00")
        assert code_for("purchase.ON.standard", "purchase", D(2026, 12, 31)) == old
        assert code_for("purchase.ON.standard", "purchase", D(2027, 1, 1)) == v2
        assert v2.name == "HST 14 % (ON) on purchases"


def test_components_locked_in_place(org: Organisation) -> None:
    with org_context(org):
        link = TaxCode.objects.get(code="sales.ON.standard").components.get()
        link.recoverable_pct = P("10")
        with pytest.raises(TaxError) as caught:
            link.save()
        assert caught.value.code == "tax.code.component_locked"
        with pytest.raises(TaxError):
            link.delete()


def test_revision_date_must_be_inside_the_version_in_force(org: Organisation) -> None:
    with org_context(org):
        current = TaxCode.objects.get(code="sales.ON.standard")
        hst = current.components.get().component
        with pytest.raises(TaxError) as caught:
            revise_code(current, effective_from=current.effective_from, components=[hst])
        assert caught.value.code == "tax.code.revision_date"
        with pytest.raises(TaxError):
            revise_code(current, effective_from=D(2005, 1, 1), components=[hst])
