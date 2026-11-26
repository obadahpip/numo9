"""K-05-T04 — deadlines widget service from the G-03a filing periods, due soon / overdue.

Acceptance: the next due period is shown; ended unfiled periods are overdue after their return
due date and due soon in the 14 days before it (the nightly job's rule); filed periods never
appear; other providers (payroll later) merge in date order; an organisation without filing
registrations gets an empty answer with its message.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from freezegun import freeze_time

from numo9.dashboard.deadlines import (
    Deadline,
    deadlines,
    register_provider,
    unregister_provider,
)
from numo9.orgsettings.models import TaxRegistration
from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod, PeriodStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.filing_helpers import registration

pytestmark = pytest.mark.django_db
day = dt.date


@pytest.fixture
def quarterly() -> TaxRegistration:
    reg = registration()
    switch_frequency(reg, "quarterly", day(2026, 1, 1), today=day(2026, 2, 1))
    return reg


def summary(items: list[dict[str, object]]) -> list[tuple[object, ...]]:
    return [(i["period_start"], i["period_end"], i["due_date"], i["status"]) for i in items]


def test_overdue_due_soon_and_next_period(quarterly: TaxRegistration) -> None:
    answer = deadlines(quarterly.organisation, day(2026, 7, 20))
    assert summary(answer["items"]) == [
        ("2026-01-01", "2026-03-31", "2026-04-30", "overdue"),
        ("2026-04-01", "2026-06-30", "2026-07-31", "due_soon"),
        ("2026-07-01", "2026-09-30", "2026-11-02", "upcoming"),  # 31 Oct is a Saturday,
    ]
    assert (answer["overdue"], answer["due_soon"]) == (1, 1)
    first = answer["next"]
    assert first is not None and first["status"] == "overdue"
    assert first["days"] == -81
    assert first["label"] == "GST/HST 123456782 RT 0001" or str(first["label"]).startswith(
        "GST/HST"
    )
    assert str(first["href"]).endswith(f"/settings/tax/registrations/{quarterly.public_id}/filing")
    assert answer["as_of"] == "2026-07-20" and answer["empty_message"] == ""


def test_filed_periods_disappear_and_the_next_due_shows(quarterly: TaxRegistration) -> None:
    with org_context(quarterly.organisation):
        FilingPeriod.objects.filter(registration=quarterly, start=day(2026, 1, 1)).update(
            status=PeriodStatus.FILED
        )
    answer = deadlines(quarterly.organisation, day(2026, 7, 5))
    # 26 days before the Q2 return is due: not yet "due soon".
    assert summary(answer["items"]) == [
        ("2026-04-01", "2026-06-30", "2026-07-31", "upcoming"),
        ("2026-07-01", "2026-09-30", "2026-11-02", "upcoming"),  # 31 Oct is a Saturday,
    ]
    assert answer["next"] is not None and answer["next"]["due_date"] == "2026-07-31"
    assert (answer["overdue"], answer["due_soon"]) == (0, 0)


def test_due_soon_boundary_is_fourteen_days(quarterly: TaxRegistration) -> None:
    statuses = {
        today: deadlines(quarterly.organisation, today)["items"][1]["status"]
        for today in (day(2026, 7, 16), day(2026, 7, 17), day(2026, 7, 31), day(2026, 8, 1))
    }
    assert statuses == {
        day(2026, 7, 16): "upcoming",  # 15 days
        day(2026, 7, 17): "due_soon",  # 14 days
        day(2026, 7, 31): "due_soon",  # due today
        day(2026, 8, 1): "overdue",
    }


@freeze_time("2026-08-01T02:00:00Z")  # 31 Jul, 10 p.m. in Toronto: due today, not overdue yet
def test_today_is_the_organisations(quarterly: TaxRegistration) -> None:
    organisation = quarterly.organisation
    organisation.time_zone = "America/Toronto"
    organisation.save(update_fields=["time_zone"])
    answer = deadlines(organisation)
    assert answer["as_of"] == "2026-07-31"
    assert answer["items"][1]["status"] == "due_soon"


@pytest.fixture
def payroll() -> Iterator[None]:
    def provider(organisation: Organisation, today: dt.date) -> list[Deadline]:
        return [
            Deadline(
                kind="payroll_remittance",
                label="Payroll remittance",
                period_start=None,
                period_end=None,
                due_date=day(2026, 8, 15),
                payment_due_date=None,
                status="upcoming",
                href="/payroll",
            )
        ]

    register_provider("payroll-test", provider)
    yield
    unregister_provider("payroll-test")


def test_other_providers_merge_in_date_order(quarterly: TaxRegistration, payroll: None) -> None:
    answer = deadlines(quarterly.organisation, day(2026, 7, 20))
    assert [i["kind"] for i in answer["items"]] == [
        "gst_hst",
        "gst_hst",
        "payroll_remittance",
        "gst_hst",
    ]
    assert deadlines(quarterly.organisation, day(2026, 7, 20), limit=2)["items"][1]["due_date"] == (
        "2026-07-31"
    )


def test_no_registration_no_deadline() -> None:
    organisation = Organisation.objects.create(name="No Tax Yet Ltd.")
    answer = deadlines(organisation, day(2026, 7, 20))
    assert (answer["items"], answer["next"], answer["overdue"]) == ([], None, 0)
    assert answer["empty_message"] == "No tax or filing deadline is coming up."
