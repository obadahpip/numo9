"""B-01-T05 — payment terms master per organisation, seeded with the defaults.

Acceptance: seed per new org. Also: the six defaults and their rules (Net 15/30/60, Due on
receipt, 2/10 net 30, EOM); seeding is idempotent and only for the new organisation; existing
organisations are seeded by the migration helper; names per language and unique per
organisation; day-of-month terms 1–31; discount window shorter than the term; ranges also held by
the database; archive keeps the term; people's changes are audited; scoping.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from numo9.audit.models import AuditEvent
from numo9.contacts.models import DEFAULT_TERMS, PaymentTerm, seed_payment_terms
from numo9.orgsettings.models import TermsType
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def term(org: Organisation, name: str, **fields: Any) -> PaymentTerm:
    item = PaymentTerm(organisation=org, name_i18n={"en-ca": name}, **fields)
    item.save()
    return item


def codes(excinfo: pytest.ExceptionInfo[ValidationError]) -> dict[str, list[str]]:
    return {f: [e.code or "" for e in errs] for f, errs in excinfo.value.error_dict.items()}


# ---- acceptance: seeded per new organisation ---------------------------------------------------


def test_a_new_organisation_gets_the_default_terms(org: Organisation) -> None:
    rows = list(
        PaymentTerm.objects.values_list(
            "code", "terms_type", "days", "discount_pct", "discount_days"
        )
    )
    assert rows == [
        ("due_on_receipt", TermsType.DAYS_AFTER_DOCUMENT, 0, Decimal("0.00"), 0),
        ("net_15", TermsType.DAYS_AFTER_DOCUMENT, 15, Decimal("0.00"), 0),
        ("net_30", TermsType.DAYS_AFTER_DOCUMENT, 30, Decimal("0.00"), 0),
        ("net_60", TermsType.DAYS_AFTER_DOCUMENT, 60, Decimal("0.00"), 0),
        ("2_10_net_30", TermsType.DAYS_AFTER_DOCUMENT, 30, Decimal("2.00"), 10),
        ("eom", TermsType.DAYS_AFTER_MONTH_END, 0, Decimal("0.00"), 0),
    ]
    assert [t.name for t in PaymentTerm.objects.all()] == [name for _, name, *_ in DEFAULT_TERMS]


def test_each_organisation_has_its_own_terms(org: Organisation) -> None:
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        assert PaymentTerm.objects.count() == len(DEFAULT_TERMS)
    assert PaymentTerm.objects.count() == len(DEFAULT_TERMS)
    assert PaymentTerm.objects.filter(organisation=other).count() == 0  # scoped


def test_seeding_is_idempotent_and_fills_what_is_missing(org: Organisation) -> None:
    assert seed_payment_terms(org) == 0
    PaymentTerm.objects.filter(code="net_60").delete()
    assert seed_payment_terms(org) == 1
    assert PaymentTerm.objects.filter(code="net_60").count() == 1


def test_the_migration_seeds_organisations_created_before_it(org: Organisation) -> None:
    from importlib import import_module

    from django.apps import apps

    migration = import_module("numo9.contacts.migrations.0005_payment_term")
    PaymentTerm.objects.all().delete()
    migration.seed_existing_organisations(apps, None)
    assert PaymentTerm.objects.count() == len(DEFAULT_TERMS)


def test_seeded_terms_are_not_audited_but_changes_are(org: Organisation) -> None:
    assert not AuditEvent.objects.filter(object_type="contacts.PaymentTerm").exists()
    net_30 = PaymentTerm.objects.get(code="net_30")
    net_30.late_interest_pct = Decimal("18")
    net_30.save()
    event = AuditEvent.objects.get(object_type="contacts.PaymentTerm")
    assert event.action == "contacts.paymentterm.updated"
    assert event.changes == {"late_interest_pct": ["0.000", "18"]}


# ---- rules -------------------------------------------------------------------------------------


def test_custom_terms_and_names_per_language(org: Organisation) -> None:
    from django.utils import translation

    item = term(
        org,
        "Net 45",
        days=45,
        late_interest_pct=Decimal("24"),
    )
    item.name_i18n = {"en-ca": "Net 45", "fr-ca": "Net 45 jours"}
    item.save()
    with translation.override("fr-ca"):
        assert item.name == "Net 45 jours"
    assert item.code == "" and not item.has_discount


def test_names_are_required_and_unique(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        term(org, "  ")
    assert codes(excinfo) == {"name_i18n": ["contacts.payment_term.name_required"]}
    with pytest.raises(ValidationError) as excinfo:
        term(org, "net 30")
    assert codes(excinfo) == {"name_i18n": ["contacts.payment_term.name_taken"]}


@pytest.mark.parametrize("day", [0, 32])
def test_day_of_month_terms_need_a_real_day(org: Organisation, day: int) -> None:
    with pytest.raises(ValidationError) as excinfo:
        term(org, "15th next month", terms_type=TermsType.DAY_OF_FOLLOWING_MONTH, days=day)
    assert codes(excinfo) == {"days": ["contacts.payment_term.day"]}
    assert term(org, "20th next month", terms_type=TermsType.DAY_OF_FOLLOWING_MONTH, days=20)


def test_terms_are_at_most_365_days(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        term(org, "Net 400", days=400)
    assert "days" in codes(excinfo)


def test_discount_rules(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        term(org, "1/30 net 30", days=30, discount_pct=Decimal("1"), discount_days=30)
    assert codes(excinfo) == {"discount_days": ["contacts.payment_term.discount_window"]}
    with pytest.raises(ValidationError) as excinfo:
        term(org, "1/? net 30", days=30, discount_pct=Decimal("1"))
    assert codes(excinfo) == {"discount_days": ["contacts.payment_term.discount_days_required"]}
    with pytest.raises(ValidationError) as excinfo:
        term(org, "100 off", days=30, discount_pct=Decimal("100"), discount_days=5)
    assert "discount_pct" in codes(excinfo)
    plain = term(org, "Net 20", days=20, discount_days=5)
    assert plain.discount_days == 0  # no discount, no window
    ok = term(org, "1/10 net 45", days=45, discount_pct=Decimal("1"), discount_days=10)
    assert ok.has_discount


def test_late_interest_range(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        term(org, "Usury", late_interest_pct=Decimal("120"))
    assert "late_interest_pct" in codes(excinfo)


def test_the_database_holds_the_ranges(org: Organisation) -> None:
    net_30 = PaymentTerm.objects.get(code="net_30")
    for change in ({"days": 400}, {"discount_pct": Decimal("150")}, {"terms_type": "weekly"}):
        with pytest.raises(IntegrityError), transaction.atomic():
            PaymentTerm.objects.filter(pk=net_30.pk).update(**change)
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentTerm.objects.bulk_create(
            [PaymentTerm(organisation=org, code="net_30", name_i18n={"en-ca": "Dup"})]
        )


def test_archive_keeps_the_term(org: Organisation) -> None:
    eom = PaymentTerm.objects.get(code="eom")
    eom.archive()
    eom.refresh_from_db()
    assert eom.status == "archived" and eom.deleted_at is None
    eom.unarchive()
    eom.refresh_from_db()
    assert eom.status == "active"
