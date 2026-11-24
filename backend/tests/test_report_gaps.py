"""K-01-T19 — gap tests of the report engine (xero_teardown §6.10, §6.14, §9.1, §9.2):

- gap-46: reports filter by tracking — the figure and its drill-down count only the lines of the
  chosen options, through the API too;
- gap-49: one basis — the report's basis is the tax-settings basis with an explicit, labelled
  override per report; changing the tax setting changes the reports' default;
- gap-54: one engine — every report (financial and tax) is a definition in one registry, run,
  exported, drilled and laid out through the same API;
- gap-55: the header never prints a number as the legal name, an empty report says "No activity
  in this period" (never "–"), a period ending after today says "Year to date — unaudited".
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.services import post_journal
from numo9.orgsettings.validators import validate_organisation_legal_name
from numo9.reports.aggregation import period_movements
from numo9.reports.drill import drill
from numo9.reports.engine import Column, ReportDefinition, ReportRow, register, registry
from numo9.reports.exports import render_csv, render_pdf
from numo9.reports.header import header_for, report_header
from numo9.reports.parameters import DateRange
from numo9.tax.settings import tax_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.journal_helpers import pay
from tests.report_helpers import report_books
from tests.test_report_exports import pdf_text

pytestmark = pytest.mark.django_db
D = dt.date
JUNE = DateRange(D(2026, 6, 1), D(2026, 6, 30))


@pytest.fixture
def books() -> dict[str, Any]:
    books = report_books()
    with org_context(books["org"]):
        for amount, region in (("300.00", "east"), ("200.00", "west")):
            post_journal(
                pay(
                    books["office"],
                    books["chequing"],
                    amount,
                    D(2026, 6, 25),
                    tracking={"region": region},
                ),
                user=None,
            )
    owner = User.objects.create_user("owner@refined.ca", name="Owner")
    OrganisationMember.objects.create(organisation=books["org"], user=owner, role="owner")
    client = Client()
    client.force_login(owner)
    return {**books, "client": client, "base": f"/api/v1/o/{books['org'].public_id}/reports"}


@pytest.mark.gap("gap-46")
def test_tracking_filter_counts_only_the_chosen_options(books: dict[str, Any]) -> None:
    office = books["office"]
    with org_context(books["org"]):
        every = period_movements([JUNE], accounts=[office.pk])[office.pk][0]
        east = period_movements([JUNE], tracking={"region": ["east"]}, accounts=[office.pk])
    assert every == Decimal("650.00")  # 150 untagged + 300 east + 200 west
    assert east[office.pk] == [Decimal("300.00")]
    lines = drill(
        books["org"],
        account="6100",
        date_from=JUNE.start,
        date_to=JUNE.end,
        tracking={"region": ["east"]},
    )
    assert (lines.total, lines.count) == (Decimal("300.00"), 1)
    answer = books["client"].get(
        f"{books['base']}/account-activity/drill",
        {"account": "6100", "from": "2026-06-01", "to": "2026-06-30", "tracking": "region:west"},
    )
    assert (answer.json()["total"], answer.json()["count"]) == ("200.00", 1)


@pytest.mark.gap("gap-49")
def test_one_basis_from_tax_settings_with_a_labelled_override(books: dict[str, Any]) -> None:
    org = books["org"]
    header = report_header(org, title="P&L", today=D(2026, 8, 1), period=JUNE)
    assert header.basis_label == "Basis: Accrual (organisation default)"
    with org_context(org):
        settings = tax_settings(org)
        settings.basis = "cash"
        settings.save()
    header = report_header(org, title="P&L", today=D(2026, 8, 1), period=JUNE)
    assert header.basis_label == "Basis: Cash (organisation default)"
    override = report_header(org, title="P&L", today=D(2026, 8, 1), period=JUNE, basis="accrual")
    assert override.basis_label == "Basis: Accrual (this report)"
    run = books["client"].get(
        f"{books['base']}/account-activity/run",
        {"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert run.json()["header"]["basis_label"] == "Basis: Cash (organisation default)"


class TaxSummarySample(ReportDefinition):
    id = "gap54_tax_summary"
    slug = "gap54-tax-summary"
    name = "Sales tax summary"
    category = "tax"
    feature = "tax.reports.read"

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [Column("amount", "Amount")]

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        return None

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        return [ReportRow("gst", "GST/HST collected", values=[Decimal("13.00")])]


@pytest.fixture
def tax_report() -> Iterator[None]:
    register(TaxSummarySample)
    yield
    registry.unregister(TaxSummarySample.id)


@pytest.mark.gap("gap-54")
def test_one_engine_for_financial_and_tax_reports(books: dict[str, Any], tax_report: None) -> None:
    client, base = books["client"], books["base"]
    catalogue = client.get(base).json()
    listed = {r["id"]: r for c in catalogue["categories"] for r in c["reports"]}
    assert {"trial_balance", "account_activity", "gap54_tax_summary"} <= set(listed)
    assert {listed[k]["category"] for k in listed} >= {"financial", "tax"}
    for report in registry:
        slug = report.slug
        run = client.get(f"{base}/{slug}/run", _sample_params(report))
        assert run.status_code == 200, (slug, run.json())
        body = run.json()
        assert body["report"] == report.id and "header" in body
        export = client.get(f"{base}/{slug}/export", {**_sample_params(report), "file": "csv"})
        assert export.status_code == 200, slug
        assert client.get(f"{base}/{slug}/layouts").status_code == 200


def _sample_params(report: ReportDefinition) -> dict[str, str]:
    names = {spec.name for spec in report.params}
    params = {}
    if {"date_from", "date_to"} <= names:
        params = {"date_from": "2026-06-01", "date_to": "2026-06-30"}
    if "account" in names:  # account transactions (K-02-T10): the report books' chequing account
        params["account"] = "1000"
    return params


@pytest.mark.gap("gap-55")
def test_header_name_no_activity_and_year_to_date(books: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        validate_organisation_legal_name("1001633222")
    validate_organisation_legal_name("1001633222 Ontario Inc.")
    report = registry.get("account_activity")
    empty = report.run(books["org"], {"date_from": "2025-01-01", "date_to": "2025-01-31"})
    body = empty.as_dict()
    body["header"] = header_for(books["org"], report, empty.params, today=D(2026, 8, 1)).as_dict()
    assert body["rows"] == []
    assert "–" not in render_csv(body).decode("utf-8")
    printed = pdf_text(render_pdf(body))
    assert "No activity in this period" in printed and "–" not in printed
    future = header_for(
        books["org"],
        report,
        {"date_from": D(2026, 4, 1), "date_to": D(2027, 3, 31)},
        today=D(2026, 8, 1),
    )
    assert future.status_label == "Year to date — unaudited"
    past = header_for(
        books["org"], report, {"date_from": JUNE.start, "date_to": JUNE.end}, today=D(2026, 8, 1)
    )
    assert past.status_label == ""
