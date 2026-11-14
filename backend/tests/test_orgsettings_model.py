"""A-05-T01 — the OrganisationSettings model.

Acceptance: the migration creates the table. Also: one settings row per organisation and CAD as
the only base currency, both enforced by the database; the defaults (31 December year end, CAD,
the organisation's time zone, 12-hour times, 30-day terms); a fiscal year end must be a real day;
day-of-month terms name a day from 1 to 31; display name and time zone are mirrored onto the
organisation; ``get_settings()`` creates the row once, from the organisation; every change is in
the audit log; rows are scoped to the active organisation.
"""

from __future__ import annotations

from collections.abc import Iterator
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction

from numo9.audit.models import AuditEvent
from numo9.orgsettings.models import (
    BASE_CURRENCY,
    BusinessStructure,
    OrganisationSettings,
    TermsType,
)
from numo9.orgsettings.service import get_settings
from numo9.tenancy.context import TenantContextMissing, org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.", time_zone="America/Vancouver")


@pytest.fixture
def other_org() -> Organisation:
    return Organisation.objects.create(name="Northern Lights Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def settings_for(org: Organisation, **fields: object) -> OrganisationSettings:
    item = OrganisationSettings(organisation=org, display_name=org.name, **fields)
    item.save()
    return item


# ---- acceptance: migration --------------------------------------------------------------------


def test_migration_creates_the_table() -> None:
    assert "orgsettings_organisationsettings" in connection.introspection.table_names()


def test_models_and_migrations_are_in_step() -> None:
    out = StringIO()
    call_command("makemigrations", "orgsettings", "--check", "--dry-run", stdout=out)
    assert "No changes detected" in out.getvalue()


# ---- defaults -----------------------------------------------------------------------------------


def test_defaults(org: Organisation) -> None:
    item = settings_for(org)
    item.refresh_from_db()
    assert (item.fye_month, item.fye_day) == (12, 31)
    assert item.base_currency == BASE_CURRENCY == "CAD"
    assert item.structure == BusinessStructure.CORPORATION
    assert item.time_format == "12h"
    assert (item.sales_terms_type, item.sales_terms_days) == (TermsType.DAYS_AFTER_DOCUMENT, 30)
    assert (item.purchase_terms_type, item.purchase_terms_days) == (
        TermsType.DAYS_AFTER_DOCUMENT,
        30,
    )
    assert item.mailing_country == item.physical_country == "CA"
    assert item.physical_same_as_mailing is True


# ---- database rules -----------------------------------------------------------------------------


def test_one_settings_row_per_organisation(org: Organisation) -> None:
    settings_for(org)
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganisationSettings.objects.bulk_create(
            [OrganisationSettings(organisation=org, display_name="Second")]
        )


def test_another_organisation_has_its_own_row(org: Organisation, other_org: Organisation) -> None:
    settings_for(org)
    with org_context(other_org):
        settings_for(other_org)
        assert OrganisationSettings.objects.count() == 1
    assert OrganisationSettings.objects.count() == 1


def test_base_currency_is_locked_to_cad(org: Organisation) -> None:
    item = settings_for(org)
    item.base_currency = "USD"
    item.save()  # the model puts CAD back
    item.refresh_from_db()
    assert item.base_currency == "CAD"
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganisationSettings.objects.filter(pk=item.pk).update(base_currency="USD")


def test_base_currency_is_not_editable() -> None:
    assert OrganisationSettings._meta.get_field("base_currency").editable is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fye_month", 13),
        ("fye_day", 32),
        ("structure", "llc"),
        ("time_format", "am"),
        ("sales_terms_days", 400),
    ],
)
def test_database_refuses_out_of_range_values(org: Organisation, field: str, value: object) -> None:
    item = settings_for(org)
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganisationSettings.objects.filter(pk=item.pk).update(**{field: value})


# ---- validation ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("month", "day"), [(2, 29), (4, 30), (6, 30), (12, 31), (3, 31)])
def test_fiscal_year_end_on_a_real_day(org: Organisation, month: int, day: int) -> None:
    item = settings_for(org, fye_month=month, fye_day=day)
    assert (item.fye_month, item.fye_day) == (month, day)


