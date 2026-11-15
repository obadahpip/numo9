"""A-06-T10 — tagging API (period YYYY-MM, tax year, custom tags), archive/unarchive, bulk.

Acceptance: filter by tag works. Also: filters by folder, period (and untagged), tax year, status,
source and text; several tags must all match; keyset pages over a large inbox with the total;
PATCH validates period, tax year and tags; bulk archive / unarchive / tags / period / tax year in
one transaction and one audit batch; invalid values refuse the whole bulk; tags in use with counts;
other organisations' documents untouched; permissions.
"""

from __future__ import annotations

from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.files import storage
from numo9.files.models import Document, DocumentSource, DocumentStatus, Folder
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.files_helpers import api, owner_of

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def client(org: Organisation) -> Any:
    return api(owner_of(org))


def make(org: Organisation, name: str, **fields: Any) -> Document:
    with org_context(org):
        fields.setdefault("status", DocumentStatus.CLEAN)
        item = Document(
            organisation=org,
            name=name,
            file_key=storage.new_key(org, name),
            mime="application/pdf",
            size=10,
            **fields,
        )
        item.save()
        return item


def names(response: Any) -> list[str]:
    assert response.status_code == 200, response.json()
    return [d["name"] for d in response.json()["results"]]


def url(org: Organisation, suffix: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/files{suffix}"


# ---- acceptance -----------------------------------------------------------------------------


def test_filter_by_tag_works(client: Any, org: Organisation) -> None:
    make(org, "hydro.pdf", tags=["Utilities", "GST return"])
    make(org, "rent.pdf", tags=["Rent"])
    make(org, "gas.pdf", tags=["utilities"])
    assert sorted(names(client.get(url(org), {"tag": "Utilities"}))) == ["gas.pdf", "hydro.pdf"]
    assert names(client.get(url(org) + "?tag=Utilities&tag=GST+return")) == ["hydro.pdf"]
    assert names(client.get(url(org), {"tag": "Payroll"})) == []


# ---- filters --------------------------------------------------------------------------------


def test_filters(client: Any, org: Organisation) -> None:
    make(org, "oct.pdf", period="2026-10", tax_year=2026)
    make(
        org,
        "sep.pdf",
        period="2026-09",
        tax_year=2026,
        source=DocumentSource.EMAIL,
        sender="billing@hydro.example",
    )
    make(org, "old.pdf", tax_year=2025, folder=Folder.ARCHIVED)
    make(org, "new.pdf", status=DocumentStatus.SCANNING)
    assert names(client.get(url(org), {"period": "2026-10"})) == ["oct.pdf"]
    assert names(client.get(url(org), {"period": "none"})) == ["new.pdf"]
    assert sorted(names(client.get(url(org), {"tax_year": "2026"}))) == ["oct.pdf", "sep.pdf"]
    assert names(client.get(url(org), {"folder": "archived"})) == ["old.pdf"]
    assert names(client.get(url(org), {"status": "scanning"})) == ["new.pdf"]
    assert names(client.get(url(org), {"source": "email"})) == ["sep.pdf"]
    assert names(client.get(url(org), {"q": "hydro"})) == ["sep.pdf"]
    bad = client.get(url(org), {"period": "Oct 2026"})
    assert bad.status_code == 400 and bad.json()["code"] == "files.bad_filter"


def test_keyset_pages_with_the_total(client: Any, org: Organisation) -> None:
    for i in range(25):
        make(org, f"doc-{i:02d}.pdf")
    first = client.get(url(org), {"limit": 10}).json()
    assert first["total"] == 25 and len(first["results"]) == 10
    seen = [d["name"] for d in first["results"]]
    cursor = first["next"]
    while cursor:
        page = client.get(url(org), {"limit": 10, "cursor": cursor}).json()
        seen += [d["name"] for d in page["results"]]
        cursor = page["next"]
    assert sorted(seen) == sorted(f"doc-{i:02d}.pdf" for i in range(25)) and len(seen) == 25
    assert client.get(url(org), {"limit": 1001}).json()["code"] == "files.bad_limit"
    assert client.get(url(org), {"cursor": "garbage!"}).json()["code"] == "files.bad_cursor"


# ---- one document ---------------------------------------------------------------------------


def test_patch_tags_period_and_folder(client: Any, org: Organisation) -> None:
    item = make(org, "hydro.pdf")
    response = client.patch(
        url(org, f"/{item.public_id}"),
        {
            "period": "2026-10",
            "tax_year": 2026,
            "tags": ["Utilities", "utilities", " GST "],
            "folder": "archived",
        },
        format="json",
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert (body["period"], body["tax_year"], body["tags"], body["folder"]) == (
        "2026-10",
        2026,
        ["Utilities", "GST"],
        "archived",
    )
    bad = client.patch(
        url(org, f"/{item.public_id}"), {"period": "2026-13", "tax_year": 1800}, format="json"
    )
    assert bad.status_code == 400
    assert set(bad.json()) == {"period", "tax_year"}


# ---- bulk -----------------------------------------------------------------------------------


def test_bulk_archive_tag_and_period(client: Any, org: Organisation) -> None:
    items = [make(org, f"doc-{i}.pdf") for i in range(3)]
    ids = [str(i.public_id) for i in items]
    assert client.post(
        url(org, "/bulk"), {"ids": ids, "action": "add_tags", "tags": ["Q4"]}, format="json"
    ).json() == {"updated": 3}
    assert client.post(
        url(org, "/bulk"),
        {"ids": ids[:2], "action": "set_period", "period": "2026-12"},
        format="json",
    ).json() == {"updated": 2}
    assert client.post(
        url(org, "/bulk"), {"ids": ids, "action": "archive"}, format="json"
    ).json() == {"updated": 3}
    assert names(client.get(url(org))) == []
    archived = client.get(url(org), {"folder": "archived", "tag": "Q4", "period": "2026-12"})
    assert sorted(names(archived)) == ["doc-0.pdf", "doc-1.pdf"]
    client.post(url(org, "/bulk"), {"ids": ids, "action": "unarchive"}, format="json")
    client.post(
        url(org, "/bulk"), {"ids": ids, "action": "remove_tags", "tags": ["q4"]}, format="json"
    )
    assert names(client.get(url(org), {"tag": "Q4"})) == []
    with org_context(org):
        batches = AuditEvent.objects.filter(action="audit.batch").count()
    assert batches == 5


def test_an_invalid_value_refuses_the_whole_bulk(client: Any, org: Organisation) -> None:
    items = [make(org, f"doc-{i}.pdf") for i in range(2)]
    response = client.post(
        url(org, "/bulk"),
        {"ids": [str(i.public_id) for i in items], "action": "set_period", "period": "2026-13"},
        format="json",
    )
    assert response.status_code == 400
    assert names(client.get(url(org), {"period": "none"})) == ["doc-1.pdf", "doc-0.pdf"]


def test_bulk_never_touches_another_organisation(client: Any, org: Organisation) -> None:
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    theirs = make(other, "theirs.pdf")
    response = client.post(
        url(org, "/bulk"), {"ids": [str(theirs.public_id)], "action": "archive"}, format="json"
    )
    assert response.json() == {"updated": 0}
    theirs.refresh_from_db()
    assert theirs.folder == Folder.INBOX


def test_tags_in_use(client: Any, org: Organisation) -> None:
    make(org, "a.pdf", tags=["Utilities", "GST"])
    make(org, "b.pdf", tags=["Utilities"])
    assert client.get(url(org, "/tags")).json() == {
        "results": [{"tag": "Utilities", "count": 2}, {"tag": "GST", "count": 1}]
    }
