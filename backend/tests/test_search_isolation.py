"""A-09-T11 — isolation: search never returns another organisation's records.

Acceptance: the sweep passes (the search endpoint, requested as another organisation's user,
answers 404 — ``tenant_sweep``). Also, by hand: two organisations with look-alike records (same
contact names, account codes, amounts) and one person belonging to both — every result of a
search in one organisation is that organisation's (its documents and links), whatever the query
(a name, a code, a prefix, an amount, a typo, the other organisation's own name); a stranger to
the organisation is refused; and row-level security hides the other organisation's documents even
from raw SQL and unscoped queries under the application's ordinary role.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection

from numo9.search.api import ranked_documents
from numo9.search.models import SearchDocument
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.contact_helpers import contact
from tests.files_helpers import api, owner_of
from tests.ledger_helpers import account

pytestmark = [pytest.mark.django_db, pytest.mark.tenant_isolation]

postgres_only = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="row-level security is PostgreSQL-only"
)


def sql(query: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        return list(cursor.fetchall()) if cursor.description else []


def books(name: str, extra: str) -> Organisation:
    org = Organisation.objects.create(name=name)
    with org_context(org):
        contact(org, "Cedar Roofing Co.")
        contact(org, extra)
        account(org, "5400", "Rent")
        account(org, "1000", "Chequing", subtype="bank")
    return org


@pytest.fixture
def maple() -> Organisation:
    return books("Maple Leaf Supply Ltd.", "Northwood Dental")


@pytest.fixture
def birch() -> Organisation:
    return books("Birch Garage Inc.", "Northwood Lumber")


@pytest.fixture
def both(maple: Organisation, birch: Organisation) -> Any:
    """Dana keeps the books of both organisations."""
    dana = owner_of(maple, "dana@maple.ca")
    OrganisationMember.objects.create(organisation=birch, user=dana, role=OrganisationRole.OWNER)
    return api(dana)


def own_ids(org: Organisation) -> set[str]:
    with org_context(org):
        return set(SearchDocument.objects.values_list("object_id", flat=True))


def test_sweep_passes_on_the_search_endpoint() -> None:
    out = StringIO()
    call_command("tenant_sweep", stdout=out)  # raises CommandError on any leak
    assert "search" in out.getvalue()


@pytest.mark.parametrize(
    "query",
    [
        "cedar",
        "Cedar Roofing",
        "5400",
        "54",
        "chequing",
        "cedr rofing",
        "birch",
        "northwood",
        "lumber",
    ],
)
def test_every_result_belongs_to_the_searched_organisation(
    query: str, maple: Organisation, birch: Organisation, both: Any
) -> None:
    mine, theirs = own_ids(maple), own_ids(birch)
    theirs_only = theirs - mine  # Dana herself is a user of both, indexed in each
    assert mine and len(theirs_only) == len(theirs) - 1
    response = both.get(f"/api/v1/o/{maple.public_id}/search", {"q": query})
    assert response.status_code == 200
    records = response.json()["records"]
    for record in records:
        assert record["id"] in mine and record["id"] not in theirs_only, (query, record)
        assert record["url"].startswith(f"/o/{maple.public_id}"), (query, record)
    titles = {record["title"] for record in records}
    assert "Northwood Lumber" not in titles
    assert "Birch Garage Inc." not in titles
    for group in ("settings", "reports", "navigation"):
        for entry in response.json()[group]:
            assert entry["url"].startswith(f"/o/{maple.public_id}"), entry


def test_the_same_person_finds_each_organisations_own_records(
    maple: Organisation, birch: Organisation, both: Any
) -> None:
    for org, extra in ((maple, "Northwood Dental"), (birch, "Northwood Lumber")):
        records = both.get(f"/api/v1/o/{org.public_id}/search", {"q": "northwood"}).json()[
            "records"
        ]
        assert [r["title"] for r in records] == [extra]


def test_a_stranger_is_refused(maple: Organisation, birch: Organisation) -> None:
    omar = api(owner_of(birch, "omar@birch.ca"))
    response = omar.get(f"/api/v1/o/{maple.public_id}/search", {"q": "cedar"})
    assert response.status_code == 404


def test_ranking_reads_only_the_active_organisation(
    maple: Organisation, birch: Organisation
) -> None:
    with org_context(maple):
        found = ranked_documents("cedar")
    assert found and {d.organisation_id for _, _, d in found} == {maple.pk}


@pytest.fixture
def app_role(maple: Organisation, birch: Organisation) -> Iterator[None]:
    role = f"numo9_rls_probe_{uuid.uuid4().hex[:8]}"
    sql(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
    sql(f"GRANT USAGE ON SCHEMA public TO {role}")
    sql(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
    sql(f"SET LOCAL ROLE {role}")
    yield
    sql("RESET ROLE")


@postgres_only
def test_row_level_security_hides_the_other_organisations_documents(
    maple: Organisation, birch: Organisation, app_role: None
) -> None:
    assert sql("SELECT count(*) FROM search_searchdocument") == [(0,)]  # no organisation active
    with org_context(maple):
        orgs = {row[0] for row in sql("SELECT organisation_id FROM search_searchdocument")}
        assert orgs == {maple.pk}
        unscoped = SearchDocument.objects.unscoped(reason="A-09-T11 isolation probe")
        assert set(unscoped.values_list("organisation_id", flat=True)) == {maple.pk}
        assert (
            sql(
                "UPDATE search_searchdocument SET title = 'x' WHERE organisation_id = %s",
                [birch.pk],
            )
            == []
        )
    with org_context(birch):
        assert "x" not in {t for (t,) in sql("SELECT title FROM search_searchdocument")}
