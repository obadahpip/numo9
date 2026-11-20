"""A-09-T01 — the ``SearchDocument`` table: organisation, type, object id, title, subtitle, body
vector, amount, date, permission key, feature key; GIN and trigram indexes.

Acceptance: the migration creates the table with its indexes and row-level security; one row per
record (organisation, type, id); rows are organisation-scoped.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from numo9.search.models import SearchDocument
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def test_migration_creates_the_indexes_and_rls() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'search_searchdocument'")
        names = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = 'search_searchdocument'"
        )
        rls = cursor.fetchone()
    assert {
        "search_doc_vector_idx",
        "search_doc_title_trgm_idx",
        "search_doc_code_trgm_idx",
    } <= names
    assert rls == (True, True)


def test_one_document_per_record_and_organisation_scoped() -> None:
    maple = Organisation.objects.create(name="Maple")
    with org_context(maple):
        doc = SearchDocument.objects.create(
            organisation=maple,
            object_type="contacts.contact",
            object_id="c-1",
            title="Cedar Roofing Co.",
            amount=Decimal("1130.00"),
            url="/o/x/contacts/c-1",
            permission_key="contacts.contact.view",
            feature_key="accounting.contacts.read",
        )
        assert SearchDocument.objects.count() == 1
        with pytest.raises(IntegrityError), transaction.atomic():
            SearchDocument.objects.create(
                organisation=maple,
                object_type="contacts.contact",
                object_id="c-1",
                title="x",
                url="/",
            )
    birch = Organisation.objects.create(name="Birch")
    with org_context(birch):
        assert SearchDocument.objects.count() == 0
    assert str(doc) == "contacts.contact · Cedar Roofing Co."
