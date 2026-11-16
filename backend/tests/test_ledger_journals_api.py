"""C-02-T15 — Read API ``GET journals`` and ``GET journals/<id>``. Contract tests + sweep.

Covers: the list (posted and reversed by default, newest first, totals and line counts, filters:
status, dates, type, source, account, book, text/number, paging) and the detail (lines with
account and contact, totals per book, source, reversal links both ways, posted by/at, audit
trail); permission ``accounting.journals.view`` (403 without it), feature
``accounting.journals.read`` (402 outside the package), another organisation's journal → 404,
bad filters → 400; documented in the OpenAPI schema; the tenant sweep has a factory.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
import yaml
from django.test import Client

from numo9.accounts.models import User
from numo9.catalogue import drf as catalogue_drf
from numo9.ledger.models import Book, JournalEntry
from numo9.ledger.services import post_journal, reverse, save_draft
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from numo9.tenancy.sweep import SWEEP_FACTORIES
from tests.contact_helpers import contact
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


def _client(org: Organisation, role: str) -> Client:
    user = User.objects.create_user(
        f"{role}-{org.public_id.hex[:6]}@maple.ca", password="x" * 12, name=role.title()
    )
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


def url(org: Organisation, suffix: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/journals{suffix}"


@pytest.fixture
def books(org: Organisation) -> Iterator[dict[str, Any]]:
    with org_context(org):
        acc = {
            "ar": account(org, "1100", "Accounts receivable", subtype="current_asset"),
            "sales": account(org, "4000", "Sales", subtype="revenue"),
            "amort": account(org, "6400", "Amortization", subtype="amortisation"),
            "accum": account(
                org, "1810", "Accumulated amortization", subtype="accumulated_amortisation"
            ),
        }
        customer = contact(org, "Érable Distribution inc.")
        first = post_journal(
            JournalSpec(
                date=dt.date(2026, 3, 1),
                type="sales",
                narration="Invoice INV-0042",
                source_type="sales.Invoice",
                source_id="inv-42",
                lines=(
                    LineSpec(acc["ar"], debit=Decimal("1130.00"), contact=customer),
                    LineSpec(acc["sales"], credit=Decimal("1130.00"), tax_code="HST-ON"),
                ),
            ),
            user=None,
        )
        cca = post_journal(
            JournalSpec(
                date=dt.date(2026, 3, 31),
                type="adjustment",
                narration="CCA vs. book amortization",
                lines=(
                    LineSpec(acc["amort"], debit=Decimal("40.00"), book=Book.TAX),
                    LineSpec(acc["accum"], credit=Decimal("40.00"), book=Book.TAX),
                ),
            ),
            user=None,
        )
        reversal = reverse(first, date=dt.date(2026, 4, 2), user=None)
        draft = save_draft(
            JournalSpec(
                date=dt.date(2026, 4, 5),
                narration="Draft accrual",
                lines=(
                    LineSpec(acc["ar"], debit=Decimal("5.00")),
                    LineSpec(acc["sales"], credit=Decimal("5.00")),
                ),
            ),
            user=None,
        )
        yield {
            "acc": acc,
            "first": first,
            "cca": cca,
            "reversal": reversal,
            "draft": draft,
            "customer": customer,
        }


def numbers(body: dict[str, Any]) -> list[str]:
    return [row["number"] for row in body["results"]]


def test_list_newest_first_posted_and_reversed(org: Organisation, books: dict[str, Any]) -> None:
    response = _client(org, "owner").get(url(org))
    assert response.status_code == 200, response.content
    body = response.json()
    assert numbers(body) == ["JE-000003", "JE-000002", "JE-000001"]
    assert body["count"] == 3 and body["next_offset"] is None
    first = body["results"][2]
    assert first["status"] == "reversed" and first["total"] == "1130.00" and first["lines"] == 2
    assert first["source"] == {"type": "sales.Invoice", "id": "inv-42"}
    assert first["reversed_by"]["number"] == "JE-000003"
    assert body["results"][0]["reversal_of"]["number"] == "JE-000001"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("status=draft", [""]),
        ("status=posted", ["JE-000003", "JE-000002"]),
        ("from=2026-03-15&to=2026-03-31", ["JE-000002"]),
        ("type=sales", ["JE-000001"]),
        ("source_type=sales.Invoice&source_id=inv-42", ["JE-000003", "JE-000001"]),
        ("book=accounting", ["JE-000003", "JE-000001"]),
        ("book=tax", ["JE-000003", "JE-000002", "JE-000001"]),
        ("q=amortization", ["JE-000002"]),
        ("q=JE-000002", ["JE-000002"]),
        ("q=3", ["JE-000003"]),
        ("limit=2", ["JE-000003", "JE-000002"]),
        ("limit=2&offset=2", ["JE-000001"]),
    ],
)
def test_filters(org: Organisation, books: dict[str, Any], query: str, expected: list[str]) -> None:
    body = _client(org, "owner").get(f"{url(org)}?{query}").json()
    assert numbers(body) == expected


def test_account_filter_and_paging(org: Organisation, books: dict[str, Any]) -> None:
    client = _client(org, "owner")
    sales = books["acc"]["sales"].public_id
    assert numbers(client.get(f"{url(org)}?account={sales}").json()) == ["JE-000003", "JE-000001"]
    assert client.get(f"{url(org)}?limit=2").json()["next_offset"] == 2


@pytest.mark.parametrize("query", ["status=open", "from=31/03/2026", "book=both", "limit=x"])
def test_bad_filters(org: Organisation, books: dict[str, Any], query: str) -> None:
    assert _client(org, "owner").get(f"{url(org)}?{query}").status_code == 400


def test_detail(org: Organisation, books: dict[str, Any]) -> None:
    first: JournalEntry = books["first"]
    body = _client(org, "owner").get(url(org, f"/{first.public_id}")).json()
    assert body["number"] == "JE-000001" and body["status"] == "reversed"
    assert body["lines"][0]["account"] == {
        "id": str(books["acc"]["ar"].public_id),
        "code": "1100",
        "name": "Accounts receivable",
    }
    assert body["lines"][0]["contact"]["name"] == "Érable Distribution inc."
    assert body["lines"][1]["tax_code"] == "HST-ON" and body["lines"][1]["credit"] == "1130.00"
    assert body["books"] == {
        "accounting": {"debit": "1130.00", "credit": "1130.00"},
        "tax": {"debit": "1130.00", "credit": "1130.00"},
    }
    assert body["reversed_by"]["number"] == "JE-000003" and body["posted_at"]
    assert [a["action"] for a in body["audit"]] == [
        "ledger.journalentry.posted",
        "ledger.journalentry.reversed",
    ]
    cca = _client(org, "accountant_delegate").get(url(org, f"/{books['cca'].public_id}")).json()
    assert cca["book_scope"] == "tax" and list(cca["books"]) == ["tax"]


def test_permission_feature_and_isolation(org: Organisation, books: dict[str, Any]) -> None:
    assert _client(org, "employee").get(url(org)).status_code == 403
    other = Organisation.objects.create(name="Other Inc.")
    outsider = _client(other, "owner")
    assert outsider.get(url(org)).status_code == 404
    assert outsider.get(url(other, f"/{books['first'].public_id}")).status_code == 404


class NoPackage:
    def allows(self, organisation: Organisation | None, key: str) -> bool:
        return False


def test_feature_outside_the_package(
    org: Organisation, books: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalogue_drf, "get_resolver", lambda: NoPackage())
    refused = _client(org, "owner").get(url(org))
    assert refused.status_code == 402
    assert refused.json()["feature"] == "accounting.journals.read"


def test_documented_and_swept(org: Organisation) -> None:
    schema = yaml.safe_load(_client(org, "owner").get("/api/schema/").content)
    assert set(schema["paths"]["/api/v1/o/{org}/journals"]) >= {"get"}
    assert schema["paths"]["/api/v1/o/{org}/journals/{public_id}"]["get"]["operationId"] == (
        "journals_get"
    )
    row: Any = SWEEP_FACTORIES["ledger.JournalEntry"](org)
    assert row.number == 1
