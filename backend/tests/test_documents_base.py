"""D-01-T01 — the abstract document header and line: a concrete test document migrates, saves,
is organisation-scoped and audited, and the shared constraints hold."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from numo9.audit.models import AuditEvent
from numo9.documents.models import DiscountType, DocumentBase, DocumentLineBase, TaxMode
from numo9.ledger.template import load_template
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


def test_bases_are_abstract() -> None:
    assert DocumentBase._meta.abstract and DocumentLineBase._meta.abstract


def test_concrete_document_saves_with_defaults(org: Organisation) -> None:
    with org_context(org):
        customer = contact(org, "Maple Café")
        doc = SampleDocument(organisation=org, contact=customer, date=D, number="T-1")
        doc.save()
        line = SampleDocumentLine(organisation=org, document=doc, description="Design work")
        line.save()
        doc.refresh_from_db()
        assert (doc.tax_mode, doc.currency, doc.discount_type, doc.version) == (
            TaxMode.EXCLUSIVE,
            "CAD",
            DiscountType.NONE,
            1,
        )
        assert doc.total == Decimal("0") and doc.due_date is None
        assert list(doc.lines.all()) == [line]
        assert (line.quantity, line.unit_price, line.tax_overridden) == (
            Decimal("1"),
            Decimal("0"),
            False,
        )
        assert AuditEvent.objects.filter(object_type__iendswith="sampledocument").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tax_mode", "sometimes"),
        ("discount_type", "half"),
        ("discount_value", Decimal("-1")),
    ],
)
def test_header_constraints(org: Organisation, field: str, value: object) -> None:
    with org_context(org):
        customer = contact(org, "Maple Café")
        doc = SampleDocument(organisation=org, contact=customer, date=D, **{field: value})
        with pytest.raises(IntegrityError), transaction.atomic():
            doc.save()


def test_percent_discount_at_most_100_and_due_date_not_before_date(org: Organisation) -> None:
    with org_context(org):
        customer = contact(org, "Maple Café")
        for fields in (
            {"discount_type": "percent", "discount_value": Decimal("100.01")},
            {"due_date": D - dt.timedelta(days=1)},
        ):
            doc = SampleDocument(organisation=org, contact=customer, date=D, **fields)
            with pytest.raises(IntegrityError), transaction.atomic():
                doc.save()
        SampleDocument(
            organisation=org,
            contact=customer,
            date=D,
            due_date=D,
            discount_type="amount",
            discount_value=Decimal("500"),
        ).save()


def test_line_constraints(org: Organisation) -> None:
    with org_context(org):
        customer = contact(org, "Maple Café")
        doc = SampleDocument(organisation=org, contact=customer, date=D)
        doc.save()
        line = SampleDocumentLine(
            organisation=org, document=doc, discount_type="percent", discount_value=Decimal("101")
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            line.save()


def test_documents_are_organisation_scoped(org: Organisation) -> None:
    other = Organisation.objects.create(name="Other Co.")
    with org_context(org):
        doc = SampleDocument(organisation=org, contact=contact(org, "Maple Café"), date=D)
        doc.save()
    with org_context(other):
        assert not SampleDocument.objects.filter(pk=doc.pk).exists()
