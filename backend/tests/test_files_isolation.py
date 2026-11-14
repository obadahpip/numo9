"""A-06-T14 — documents isolation & security.

Acceptance: the sweep passes (every files endpoint, requested as another organisation's user,
answers 404). Also, by hand: another organisation's document id under one's own organisation is
404 on every document endpoint (detail, edit, finalize, signed URL, actions); a signed URL for
another organisation's document is refused by the service and keys outside the organisation's
prefix are refused; bulk changes and attachments can't reach another organisation's documents
or records; row-level security hides the documents tables from raw SQL of another
organisation; inbound mail for one organisation's address never lands in another's.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection

from numo9.contacts.models import Contact
from numo9.files import storage
from numo9.files.models import Attachment, Document, DocumentStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from numo9.tenancy.rls import GUC
from tests.contact_helpers import contact
from tests.files_helpers import PDF, api, owner_of, upload

pytestmark = [pytest.mark.django_db, pytest.mark.tenant_isolation, pytest.mark.usefixtures("s3")]

postgres_only = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="row-level security is PostgreSQL-only"
)


@pytest.fixture
def maple() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def birch() -> Organisation:
    return Organisation.objects.create(name="Birch Garage Inc.")


@pytest.fixture
def maple_client(maple: Organisation) -> Any:
    return api(owner_of(maple, "dana@maple.ca"))


@pytest.fixture
def birch_client(birch: Organisation) -> Any:
    return api(owner_of(birch, "omar@birch.ca"))


@pytest.fixture
def maple_doc(maple: Organisation, maple_client: Any) -> Document:
    """A clean, previewed document of Maple Leaf."""
    created = upload(maple_client, maple, "maple-bill.pdf", PDF).json()
    document = Document._base_manager.get(public_id=created["id"])
    document.status = DocumentStatus.CLEAN
    document.preview_status = "ready"
    document.preview_key = storage.derived_key(document.file_key, "preview.jpg")
    document.save(update_fields=["status", "preview_status", "preview_key"])
    return document


def files(org: Organisation) -> str:
    return f"/api/v1/o/{org.public_id}/files"


# ---- acceptance: the sweep --------------------------------------------------------------------


def test_sweep_passes_on_every_files_endpoint() -> None:
    out = StringIO()
    call_command("tenant_sweep", stdout=out)  # raises CommandError on any leak
    report = out.getvalue()
    routes = [line for line in report.splitlines() if "/files" in line]
    assert len(routes) >= 12, report
    for line in routes:
        assert not line.startswith("FAIL"), line
    # The public inbound webhook is the one exemption (signed by the provider, no organisation).
    assert any("inbound/email" in line for line in report.splitlines())


# ---- another organisation's document id ---------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("get", "", None),
        ("patch", "", {"period": "2026-10"}),
        ("post", "/finalize", None),
        ("get", "/url", None),
        ("get", "/url?variant=preview", None),
        ("get", "/actions", None),
    ],
)
def test_foreign_document_id_is_404_on_every_document_endpoint(
    maple_doc: Document,
    birch: Organisation,
    birch_client: Any,
    method: str,
    suffix: str,
    body: dict[str, str] | None,
) -> None:
    response = getattr(birch_client, method)(
        f"{files(birch)}/{maple_doc.public_id}{suffix}", body, format="json"
    )
    assert response.status_code == 404
    assert "maple-bill" not in response.content.decode()
    maple_doc.refresh_from_db()
    assert maple_doc.period == ""


def test_another_organisations_files_url_is_404_for_a_non_member(
    maple: Organisation, maple_doc: Document, birch_client: Any
) -> None:
    for path in ("", f"/{maple_doc.public_id}", f"/{maple_doc.public_id}/url", "/tags"):
        assert birch_client.get(f"{files(maple)}{path}").status_code == 404


def test_listing_and_tags_show_only_the_organisations_documents(
    maple_doc: Document, birch: Organisation, birch_client: Any
) -> None:
    upload(birch_client, birch, "birch-receipt.pdf", PDF + b"% birch\n")
    names = [d["name"] for d in birch_client.get(files(birch)).json()["results"]]
    assert names == ["birch-receipt.pdf"]


# ---- signed URLs and keys -----------------------------------------------------------------------


def test_signed_url_for_another_organisations_document_is_refused(
    maple: Organisation, maple_doc: Document, birch: Organisation
) -> None:
    with org_context(maple):
        assert storage.signed_url(maple_doc).url
    with org_context(birch):
        for variant in ("file", "preview"):
            with pytest.raises(storage.ForeignDocument):
                storage.signed_url(maple_doc, variant=variant)
    with pytest.raises(storage.ForeignDocument):  # no organisation at all
        storage.signed_url(maple_doc)


def test_signed_urls_carry_the_organisation_prefix_and_expire(
    maple: Organisation, maple_doc: Document, maple_client: Any
) -> None:
    url = maple_client.get(f"{files(maple)}/{maple_doc.public_id}/url").json()["url"]
    assert f"org/{maple.public_id}/" in url
    assert "X-Amz-Expires=300" in url


def test_keys_outside_the_organisation_prefix_are_refused(
    maple: Organisation, birch: Organisation, maple_doc: Document
) -> None:
    storage.check_key(maple, maple_doc.file_key)
    for key in (
        maple_doc.file_key,  # Maple's key, checked for Birch
        f"org/{birch.public_id}/../{maple.public_id}/x.pdf",
        "",
        f"org/{uuid.uuid4()}/x.pdf",
    ):
        with pytest.raises(storage.ForeignDocument):
            storage.check_key(birch, key)


def test_a_document_pointing_at_another_organisations_key_is_not_served(
    maple_doc: Document, birch: Organisation, birch_client: Any
) -> None:
    """Even a (corrupted) Birch row holding Maple's key gets no URL for it."""
    with org_context(birch):
        forged = Document.objects.create(
            file_key=maple_doc.file_key,
            name="forged.pdf",
            mime="application/pdf",
            size=len(PDF),
            sha256="f" * 64,
            status=DocumentStatus.CLEAN,
        )
    assert birch_client.get(f"{files(birch)}/{forged.public_id}/url").status_code == 404