@pytest.mark.parametrize(("month", "day"), [(2, 30), (4, 31), (9, 31), (11, 31)])
def test_fiscal_year_end_on_a_day_the_month_lacks_is_refused(
    org: Organisation, month: int, day: int
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        settings_for(org, fye_month=month, fye_day=day)
    assert excinfo.value.error_dict["fye_day"][0].code == "orgsettings.fye_day_invalid"


def test_fiscal_year_end_month_out_of_range_is_refused(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        settings_for(org, fye_month=0)
    assert "fye_month" in excinfo.value.error_dict


def test_day_of_month_terms_need_a_day_from_1_to_31(org: Organisation) -> None:
    settings_for(org, sales_terms_type=TermsType.DAY_OF_FOLLOWING_MONTH, sales_terms_days=20)
    with pytest.raises(ValidationError) as excinfo:
        OrganisationSettings(
            organisation=org,
            display_name="x",
            purchase_terms_type=TermsType.DAY_OF_CURRENT_MONTH,
            purchase_terms_days=0,
        ).clean()
    assert excinfo.value.error_dict["purchase_terms_days"][0].code == (
        "orgsettings.terms_day_invalid"
    )


def test_days_after_terms_allow_zero_days(org: Organisation) -> None:
    item = settings_for(org, sales_terms_days=0)
    assert item.sales_terms_days == 0


def test_display_name_is_required(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        OrganisationSettings(organisation=org, display_name="  ").save()
    assert "display_name" in excinfo.value.error_dict


def test_time_zone_must_exist(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        settings_for(org, time_zone="Canada/Nowhere")
    assert "time_zone" in excinfo.value.error_dict


def test_invalid_email_and_website_are_refused(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        settings_for(org, email="not-an-email", website="not a url")
    assert {"email", "website"} <= set(excinfo.value.error_dict)


# ---- derived ------------------------------------------------------------------------------------


def test_printed_name_is_the_legal_name_else_the_display_name(org: Organisation) -> None:
    item = settings_for(org, legal_name="Maple Bakery Incorporated")
    assert item.printed_name == "Maple Bakery Incorporated"
    item.legal_name = ""
    assert item.printed_name == "Maple Bakery Inc."


def test_physical_address_follows_mailing_when_the_same(org: Organisation) -> None:
    item = settings_for(
        org,
        mailing_line1="100 King St W",
        mailing_city="Toronto",
        mailing_province="ON",
        mailing_postal_code="M5X 1A9",
        physical_line1="1 Factory Rd",
    )
    assert item.address("physical")["line1"] == "100 King St W"
    item.physical_same_as_mailing = False
    assert item.address("physical")["line1"] == "1 Factory Rd"
    with pytest.raises(ValueError):
        item.address("billing")


# ---- mirrored onto the organisation ------------------------------------------------------------


def test_display_name_and_time_zone_are_mirrored_onto_the_organisation(org: Organisation) -> None:
    item = settings_for(org)
    item.display_name = "Maple Bakery"
    item.time_zone = "America/Halifax"
    item.save()
    org.refresh_from_db()
    assert (org.name, org.time_zone) == ("Maple Bakery", "America/Halifax")


# ---- get_settings -------------------------------------------------------------------------------


def test_get_settings_creates_the_row_once_from_the_organisation(org: Organisation) -> None:
    first = get_settings()
    assert first.display_name == first.legal_name == "Maple Bakery Inc."
    assert first.time_zone == "America/Vancouver"
    assert get_settings().pk == first.pk == get_settings(org).pk
    assert OrganisationSettings.objects.count() == 1


def test_get_settings_does_not_take_a_number_as_legal_name() -> None:
    numbered = Organisation.objects.create(name="1001633222")
    with org_context(numbered):
        item = get_settings()
    assert item.display_name == "1001633222" and item.legal_name == ""


def test_get_settings_needs_an_organisation() -> None:
    with org_context(None), pytest.raises(TenantContextMissing):
        get_settings()


# ---- scoping and audit --------------------------------------------------------------------------


def test_rows_are_scoped_to_the_active_organisation(org: Organisation) -> None:
    settings_for(org)
    with org_context(None), pytest.raises(TenantContextMissing):
        OrganisationSettings.objects.count()


def test_every_change_is_audited(org: Organisation) -> None:
    item = settings_for(org)
    item.fye_month, item.fye_day = 6, 30
    item.save()
    events = list(
        AuditEvent.objects.filter(object_type="orgsettings.OrganisationSettings").order_by("id")
    )
    assert [e.action for e in events] == [
        "orgsettings.organisationsettings.created",
        "orgsettings.organisationsettings.updated",
    ]
    assert events[1].changes == {"fye_month": [12, 6], "fye_day": [31, 30]}
