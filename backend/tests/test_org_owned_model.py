"""A-01-T02 — abstract OrgOwnedModel: organisation FK, created_by, timestamps, soft delete and
UUID public id, verified through the test-only concrete models in tests.testapp."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from numo9.accounts.models import User
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrgOwnedModel
from tests.testapp.models import Gadget, Widget

EXPECTED = {
    "organisation": models.ForeignKey,
    "public_id": models.UUIDField,
    "created_by": models.ForeignKey,
    "created_at": models.DateTimeField,
    "updated_at": models.DateTimeField,
    "deleted_at": models.DateTimeField,
}


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery")


@pytest.fixture(autouse=True)
def _active_org(request: pytest.FixtureRequest) -> Iterator[None]:
    """Database tests run inside the organisation's context (OrgScopedManager, A-01-T04)."""
    if request.node.get_closest_marker("django_db") is None:
        yield
        return
    with org_context(request.getfixturevalue("org")):
        yield


@pytest.fixture
def user() -> User:
    return User.objects.create_user("clerk@example.com", name="Clerk")


def test_base_is_abstract() -> None:
    assert OrgOwnedModel._meta.abstract is True


@pytest.mark.parametrize("model", [Widget, Gadget])
def test_subclass_gets_every_field(model: type[OrgOwnedModel]) -> None:
    for name, field_class in EXPECTED.items():
        assert isinstance(model._meta.get_field(name), field_class), name
    org_fk = model._meta.get_field("organisation")
    assert org_fk.related_model is Organisation
    assert org_fk.null is False
    assert org_fk.remote_field.on_delete is models.PROTECT
    created_by = model._meta.get_field("created_by")
    assert created_by.related_model is User
    assert created_by.null is True
    assert model._meta.get_field("public_id").unique is True
    assert model._meta.get_field("deleted_at").null is True


@pytest.mark.django_db
def test_defaults_on_create(org: Organisation, user: User) -> None:
    before = timezone.now()
    widget = Widget.objects.create(organisation=org, created_by=user, label="w")
    assert isinstance(widget.public_id, uuid.UUID)
    assert widget.created_by == user
    assert before <= widget.created_at <= timezone.now()
    assert widget.updated_at >= widget.created_at
    assert widget.deleted_at is None
    assert widget.is_deleted is False


@pytest.mark.django_db
def test_public_ids_are_unique_and_not_sequential(org: Organisation) -> None:
    ids = {Widget.objects.create(organisation=org, label=str(i)).public_id for i in range(20)}
    assert len(ids) == 20


@pytest.mark.django_db
def test_created_by_is_optional_for_system_writes(org: Organisation) -> None:
    widget = Widget(organisation=org, label="imported")
    widget.full_clean()
    widget.save()
    assert widget.created_by is None


@pytest.mark.django_db
def test_organisation_is_required(org: Organisation) -> None:
    widget = Widget(label="orphan")
    with pytest.raises(ValidationError) as exc:
        widget.full_clean()
    assert "organisation" in exc.value.message_dict
    with pytest.raises(IntegrityError), transaction.atomic():
        Widget(label="orphan").save()  # bypasses the manager, which would fill the organisation


@pytest.mark.django_db
def test_updated_at_moves_and_created_at_stays(org: Organisation) -> None:
    widget = Widget.objects.create(organisation=org, label="a")
    created, updated = widget.created_at, widget.updated_at
    Widget.objects.filter(pk=widget.pk).update(updated_at=updated - timedelta(minutes=5))
    widget.refresh_from_db()
    widget.label = "b"
    widget.save()
    widget.refresh_from_db()
    assert widget.created_at == created
    assert widget.updated_at > updated - timedelta(minutes=5)


@pytest.mark.django_db
def test_soft_delete_keeps_the_row_and_restore_clears_it(org: Organisation) -> None:
    widget = Widget.objects.create(organisation=org, label="a")
    widget.soft_delete()
    widget.refresh_from_db()
    assert widget.is_deleted is True
    assert widget.deleted_at is not None
    assert Widget.objects.filter(pk=widget.pk).exists()  # row is kept
    widget.restore()
    widget.refresh_from_db()
    assert widget.deleted_at is None and widget.is_deleted is False


@pytest.mark.django_db
def test_soft_delete_is_idempotent(org: Organisation) -> None:
    widget = Widget.objects.create(organisation=org, label="a")
    widget.soft_delete()
    first = widget.deleted_at
    widget.soft_delete()
    widget.refresh_from_db()
    assert widget.deleted_at == first


@pytest.mark.django_db
def test_soft_delete_saves_only_its_own_fields(org: Organisation) -> None:
    widget = Widget.objects.create(organisation=org, label="saved")
    widget.label = "unsaved edit"
    widget.soft_delete()
    widget.refresh_from_db()
    assert widget.label == "saved"
    assert widget.is_deleted


@pytest.mark.django_db
def test_owning_organisation_and_creator_cannot_be_deleted(org: Organisation, user: User) -> None:
    Widget.objects.create(organisation=org, created_by=user, label="a")
    with pytest.raises(ProtectedError):
        org.delete()
    with pytest.raises(ProtectedError):
        user.delete()


@pytest.mark.django_db
def test_reverse_accessor_per_subclass(org: Organisation) -> None:
    Widget.objects.create(organisation=org, label="w")
    Gadget.objects.create(organisation=org, label="g")
    assert org.testapp_widget_set.count() == 1
    assert org.testapp_gadget_set.count() == 1
