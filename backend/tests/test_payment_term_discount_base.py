"""E-07-T01 — payment terms carry the early-payment discount: percent, days and base (document
total or amount before tax); 2/10 net 30 is seeded with every organisation."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from numo9.contacts.models import DiscountBase, PaymentTerm
from numo9.documents.due_dates import document_terms, resolve
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


def test_2_10_net_30_is_seeded(org: Organisation) -> None:
    with org_context(org):
        term = PaymentTerm.objects.get(code="2_10_net_30")
    assert (term.discount_pct, term.discount_days, term.days) == (Decimal("2.00"), 10, 30)
    assert term.discount_base == DiscountBase.TOTAL and term.has_discount
    dates = resolve(dt.date(2026, 11, 1), term)
    assert dates.discount_until == dt.date(2026, 11, 11) and dates.due == dt.date(2026, 12, 1)


def test_discount_base_pre_tax_and_documents_carry_it(org: Organisation) -> None:
    with org_context(org):
        term = PaymentTerm.objects.get(code="2_10_net_30")
        term.discount_base = DiscountBase.PRE_TAX
        term.full_clean()
        term.save()
        customer = contact(org, "Acme Ltd", roles=["customer"])
        customer.sales_payment_term = term
        customer.save()
        terms = document_terms("sales", customer, org)
    assert terms.discount_base == "pre_tax" and terms.discount_days == 10


def test_unknown_base_is_refused(org: Organisation) -> None:
    with org_context(org):
        term = PaymentTerm.objects.get(code="net_30")
        PaymentTerm.objects.filter(pk=term.pk).update(discount_base="pre_tax")
        with pytest.raises(IntegrityError), transaction.atomic():
            PaymentTerm.objects.filter(pk=term.pk).update(discount_base="net")
