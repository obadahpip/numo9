"""C-01-T07 — renumber service: code change, conflict check, audit, cache bust.

Acceptance: every reference (by foreign key) is unchanged and reports show the new code. Also: a
code another account has (any case) is refused naming that account; system accounts renumber;
one audit event with old → new attributed to the person; the cached chart shows the new code at
once; no-op and invalid codes; isolation between organisations.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.audit.presenter import action_label
from numo9.ledger.cache import chart_rows, chart_version
from numo9.ledger.models import Account, LedgerError
from numo9.ledger.renumber import RENUMBERED, renumber_account
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account
from tests.testapp.models import AccountDefault

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def clerk() -> User:
    return User.objects.create_user("clerk@maple.example", name="Sam Clerk")


def codes(org: Organisation) -> dict[str, str]:
    return {row["id"]: row["code"] for row in chart_rows(org)}


def test_references_unchanged_and_reports_show_new_code(org: Organisation) -> None:
    ar = account(org, "610", "Accounts receivable", "current_asset", system_role="ar")
    parent = account(org, "6210", "Vehicle expenses")
    fuel = account(org, "6211", "Fuel", parent=parent)
    default = AccountDefault.objects.create(label="Sales default receivable", account=ar)
    before = codes(org)  # cached chart, as reports read it
    assert before[str(ar.public_id)] == "610"

    renumber_account(ar, "1100")  # system account into the 4-digit scheme (gap-29)
    renumber_account(parent, "6300")

    default.refresh_from_db()
    fuel.refresh_from_db()
    assert default.account_id == ar.pk  # reference by id: untouched
    assert fuel.parent_id == parent.pk
    after = codes(org)
    assert after[str(ar.public_id)] == "1100"
    assert after[str(parent.public_id)] == "6300"
    assert Account.objects.get(pk=ar.pk).code == "1100"


def test_conflict_names_the_other_account(org: Organisation) -> None:
    account(org, "1010", "Chequing account", "bank")
    savings = account(org, "1020", "Savings", "bank")
    for taken in ("1010", " 1010 "):
        with pytest.raises(LedgerError) as error:
            renumber_account(savings, taken)
        assert error.value.code == "ledger.account.code_taken"
        assert "1010 · Chequing account" in error.value.messages[0]
    letters = account(org, "AB-1", "Float", "current_asset")
    with pytest.raises(LedgerError):
        renumber_account(savings, "ab-1")  # codes compare without case
    savings.refresh_from_db()
    assert savings.code == "1020" and letters.code == "AB-1"


def test_invalid_code_refused(org: Organisation) -> None:
    rent = account(org, "6130", "Rent")
    with pytest.raises(LedgerError) as error:
        renumber_account(rent, "61 30")
    assert error.value.code == "ledger.account.code_invalid"


def test_one_audit_event_attributed_to_the_person(org: Organisation, clerk: User) -> None:
    rent = account(org, "6130", "Rent")
    renumber_account(rent, "6135", actor=clerk)
    events = AuditEvent.objects.filter(object_id=str(rent.public_id)).order_by("id")
    assert [e.action for e in events] == ["ledger.account.created", RENUMBERED]
    event = events.last()
    assert event is not None
    assert event.changes == {"code": ["6130", "6135"]}
    assert event.actor_user_id == clerk.pk
    assert action_label(RENUMBERED) == "Account renumbered"
    # The instance is current: a later save doesn't record the code change again.
    rent.set_name("Rent — shop")
    rent.save()
    last = AuditEvent.objects.filter(object_id=str(rent.public_id)).order_by("id").last()
    assert last is not None and set(last.changes) == {"name_i18n"}


def test_same_code_is_a_no_op(org: Organisation) -> None:
    rent = account(org, "6130", "Rent")
    version = chart_version(org.pk)
    renumber_account(rent, "6130")
    assert not AuditEvent.objects.filter(action=RENUMBERED).exists()
    assert chart_version(org.pk) == version


def test_cache_busted_by_any_account_change(org: Organisation) -> None:
    rent = account(org, "6130", "Rent")
    chart_rows(org)
    version = chart_version(org.pk)
    renumber_account(rent, "6131")
    assert chart_version(org.pk) > version
    version = chart_version(org.pk)
    rent.set_name("Shop rent")
    rent.save()
    assert chart_version(org.pk) > version
    assert [row["name"] for row in chart_rows(org)] == ["Shop rent"]


def test_other_organisation_unaffected(org: Organisation) -> None:
    other = Organisation.objects.create(name="Other Ltd.")
    with org_context(other):
        theirs = account(other, "6130", "Their rent")
        their_rows = chart_rows(other)
    mine = account(org, "6100", "Office")
    renumber_account(mine, "6130")  # free in this organisation, taken only in the other one
    with org_context(other):
        assert Account.objects.get(pk=theirs.pk).code == "6130"
        assert chart_rows(other) == their_rows


def test_chart_rows_in_tree_order(org: Organisation) -> None:
    expense = account(org, "6210", "Vehicle expenses")
    account(org, "6212", "Parking", parent=expense)
    account(org, "6211", "Fuel", parent=expense)
    account(org, "1010", "Chequing", "bank")
    account(org, "4000", "Sales", "revenue")
    rows = chart_rows(org)
    assert [(r["code"], r["depth"], r["postable"]) for r in rows] == [
        ("1010", 1, True),
        ("4000", 1, True),
        ("6210", 1, False),
        ("6211", 2, True),
        ("6212", 2, True),
    ]
