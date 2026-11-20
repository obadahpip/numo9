"""A-09-T02 — provider registry: a model registers ``to_document()``; signals update the index on
save and delete, in the same transaction.

Acceptance: a record saved → indexed (searchable vector written); changed → the document follows;
soft-deleted or deleted → gone; a provider answering ``None`` → no document; a rolled-back save
leaves nothing; unregistering stops the signals.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import connection, transaction
from django.db.models import QuerySet

from numo9.search.models import SearchDocument
from numo9.search.registry import Doc, register_provider, unregister_provider
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.testapp.models import Widget

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    register_provider(
        Widget,
        lambda w: None if w.label == "secret" else Doc(title=w.label, url=f"/w/{w.public_id}"),
    )
    with org_context(organisation):
        yield organisation
    unregister_provider(Widget)


def widgets() -> QuerySet[SearchDocument]:
    """The widget documents (the organisation itself is indexed too, by its own provider)."""
    return SearchDocument.objects.filter(object_type="testapp.widget")


def docs() -> list[str]:
    return list(widgets().values_list("title", flat=True))


def test_saved_record_is_indexed_and_follows_changes(org: Organisation) -> None:
    widget = Widget.objects.create(organisation=org, label="Blue sprocket")
    (doc,) = widgets()
    assert (doc.object_type, doc.object_id, doc.title) == (
        "testapp.widget",
        str(widget.public_id),
        "Blue sprocket",
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT search_vector::text FROM search_searchdocument WHERE id = %s", [doc.pk]
        )
        assert "sprocket" in cursor.fetchone()[0]
    widget.label = "Red sprocket"
    widget.save()
    assert docs() == ["Red sprocket"]


def test_soft_delete_delete_and_none_remove_the_document(org: Organisation) -> None:
    one = Widget.objects.create(organisation=org, label="One")
    two = Widget.objects.create(organisation=org, label="Two")
    one.soft_delete()
    two.delete()
    assert docs() == []
    hidden = Widget.objects.create(organisation=org, label="secret")
    assert docs() == []
    hidden.label = "now public"
    hidden.save()
    assert docs() == ["now public"]
    hidden.label = "secret"
    hidden.save()
    assert docs() == []


def test_rolled_back_save_leaves_nothing(org: Organisation) -> None:
    with pytest.raises(RuntimeError), transaction.atomic():
        Widget.objects.create(organisation=org, label="Ghost")
        raise RuntimeError
    assert docs() == []


def test_unregistered_model_is_not_indexed(org: Organisation) -> None:
    unregister_provider(Widget)
    Widget.objects.create(organisation=org, label="Plain")
    assert docs() == []
