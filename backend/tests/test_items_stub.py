"""D-01-T02 — the item stub: code, name, accounts, tax keys, untracked; its defaults flow into a
document line, and its tax key is the item step of place-of-supply resolution."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.documents.lines import apply_item
from numo9.items.models import Item
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.tax.supply_context import resolve_line
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.testapp.models import SampleDocument, SampleDocumentLine

pytestmark = pytest.mark.django_db
D = dt.date(2026, 7, 15)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


def _item(org: Organisation, **fields: object) -> Item:
    with org_context(org):
        sales = Account.objects.filter(subtype="revenue").order_by("code").first()
        cost = Account.objects.filter(type="expense").order_by("code").first()
        values: dict[str, object] = {
            "code": "DESIGN",
            "name": "Design consultation",
            "sales_price": Decimal("125.0000"),
            "purchase_price": Decimal("60.0000"),
            "sales_account": sales,
            "purchase_account": cost,
        }
        values.update(fields)
        item = Item(organisation=org, **values)
        item.save()
        return item


def test_item_defaults_flow_into_a_line(org: Organisation) -> None:
    item = _item(org, description="Hourly design consultation")
    with org_context(org):
        doc = SampleDocument(organisation=org, contact=contact(org, "Maple Café"), date=D)
        doc.save()
        line = apply_item(SampleDocumentLine(organisation=org, document=doc), item, "sales")
        line.save()
        line.refresh_from_db()
        assert (line.item_id, line.description, line.unit_price, line.account_id) == (
            item.pk,
            "Hourly design consultation",
            Decimal("125.0000"),
            item.sales_account_id,
        )
        bill_line = apply_item(SampleDocumentLine(organisation=org), item, "purchase")
        assert (bill_line.unit_price, bill_line.account_id, bill_line.description) == (
            Decimal("60.0000"),
            item.purchase_account_id,
            "Hourly design consultation",
        )


def test_typed_values_are_kept_unless_replacing(org: Organisation) -> None:
    item = _item(org)
    line = SampleDocumentLine(organisation=org, description="Custom", unit_price=Decimal("99"))
    apply_item(line, item, "sales")
    assert (line.description, line.unit_price) == ("Custom", Decimal("99"))
    apply_item(line, item, "sales", replace=True)
    assert (line.description, line.unit_price) == ("Design consultation", Decimal("125.0000"))
    apply_item(line, None, "sales")
    assert line.item is None
    with pytest.raises(ValueError):
        apply_item(line, item, "other")


def test_item_tax_key_is_the_item_step_of_resolution(org: Organisation) -> None:
    groceries = _item(org, code="BREAD", name="Bread", sales_tax_key="sales.zero_rated")
    assert groceries.is_taxable is False
    resolution, version = resolve_line("sales", D, org, item=groceries)
    assert (resolution.code, resolution.source) == ("sales.zero_rated", "item")
    assert version is not None
    assert _item(org, code="SVC", name="Service").is_taxable is True


def test_item_rules(org: Organisation) -> None:
    _item(org)
    for fields in (
        {"code": "design"},  # case-insensitive duplicate
        {"code": "X1", "is_tracked": True},
        {"code": "X2", "sales_tax_key": "purchase.ON.standard"},
        {"code": "X3", "purchase_tax_key": "sales.ON.standard"},
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            _item(org, **fields)
    with org_context(org):
        Item.objects.filter(code="DESIGN").update(archived_at=timezone.now())
    _item(org)  # an archived item's code can be reused
