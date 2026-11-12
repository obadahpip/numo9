"""Audit log exports CSV / XLSX / PDF from the screen's query (A-04-T08).

Acceptance: export rows = screen rows — for the same filters, the CSV and XLSX hold exactly the
events the list pages through, in the same order (compared by event id), and the PDF lists the
same records. Also: the person's 12/24-hour preference (never "16:33PM"), masked values, CSV
formula injection, the PDF size limit, permissions, and the export recorded in the log.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import zoneinfo
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.audit import exports
from numo9.audit.models import AuditEvent
from numo9.audit.service import record
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.testapp.models import AuditedInvoice

pytestmark = pytest.mark.django_db

TORONTO = zoneinfo.ZoneInfo("America/Toronto")


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")


def person(org: Organisation, role: str, email: str, **fields: Any) -> User:
    user = User.objects.create_user(email=email, password="x" * 12, name="Avery Owner", **fields)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


@pytest.fixture
def owner(org: Organisation) -> User:
    return person(org, "owner", "avery@refined.ca")


def api(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def url(org: Organisation, path: str) -> str:
    return f"/api/v1/o/{org.public_id}/audit/{path}"


def screen_ids(client: APIClient, org: Organisation, **filters: Any) -> list[str]:
    ids: list[str] = []
    cursor = None
    while True:
        params = {**filters, "limit": 50, **({"cursor": cursor} if cursor else {})}
        body = client.get(url(org, "events"), params).json()
        ids += [row["id"] for row in body["results"]]
        cursor = body["next"]
        if not cursor:
            return ids


def csv_rows(response: Any) -> list[list[str]]:
    text = b"".join(response.streaming_content).decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text.lstrip("﻿"))))


def xlsx_rows(response: Any) -> list[tuple[Any, ...]]:
    sheet = load_workbook(io.BytesIO(response.content), read_only=True).worksheets[0]
    return [tuple(row) for row in sheet.iter_rows(values_only=True)]


@pytest.fixture
def busy(org: Organisation, owner: User) -> None:
    """130 events of several kinds over the last weeks."""
    now = dt.datetime.now(TORONTO)
    for n in range(130):
        moment = now - dt.timedelta(hours=n * 3)
        with mock.patch("numo9.audit.service.timezone.now", return_value=moment):
            if n % 3 == 0:
                record(
                    "tests.widget.updated",
                    organisation=org,
                    actor=owner,
                    object_type="tests.Widget",
                    object_label=f"Widget {n}",
                )
            elif n % 3 == 1:
                record(
                    "tests.widget.deleted",
                    organisation=org,
                    object_type="tests.Widget",
                    object_label=f"Widget {n}",
                )
            else:
                record(
                    "role.updated",
                    organisation=org,
                    actor=owner,
                    object_type="rbac.Role",
                    object_label=f"Role {n}",
                    changes={"name": [f"R{n}", f"R{n}b"]},
                )


# ---- acceptance: export rows = screen rows -----------------------------------------------------


@pytest.mark.usefixtures("busy")
@pytest.mark.parametrize("filters", [{}, {"action": "deleted"}, {"type": "rbac.Role"}])
def test_csv_and_xlsx_rows_equal_the_screen_rows(
    org: Organisation, owner: User, filters: dict[str, str]
) -> None:
    client = api(owner)
    expected = screen_ids(client, org, **filters)
    assert expected  # the filters match something
    response = client.get(url(org, "export/csv"), filters)
    assert response.status_code == 200
    rows = csv_rows(response)
    assert rows[0] == [str(c) for c in exports.COLUMNS]
    assert [row[-1] for row in rows[1:]] == expected
    expected = screen_ids(client, org, **filters)  # the CSV export is now in the log too
    sheet = xlsx_rows(client.get(url(org, "export/xlsx"), filters))
    assert sheet[0][-1] == "Event ID"
    assert [row[-1] for row in sheet[1:]] == expected


@pytest.mark.usefixtures("busy")
def test_pdf_lists_the_screen_rows(org: Organisation, owner: User) -> None:
    from pypdf import PdfReader

    client = api(owner)
    filters = {"type": "rbac.Role", "from": dt.date.today().isoformat()}
    expected = client.get(url(org, "events"), filters).json()["results"]
    response = client.get(url(org, "export/pdf"), filters)
    assert response.status_code == 200 and response["Content-Type"] == "application/pdf"
    text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
    assert f"{len(expected)} events" in text
    for row in expected:
        assert row["record"]["label"] in text


def test_export_includes_rows_older_than_one_page_and_not_its_own_event(
    org: Organisation, owner: User
) -> None:
    for n in range(260):
        record("tests.bulk", organisation=org, object_label=f"Row {n}")
    rows = csv_rows(api(owner).get(url(org, "export/csv")))
    assert len(rows) == 1 + 260  # header + every row, not the 50 of one page
    assert AuditEvent.platform_events.filter(action="audit.log.exported").count() == 1
    assert all(row[2] != "Audit log exported" for row in rows[1:])


# ---- what the rows say -------------------------------------------------------------------------


def test_times_follow_the_persons_preference(org: Organisation) -> None:
    moment = dt.datetime(2026, 10, 26, 16, 33, tzinfo=TORONTO)
    with mock.patch("numo9.audit.service.timezone.now", return_value=moment):
        record("tests.timed", organisation=org)
    filters = {"from": "2026-10-26", "to": "2026-10-26"}
    twelve = person(org, "admin", "twelve@refined.ca", time_format="12h")
    twenty_four = person(org, "admin", "h24@refined.ca", time_format="24h")
    french = person(org, "admin", "fr@refined.ca", locale="fr-ca", time_format="24h")
    assert (
        csv_rows(api(twelve).get(url(org, "export/csv"), filters))[1][0] == "26 Oct 2026, 4:33 p.m."
    )
    assert (
        csv_rows(api(twenty_four).get(url(org, "export/csv"), filters))[1][0]
        == "26 Oct 2026, 16:33"
    )
    rows = csv_rows(api(french).get(url(org, "export/csv"), filters))
    assert rows[1][0] == "26 oct. 2026, 16 h 33"
    assert rows[0][0] == "Date et heure"
    for row in (rows[1],):
        assert "PM" not in row[0]


def test_changes_text_hides_masked_values(org: Organisation, owner: User) -> None:
    with org_context(org):
        invoice = AuditedInvoice.objects.create(
            number="INV-1", amount=Decimal("100.00"), payee_sin="046454286"
        )
        invoice.amount = Decimal("120.50")
        invoice.notes = "Net 30"
        invoice.payee_sin = "130692544"
        invoice.save()
    rows = csv_rows(api(owner).get(url(org, "export/csv"), {"action": "updated"}))
    changes = rows[1][5]
    assert "Amount: 100.00 → 120.50" in changes
    assert "Notes: (empty) → Net 30" in changes
    assert "Payee sin: Hidden" in changes
    assert "046454286" not in changes and "130692544" not in changes


def test_formula_like_text_is_written_as_text(org: Organisation, owner: User) -> None:
    record("tests.x", organisation=org, object_label='=HYPERLINK("http://evil","x")')
    rows = csv_rows(api(owner).get(url(org, "export/csv")))
    assert rows[1][4].startswith("'=")


# ---- limits, permissions, the export recorded -------------------------------------------------


def test_pdf_over_the_limit_is_refused(org: Organisation, owner: User) -> None:
    for n in range(4):
        record("tests.x", organisation=org, object_label=f"R{n}")
    with mock.patch.object(exports, "PDF_MAX_ROWS", 3):
        response = api(owner).get(url(org, "export/pdf"))
    assert response.status_code == 413 and response.json()["code"] == "audit.export_too_large"


def test_unknown_format_is_refused(org: Organisation, owner: User) -> None:
    response = api(owner).get(url(org, "export/docx"))
    assert response.status_code == 400 and response.json()["code"] == "audit.export_format"


def test_only_people_who_may_see_the_log_export_it(org: Organisation) -> None:
    sales = person(org, "sales", "lee@refined.ca")
    response = api(sales).get(url(org, "export/csv"))
    assert response.status_code == 403


def test_export_is_recorded_with_its_filters(org: Organisation, owner: User) -> None:
    response = api(owner).get(url(org, "export/xlsx"), {"type": "rbac.Role"})
    assert response["Content-Disposition"].startswith(
        'attachment; filename="audit-log_refined-interiors-inc_'
    )
    event = AuditEvent.platform_events.get(action="audit.log.exported")
    assert event.actor_user == owner and event.organisation == org
    assert event.meta["format"] == "xlsx" and event.meta["filters"]["type"] == ["rbac.Role"]
