"""K-01-T05 — drill-down: the lines behind a report figure sum to the figure (account activity
and trial balance), paginated 50 a page with the total on every page; each line links to its
source document (an invoice opens the invoice, a manual journal the journal); bad parameters are
400 with a code; the API needs the reports permission.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.services import post_journal
from numo9.reports.aggregation import balances_at
from numo9.reports.drill import PAGE_SIZE, drill
from numo9.reports.engine import registry
from numo9.sales.posting import approve
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.journal_helpers import pay
from tests.report_helpers import report_books
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db
D = dt.date


@pytest.fixture
def books() -> dict[str, Any]:
    return report_books()


def test_drill_sum_equals_the_figure(books: dict[str, Any]) -> None:
    org = books["org"]
    activity = registry.get("account_activity").run(
        org, {"date_from": "2026-06-01", "date_to": "2026-06-30"}
    )
    for row in activity.rows:
        assert row.drill is not None
        lines = drill(
            org,
            account=row.drill["account"],
            date_from=row.drill["from"],
            date_to=row.drill["to"],
        )
        assert lines.total == row.values[2], row.label
        assert sum((Decimal(line["amount"]) for line in lines.lines), Decimal("0")) == lines.total
    tb = registry.get("trial_balance").run(org, {"as_of": "2026-06-30"})
    for row in tb.rows:
        assert row.drill is not None
        lines = drill(org, account=row.drill["account"], date_to=row.drill["to"])
        figure = (row.values[0] or Decimal("0")) - (row.values[1] or Decimal("0"))
        assert lines.total == figure, row.label
    rent = drill(org, account="5400", date_to=D(2026, 6, 30))
    [line] = rent.lines  # the 999.00 draft isn't a line of any figure
    assert (line["amount"], line["journal"]) == ("2400.00", rent.lines[0]["journal"])
    assert line["source"]["url"].startswith(f"/o/{org.public_id}/accounting/journals/")


def test_pages_keep_the_total(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        for n in range(PAGE_SIZE + 5):
            post_journal(
                pay(
                    books["office"], books["chequing"], "1.00", D(2026, 8, 1) + dt.timedelta(n % 20)
                ),
                user=None,
            )
    first = drill(org, account="6100", date_from=D(2026, 8, 1), date_to=D(2026, 8, 31))
    second = drill(org, account="6100", date_from=D(2026, 8, 1), date_to=D(2026, 8, 31), page=2)
    assert (first.count, first.pages, len(first.lines), len(second.lines)) == (55, 2, 50, 5)
    assert first.total == second.total == Decimal("55.00")
    with org_context(org):
        assert balances_at([D(2026, 8, 31)], accounts=[books["office"].pk])[books["office"].pk] == [
            Decimal("205.00")
        ]


def test_invoice_line_links_to_the_invoice() -> None:
    sales = sales_books()
    owner = User.objects.create_user("owner@refined.ca", name="Owner")
    OrganisationMember.objects.create(organisation=sales["org"], user=owner, role="owner")
    invoice = approve(draft(sales, [("1", "100.00", "sales.ON.standard")]), owner)
    with org_context(sales["org"]):
        code = sales["revenue"].code
    lines = drill(sales["org"], account=code, date_to=D(2026, 6, 30))
    [line] = lines.lines
    assert line["source"]["type"] == "sales.invoice"
    assert (
        line["source"]["url"]
        == f"/o/{sales['org'].public_id}/sales/invoices/{invoice.public_id}/email"
    )


def test_api(books: dict[str, Any]) -> None:
    org = books["org"]
    owner = User.objects.create_user("owner@refined.ca", name="Owner")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    client = Client()
    client.force_login(owner)
    base = f"/api/v1/o/{org.public_id}/reports/account-activity/drill"
    answer = client.get(base, {"account": "5400", "from": "2026-06-01", "to": "2026-06-30"})
    assert answer.status_code == 200, answer.json()
    body = answer.json()
    assert (body["account"]["code"], body["total"], body["count"]) == ("5400", "2400.00", 1)
    for params, code in (
        ({"to": "2026-06-30"}, "reports.param.required"),
        ({"account": "5400"}, "reports.param.required"),
        ({"account": "9999", "to": "2026-06-30"}, "reports.drill.account"),
        ({"account": "5400", "to": "June"}, "reports.param.invalid"),
        ({"account": "5400", "to": "2026-06-30", "page": "9"}, "reports.drill.page"),
    ):
        refused = client.get(base, params)
        assert (refused.status_code, refused.json()["code"]) == (400, code), params
    assert client.get(f"/api/v1/o/{org.public_id}/reports/nope/drill").status_code == 404
    hr = User.objects.create_user("hr@refined.ca", name="HR")
    OrganisationMember.objects.create(organisation=org, user=hr, role="hr")
    other = Client()
    other.force_login(hr)
    assert other.get(base, {"account": "5400", "to": "2026-06-30"}).status_code == 403
