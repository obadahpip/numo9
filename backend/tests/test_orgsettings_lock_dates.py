"""A-05-T04 — the LockDate model (per-module lock dates at two levels) and its history.

Acceptance: the migration creates the table. Also: six modules (GL, AR, AP, Bank, Payroll, Tax)
× two levels (everyone except advisers, everyone), one row each per organisation (database);
a lock moved back — an earlier date, or removed — needs a reason; the everyone lock is never later
than the advisers-only lock of the same module; module and level never change; every change is
in the audit log with old and new date and reason and its author, so the lock's history can be
read back (gap-44).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction

from numo9.accounts.models import User
from numo9.audit.context import audit_context
from numo9.audit.models import ActorKind, AuditEvent
from numo9.orgsettings.models import REASON_MAX, LockDate, LockLevel, LockModule
from numo9.tenancy.context import TenantContextMissing, org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db

JUNE_30 = dt.date(2026, 6, 30)
MARCH_31 = dt.date(2026, 3, 31)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def lock(
    org: Organisation,
    module: str = LockModule.GL,
    level: str = LockLevel.ADVISERS_ONLY,
    date: dt.date | None = JUNE_30,
    reason: str = "",
) -> LockDate:
    item = LockDate(organisation=org, module=module, level=level, date=date, reason=reason)
    item.save()
    return item


def codes(excinfo: pytest.ExceptionInfo[ValidationError], field: str) -> list[str]:
    return [str(e.code) for e in excinfo.value.error_dict[field]]


# ---- acceptance: migration ----------------------------------------------------------------------


def test_migration_creates_the_table() -> None:
    assert "orgsettings_lockdate" in connection.introspection.table_names()
    out = StringIO()
    call_command("makemigrations", "orgsettings", "--check", "--dry-run", stdout=out)
    assert "No changes detected" in out.getvalue()


# ---- modules and levels -------------------------------------------------------------------------


def test_six_modules_and_two_levels() -> None:
    assert set(LockModule.values) == {"gl", "ar", "ap", "bank", "payroll", "tax"}
    assert set(LockLevel.values) == {"advisers_only", "everyone"}


@pytest.mark.gap("gap-44")
def test_every_module_can_be_locked_at_both_levels(org: Organisation) -> None:
    for module in LockModule.values:
        lock(org, module, LockLevel.EVERYONE, MARCH_31)
        lock(org, module, LockLevel.ADVISERS_ONLY, JUNE_30)
    assert LockDate.objects.count() == 12


def test_one_module_locked_while_another_is_open(org: Organisation) -> None:
    lock(org, LockModule.AP, date=JUNE_30)
    assert not LockDate.objects.filter(module=LockModule.GL).exists()


def test_one_row_per_module_and_level(org: Organisation) -> None:
    lock(org)
    with pytest.raises(IntegrityError), transaction.atomic():
        LockDate.objects.bulk_create(
            [LockDate(organisation=org, module=LockModule.GL, level=LockLevel.ADVISERS_ONLY)]
        )


def test_a_soft_deleted_lock_frees_its_slot(org: Organisation) -> None:
    lock(org).soft_delete()
    lock(org, date=MARCH_31)


def test_database_refuses_unknown_module_and_level(org: Organisation) -> None:
    item = lock(org)
    for update in ({"module": "inventory"}, {"level": "admins"}):
        with pytest.raises(IntegrityError), transaction.atomic():
            LockDate.objects.filter(pk=item.pk).update(**update)


def test_unknown_module_is_refused_on_save(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        lock(org, module="inventory")
    assert "module" in excinfo.value.error_dict


def test_an_empty_date_means_not_locked(org: Organisation) -> None:
    item = lock(org, date=None)
    assert item.date is None


# ---- moving a lock ------------------------------------------------------------------------------


def test_moving_a_lock_forward_needs_no_reason(org: Organisation) -> None:
    item = lock(org, date=MARCH_31)
    item.set_lock(JUNE_30)
    item.save()
    item.refresh_from_db()
    assert item.date == JUNE_30


def test_moving_a_lock_back_needs_a_reason(org: Organisation) -> None:
    item = lock(org, date=JUNE_30)
    item.set_lock(MARCH_31, "  ")
    with pytest.raises(ValidationError) as excinfo:
        item.save()
    assert codes(excinfo, "reason") == ["orgsettings.lock.reason_required"]
    assert "2026-06-30" in excinfo.value.error_dict["reason"][0].messages[0]
    item.set_lock(MARCH_31, "Correcting a May supplier bill")
    item.save()
    item.refresh_from_db()
    assert (item.date, item.reason) == (MARCH_31, "Correcting a May supplier bill")


def test_removing_a_lock_needs_a_reason(org: Organisation) -> None:
    item = lock(org, date=JUNE_30)
    item.set_lock(None)
    with pytest.raises(ValidationError) as excinfo:
        item.save()
    assert codes(excinfo, "reason") == ["orgsettings.lock.reason_required"]
    item.set_lock(None, "Year-end adjustments by the accountant")
    item.save()


def test_reason_has_a_maximum_length(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        lock(org, reason="x" * (REASON_MAX + 1))
    assert "reason" in excinfo.value.error_dict


def test_module_and_level_never_change(org: Organisation) -> None:
    item = lock(org)
    item.module = LockModule.AP
    with pytest.raises(ValidationError) as excinfo:
        item.save()
    assert codes(excinfo, "module") == ["orgsettings.lock.immutable"]


# ---- levels in order ----------------------------------------------------------------------------


def test_everyone_lock_may_equal_or_precede_the_advisers_lock(org: Organisation) -> None:
    lock(org, level=LockLevel.ADVISERS_ONLY, date=JUNE_30)
    lock(org, level=LockLevel.EVERYONE, date=JUNE_30)
    lock(org, LockModule.AR, LockLevel.ADVISERS_ONLY, JUNE_30)
    lock(org, LockModule.AR, LockLevel.EVERYONE, MARCH_31)


def test_everyone_lock_after_the_advisers_lock_is_refused(org: Organisation) -> None:
    lock(org, level=LockLevel.ADVISERS_ONLY, date=MARCH_31)
    with pytest.raises(ValidationError) as excinfo:
        lock(org, level=LockLevel.EVERYONE, date=JUNE_30)
    assert codes(excinfo, "date") == ["orgsettings.lock.levels_out_of_order"]


def test_advisers_lock_before_the_everyone_lock_is_refused(org: Organisation) -> None:
    lock(org, level=LockLevel.EVERYONE, date=JUNE_30)
    item = lock(org, level=LockLevel.ADVISERS_ONLY, date=JUNE_30)
    item.set_lock(MARCH_31, "Reopen Q2 for advisers")
    with pytest.raises(ValidationError) as excinfo:
        item.save()
    assert codes(excinfo, "date") == ["orgsettings.lock.levels_out_of_order"]


def test_levels_of_other_modules_are_independent(org: Organisation) -> None:
    lock(org, LockModule.GL, LockLevel.ADVISERS_ONLY, MARCH_31)
    lock(org, LockModule.AP, LockLevel.EVERYONE, JUNE_30)


# ---- scoping, audit and history -----------------------------------------------------------------


def test_lock_dates_are_scoped_to_the_active_organisation(org: Organisation) -> None:
    lock(org)
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        assert LockDate.objects.count() == 0
        lock(other)
    with org_context(None), pytest.raises(TenantContextMissing):
        LockDate.objects.count()


@pytest.mark.gap("gap-44")
def test_lock_history_is_read_from_the_audit_log(org: Organisation) -> None:
    user = User.objects.create_user("jo@practice.ca", password="x" * 12, name="Jo Accountant")
    actor = {"kind": ActorKind.USER, "user": user, "label": "Jo Accountant (jo@practice.ca)"}
    with audit_context(**actor):
        item = lock(org, date=MARCH_31, reason="Q1 closed")
        item.set_lock(JUNE_30, "Q2 closed")
        item.save()
        item.set_lock(MARCH_31, "Correcting a May supplier bill")
        item.save()
    history = list(
        AuditEvent.objects.filter(
            object_type="orgsettings.LockDate", object_id=str(item.public_id)
        ).order_by("id")
    )
    assert [e.action for e in history] == [
        "orgsettings.lockdate.created",
        "orgsettings.lockdate.updated",
        "orgsettings.lockdate.updated",
    ]
    assert history[0].changes == {
        "module": [None, "gl"],
        "level": [None, "advisers_only"],
        "date": [None, "2026-03-31"],
        "reason": [None, "Q1 closed"],
    }
    assert history[2].changes == {
        "date": ["2026-06-30", "2026-03-31"],
        "reason": ["Q2 closed", "Correcting a May supplier bill"],
    }
    assert {e.actor_label for e in history} == {"Jo Accountant (jo@practice.ca)"}
    assert history[0].object_label == "General ledger — Everyone except advisers"
