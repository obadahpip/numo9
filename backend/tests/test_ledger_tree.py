"""C-01-T03 — tree constraints: depth ≤ 4, same type family, post-to-leaf rule.

Acceptance: an invalid parent is rejected. Covered: a parent of another type, a fifth level
(also when moving a subtree), cycles, a parent in another organisation, a system or archived
parent, a parent that already has transactions (C-02 probe), type change of a parent, and
``assert_postable`` refusing parents and archived accounts.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.ledger import tree
from numo9.ledger.models import Account, LedgerError
from numo9.ledger.postings import register_posting_probe, unregister_posting_probe
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def code_of(error: pytest.ExceptionInfo[LedgerError]) -> str | None:
    return error.value.code


def test_sub_accounts_of_the_same_type(org: Organisation) -> None:
    vehicles = account(org, "6210", "Vehicle expenses")
    fuel = account(org, "6211", "Fuel", parent=vehicles)
    assert fuel.parent == vehicles
    assert tree.depth(fuel) == 2
    assert not tree.is_leaf(vehicles)
    assert tree.is_leaf(fuel)


def test_parent_of_another_type_rejected(org: Organisation) -> None:
    bank = account(org, "1010", "Chequing", "bank")
    with pytest.raises(LedgerError) as error:
        account(org, "6100", "Office", parent=bank)
    assert code_of(error) == "ledger.account.parent_type_mismatch"
    # Same type, different sub-type is fine (a family is the type).
    current = account(org, "1100", "Receivables", "current_asset")
    assert account(org, "1101", "Holdbacks", "current_asset", parent=current).pk
    prepaid = account(org, "1300", "Prepaid", "prepayment", parent=current)
    assert prepaid.parent_id == current.pk


def test_depth_four_allowed_five_rejected(org: Organisation) -> None:
    level1 = account(org, "6000", "Level 1")
    level2 = account(org, "6001", "Level 2", parent=level1)
    level3 = account(org, "6002", "Level 3", parent=level2)
    level4 = account(org, "6003", "Level 4", parent=level3)
    assert tree.depth(level4) == 4
    with pytest.raises(LedgerError) as error:
        account(org, "6004", "Level 5", parent=level4)
    assert code_of(error) == "ledger.account.too_deep"


def test_moving_a_subtree_counts_its_levels(org: Organisation) -> None:
    a = account(org, "6000", "A")
    b = account(org, "6001", "B", parent=a)
    account(org, "6002", "C", parent=b)  # A > B > C
    x = account(org, "6100", "X")
    y = account(org, "6101", "Y", parent=x)  # X > Y
    a.parent = y  # X > Y > A > B > C = 5 levels
    with pytest.raises(LedgerError) as error:
        a.save()
    assert code_of(error) == "ledger.account.too_deep"
    a.parent = x  # X > A > B > C = 4 levels
    a.save()
    assert tree.depth(Account.objects.get(code="6002")) == 4


def test_cycles_rejected(org: Organisation) -> None:
    a = account(org, "6000", "A")
    b = account(org, "6001", "B", parent=a)
    a.parent = b
    with pytest.raises(LedgerError) as error:
        a.save()
    assert code_of(error) == "ledger.account.parent_cycle"
    a.parent = a
    with pytest.raises(LedgerError) as error:
        a.save()
    assert code_of(error) == "ledger.account.parent_cycle"


def test_parent_in_another_org_rejected(org: Organisation) -> None:
    other = Organisation.objects.create(name="Other Ltd.")
    with org_context(other):
        foreign = account(other, "6000", "Theirs")
    with pytest.raises(LedgerError) as error:
        account(org, "6001", "Mine", parent=foreign)
    assert code_of(error) == "ledger.account.parent_missing"


def test_system_account_cannot_be_a_parent(org: Organisation) -> None:
    ar = account(org, "1100", "Accounts receivable", "current_asset", system_role="ar")
    with pytest.raises(LedgerError) as error:
        account(org, "1101", "AR — retail", "current_asset", parent=ar)
    assert code_of(error) == "ledger.account.parent_is_system"
    parent = account(org, "1150", "Advances", "current_asset")
    account(org, "1151", "Advance — Ana", "current_asset", parent=parent)
    parent.system_role = "itc_receivable"
    with pytest.raises(LedgerError) as error:
        parent.save()
    assert code_of(error) == "ledger.account.parent_is_system"


def test_archived_parent_rejected(org: Organisation) -> None:
    old = account(org, "6900", "Old", status="archived")
    with pytest.raises(LedgerError) as error:
        account(org, "6901", "Child", parent=old)
    assert code_of(error) == "ledger.account.parent_archived"


def test_parent_with_transactions_rejected(org: Organisation) -> None:
    posted = account(org, "6100", "Office supplies")

    def probe(item: Account) -> bool:
        return item.pk == posted.pk

    register_posting_probe(probe)
    try:
        with pytest.raises(LedgerError) as error:
            account(org, "6101", "Paper", parent=posted)
        assert code_of(error) == "ledger.account.parent_has_postings"
    finally:
        unregister_posting_probe(probe)
    assert account(org, "6101", "Paper", parent=posted).pk  # without transactions: fine


def test_parent_type_locked_while_it_has_children(org: Organisation) -> None:
    parent = account(org, "4000", "Sales", "revenue")
    account(org, "4001", "Sales — retail", "revenue", parent=parent)
    parent.subtype, parent.type = "operating_expense", "expense"
    with pytest.raises(LedgerError) as error:
        parent.save()
    assert code_of(error) == "ledger.account.type_locked_by_children"


def test_assert_postable_only_leaf_active(org: Organisation) -> None:
    parent = account(org, "6210", "Vehicle expenses")
    child = account(org, "6211", "Fuel", parent=parent)
    tree.assert_postable(child)
    with pytest.raises(LedgerError) as error:
        tree.assert_postable(parent)
    assert code_of(error) == "ledger.account.not_leaf"
    child.status = "archived"
    child.save()
    with pytest.raises(LedgerError) as error:
        tree.assert_postable(child)
    assert code_of(error) == "ledger.account.archived"
    # With its only child archived... still a parent (archived children keep the hierarchy).
    assert not tree.is_leaf(parent)