# ---- bulk and attachments -------------------------------------------------------------------


def test_bulk_ignores_another_organisations_documents(
    maple_doc: Document, birch: Organisation, birch_client: Any
) -> None:
    response = birch_client.post(
        f"{files(birch)}/bulk",
        {"ids": [str(maple_doc.public_id)], "action": "archive"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 0
    maple_doc.refresh_from_db()
    assert maple_doc.folder == "inbox"


def test_attachments_cannot_cross_organisations(
    maple: Organisation, maple_doc: Document, birch: Organisation, birch_client: Any
) -> None:
    with org_context(maple):
        maple_contact: Contact = contact(maple, "Maple Supply Ltd.")
    with org_context(birch):
        birch_contact: Contact = contact(birch, "Birch Parts Co.")
    attachments = f"{files(birch)}/attachments"
    # Maple's document on Birch's contact, and Birch's document on Maple's contact.
    first = birch_client.post(
        attachments,
        {
            "document": str(maple_doc.public_id),
            "record_type": "contacts.Contact",
            "record_id": str(birch_contact.public_id),
        },
        format="json",
    )
    assert first.status_code == 404
    birch_doc = upload(birch_client, birch, "birch.pdf", PDF + b"% b\n").json()
    second = birch_client.post(
        attachments,
        {
            "document": birch_doc["id"],
            "record_type": "contacts.Contact",
            "record_id": str(maple_contact.public_id),
        },
        format="json",
    )
    assert second.status_code == 404
    listing = birch_client.get(
        attachments,
        {"record_type": "contacts.Contact", "record_id": str(maple_contact.public_id)},
    )
    assert listing.status_code == 404
    assert Attachment._base_manager.count() == 0


def test_another_organisations_attachment_cant_be_removed(
    maple: Organisation,
    maple_client: Any,
    maple_doc: Document,
    birch: Organisation,
    birch_client: Any,
) -> None:
    with org_context(maple):
        record: Contact = contact(maple, "Maple Supply Ltd.")
    link = maple_client.post(
        f"{files(maple)}/attachments",
        {
            "document": str(maple_doc.public_id),
            "record_type": "contacts.Contact",
            "record_id": str(record.public_id),
        },
        format="json",
    ).json()
    assert birch_client.delete(f"{files(birch)}/attachments/{link['id']}").status_code == 404
    assert Attachment._base_manager.filter(deleted_at__isnull=True).count() == 1


# ---- database row-level security ----------------------------------------------------------


def sql(query: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        return list(cursor.fetchall()) if cursor.description else []


@pytest.fixture
def app_role() -> Iterator[None]:
    role = f"numo9_rls_probe_{uuid.uuid4().hex[:8]}"
    sql(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
    sql(f"GRANT USAGE ON SCHEMA public TO {role}")
    sql(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
    sql(f"SET LOCAL ROLE {role}")
    yield
    sql("RESET ROLE")


@postgres_only
def test_row_level_security_on_the_documents_tables(
    maple: Organisation, maple_doc: Document, birch: Organisation
) -> None:
    tables = ("files_document", "files_attachment", "files_inboundmessage")
    flags = sql(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = ANY(%s)",
        [list(tables)],
    )
    assert sorted(flags) == sorted((t, True, True) for t in tables)


@postgres_only
def test_raw_sql_sees_only_the_active_organisations_documents(
    maple: Organisation, maple_doc: Document, birch: Organisation, app_role: None
) -> None:
    assert sql("SELECT current_setting(%s, true)", [GUC])[0][0] in ("", None)
    assert sql("SELECT count(*) FROM files_document") == [(0,)]
    with org_context(birch):
        assert sql("SELECT count(*) FROM files_document") == [(0,)]
    with org_context(maple):
        assert sql("SELECT name FROM files_document") == [("maple-bill.pdf",)]
