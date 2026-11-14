"""Audit service record() and the AuditedModel mixin (A-04-T03).

Acceptance: editing an amount shows the old and the new value in the audit log. Also: creation
lists the given fields, nothing changed → no event, soft delete / restore / delete are their own
actions, related records are named by public id and label, masked fields (encrypted, by name, by
the model's list) never reach the log, the event rolls back with the change, and role changes
announced by A-03 are stored with their diff.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.db import connection, transaction

from numo9.accounts.models import User
from numo9.audit.models import ActorKind, AuditEvent
from numo9.audit.service import MASKED, MAX_VALUE_CHARS, clean_changes, plain, record
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, Practice
from tests.testapp.models import AuditedInvoice, Widget

pytestmark = pytest.mark.django_db

INVOICE = "tests.testapp.AuditedInvoice"


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


def events(org: Organisation, **filters: object) -> list[AuditEvent]:
    with org_context(org):
        return list(AuditEvent.objects.filter(**filters).order_by("id"))


def invoice(org: Organisation, **fields: object) -> AuditedInvoice:
    values: dict[str, object] = {"number": "INV-101", "amount": Decimal("100.00")}
    values.update(fields)
    with org_context(org):
        created: AuditedInvoice = AuditedInvoice.objects.create(**values)
    return created


# ---- acceptance: the amount's old and new value ---------------------------------------------


def test_editing_an_amount_shows_old_and_new(org: Organisation) -> None:
    inv = invoice(org)
    with org_context(org):
        loaded = AuditedInvoice.objects.get(pk=inv.pk)
        loaded.amount = Decimal("120.50")
        loaded.save()
    updated = events(org, action="testapp.auditedinvoice.updated")
    assert len(updated) == 1
    assert updated[0].changes == {"amount": ["100.00", "120.50"]}
    assert updated[0].object_type == "testapp.AuditedInvoice"
    assert updated[0].object_id == str(inv.public_id)
    assert updated[0].object_label == "Invoice INV-101"


def test_creation_lists_the_given_fields(org: Organisation) -> None:
    inv = invoice(org, notes="Net 30")
    (created,) = events(org, action="testapp.auditedinvoice.created")
    assert created.changes == {
        "amount": [None, "100.00"],
        "notes": [None, "Net 30"],
        "number": [None, "INV-101"],
    }
    assert created.object_id == str(inv.public_id)
    assert created.organisation == org


def test_saving_without_a_change_writes_nothing(org: Organisation) -> None:
    inv = invoice(org)
    with org_context(org):
        inv.save()
        AuditedInvoice.objects.get(pk=inv.pk).save()
    assert [e.action for e in events(org)] == ["testapp.auditedinvoice.created"]


def test_several_saves_each_diff_from_the_previous(org: Organisation) -> None:
    inv = invoice(org)
    with org_context(org):
        inv.amount = Decimal("110.00")
        inv.save()
        inv.amount = Decimal("90.00")
        inv.number = "INV-101-1"
        inv.save()
    updates = [e.changes for e in events(org, action="testapp.auditedinvoice.updated")]
    assert updates == [
        {"amount": ["100.00", "110.00"]},
        {"amount": ["110.00", "90.00"], "number": ["INV-101", "INV-101-1"]},
    ]


def test_save_after_refresh_diffs_from_the_reloaded_values(org: Organisation) -> None:
    inv = invoice(org)
    with org_context(org):
        AuditedInvoice.objects.filter(pk=inv.pk).update(amount=Decimal("120.00"))  # elsewhere
        inv.refresh_from_db()
        inv.amount = Decimal("130.00")
        inv.save()
        AuditedInvoice.objects.filter(pk=inv.pk).update(number="INV-7", notes="n")
        inv.refresh_from_db(fields=["number"])  # partial: only number is reloaded
        inv.number = "INV-8"
        inv.save()
    updates = [e.changes for e in events(org, action="testapp.auditedinvoice.updated")]
    assert updates == [{"amount": ["120.00", "130.00"]}, {"number": ["INV-7", "INV-8"]}]


def test_update_fields_compares_only_the_saved_fields(org: Organisation) -> None:
    inv = invoice(org)
    with org_context(org):
        inv.amount = Decimal("1.00")
        inv.notes = "not saved"
        inv.save(update_fields=["amount", "updated_at"])
    (updated,) = events(org, action="testapp.auditedinvoice.updated")
    assert updated.changes == {"amount": ["100.00", "1.00"]}


def test_row_saved_without_loading_is_compared_with_the_database(org: Organisation) -> None:
    inv = invoice(org)
    with org_context(org):
        detached = AuditedInvoice(
            pk=inv.pk,
            organisation=org,
            public_id=inv.public_id,
            number="INV-101",
            amount=Decimal("75.00"),
            created_at=inv.created_at,
        )
        detached._state.adding = False
        detached.save()
    (updated,) = events(org, action="testapp.auditedinvoice.updated")
    assert updated.changes == {"amount": ["100.00", "75.00"]}


# ---- deletes ---------------------------------------------------------------------------------


def test_soft_delete_and_restore_are_actions(org: Organisation) -> None:
    inv = invoice(org)
    with org_context(org):
        inv.soft_delete()
        inv.restore()
    assert [e.action for e in events(org)] == [
        "testapp.auditedinvoice.created",
        "testapp.auditedinvoice.deleted",
        "testapp.auditedinvoice.restored",
    ]


def test_hard_delete_keeps_the_last_values(org: Organisation) -> None:
    inv = invoice(org)
    public_id = inv.public_id
    with org_context(org):
        inv.delete()
    (deleted,) = events(org, action="testapp.auditedinvoice.deleted")
    assert deleted.object_id == str(public_id)
    assert deleted.changes["amount"] == ["100.00", None]


# ---- related records and masking ------------------------------------------------------------


def test_related_record_is_named_by_public_id_and_label(org: Organisation) -> None:
    with org_context(org):
        old = Widget.objects.create(label="Old customer")
        new = Widget.objects.create(label="New customer")
    inv = invoice(org, customer=old)
    with org_context(org):
        inv.customer = new
        inv.save()
    (updated,) = events(org, action="testapp.auditedinvoice.updated")
    old_ref, new_ref = updated.changes["customer"]
    assert old_ref["id"] == str(old.public_id) and new_ref["id"] == str(new.public_id)
    assert {old_ref["label"], new_ref["label"]} <= {str(old), str(new)}


def test_masked_fields_never_reach_the_log(org: Organisation) -> None:
    inv = invoice(org, payee_sin="046454286", bank_account="00123-004-1234567", internal_code="X1")
    with org_context(org):
        inv.payee_sin = "130692544"
        inv.bank_account = "99999-001-7654321"
        inv.internal_code = "X2"
        inv.save()
    created, updated = events(org)
    for event in (created, updated):
        for name in ("payee_sin", "bank_account", "internal_code"):
            assert event.changes[name] == [MASKED, MASKED]
    with connection.cursor() as cursor:
        cursor.execute("SELECT changes::text FROM audit_event")
        stored = " ".join(row[0] for row in cursor.fetchall())
    for secret in ("046454286", "130692544", "1234567", "7654321", "X1", "X2"):
        assert secret not in stored


def test_excluded_field_is_not_audited(org: Organisation) -> None:
    inv = invoice(org)
    with org_context(org):
        inv.search_text = "maple leaf invoice"
        inv.save()
    assert events(org, action="testapp.auditedinvoice.updated") == []


def test_record_masks_sensitive_names_given_directly(org: Organisation) -> None:
    event = record("tests.manual", organisation=org, changes={"sin": ["046454286", "130692544"]})
    assert event.changes == {"sin": [MASKED, MASKED]}


# ---- record() ----------------------------------------------------------------------------------


def test_event_rolls_back_with_the_change(org: Organisation) -> None:
    with pytest.raises(RuntimeError), transaction.atomic(), org_context(org):
        AuditedInvoice.objects.create(number="INV-9", amount=Decimal("9.00"))
        raise RuntimeError("change failed")
    assert events(org) == []


def test_record_names_the_actor(org: Organisation) -> None:
    user = User.objects.create_user("ines@example.com", name="Inès Tremblay")
    event = record("tests.manual", organisation=org, actor=user)
    assert event.actor_kind == ActorKind.USER and event.actor_user == user
    assert event.actor_label == "Inès Tremblay (ines@example.com)"
    assert record("tests.manual", organisation=org).actor_label == "System"


def test_record_defaults_to_the_active_organisation(org: Organisation) -> None:
    with org_context(org):
        event = record("tests.manual", object_type="tests.Thing", object_id="1")
    assert event.organisation == org


def test_values_are_stored_as_readable_json() -> None:
    long_text = "x" * (MAX_VALUE_CHARS + 5)
    assert plain(Decimal("1234.50")) == "1234.50"
    assert plain({1, 3, 2}) == [1, 2, 3]
    truncated = plain(long_text)
    assert truncated["truncated"] is True and truncated["length"] == MAX_VALUE_CHARS + 5
    json.dumps(clean_changes({"when": [None, Decimal("1.00")]}))


def test_changes_must_be_pairs() -> None:
    with pytest.raises(ValueError):
        clean_changes({"amount": ["1.00"]})


# ---- role changes (A-03-T15) are stored --------------------------------------------------------


def test_rbac_change_lands_in_the_log_with_its_diff(org: Organisation) -> None:
    from numo9.rbac.audit import record as rbac_record
    from numo9.rbac.models import Role

    user = User.objects.create_user("avery@example.com", name="Avery Owner")
    role = Role.objects.create(scope="organisation", organisation=org, name="Clerk", key="")
    rbac_record(
        "role.updated",
        actor=user,
        organisation=org,
        obj=role,
        label="Clerk",
        before={"name": "Clerk"},
        after={"name": "Senior clerk"},
    )
    (stored,) = events(org, action="role.updated")
    assert stored.changes == {"name": ["Clerk", "Senior clerk"]}
    assert stored.actor_user == user and stored.object_type == "rbac.Role"


def test_practice_role_change_is_a_practice_event() -> None:
    from numo9.rbac.audit import record as rbac_record
    from numo9.rbac.models import Role

    practice = Practice.objects.create(name="Lakeshore CPA")
    role = Role.objects.create(scope="practice", practice=practice, name="Junior", key="")
    rbac_record("role.created", actor=None, organisation=None, obj=role, label="Junior")
    stored = AuditEvent.platform_events.get(action="role.created")
    assert stored.organisation is None and stored.practice == practice
