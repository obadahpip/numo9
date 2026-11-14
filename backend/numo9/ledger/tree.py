"""Sub-account rules (C-01-T03): depth ≤ 4, same type family, posting only to leaf accounts.

An account may have a parent (its sub-accounts are listed and totalled under it). Rules checked
on every save (``Account.clean``):

- the parent is an account of the same organisation, not the account itself or one of its own
  sub-accounts (no cycles);
- **same type family**: the parent has the same type (Asset, Liability…) as the child; an
  account with sub-accounts can't change type;
- **depth ≤ 4**: a top-level account is level 1; moving an account moves its sub-accounts too,
  so the deepest of them must still be at level 4 or above;
- **post-to-leaf**: only accounts without sub-accounts take postings, so a parent is never a
  system account (the engine posts to those), an archived account, or an account that already has
  transactions (``has_postings``, C-02).

``assert_postable(account)`` is the check the posting engine (C-02) and document validators call.

Rows are read through the base manager filtered by organisation id: the rules hold outside a
request context too (template loads, imports, jobs).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _

from .postings import has_postings

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise

    from .models import Account

MAX_DEPTH = 4


def _base() -> type[Account]:
    from .models import Account

    return Account


def ancestors(account: Account) -> list[Account]:
    """The account's parents, nearest first (stops on a cycle in stored data)."""
    chain: list[Account] = []
    seen: set[int] = set()
    parent_id = account.parent_id
    while parent_id is not None and parent_id not in seen:
        seen.add(parent_id)
        parent = _base()._base_manager.filter(pk=parent_id).first()
        if parent is None:
            break
        chain.append(parent)
        parent_id = parent.parent_id
    return chain


def depth(account: Account) -> int:
    """Level of the account: 1 for a top-level account."""
    return 1 + len(ancestors(account))


def subtree_height(account: Account) -> int:
    """Levels in the account's own subtree: 1 for an account without sub-accounts."""
    if account.pk is None:
        return 1
    model = _base()
    height, level = 1, [account.pk]
    while True:
        level = list(model._base_manager.filter(parent_id__in=level).values_list("pk", flat=True))
        if not level:
            return height
        height += 1
        if height > MAX_DEPTH + 1:  # deeper than allowed already: enough to refuse
            return height


def has_children(account: Account) -> bool:
    if account.pk is None:
        return False
    return _base()._base_manager.filter(parent_id=account.pk, deleted_at__isnull=True).exists()


def is_leaf(account: Account) -> bool:
    return not has_children(account)


def _error(message: StrOrPromise, code: str, **params: object) -> Exception:
    from .models import LedgerError

    return LedgerError(message, code=code, params=params or None)


def check_tree_rules(account: Account) -> None:
    if account.pk is not None and has_children(account):
        model = _base()
        mismatched = (
            model._base_manager.filter(parent_id=account.pk).exclude(type=account.type).exists()
        )
        if mismatched:
            raise _error(
                _("%(account)s has sub-accounts: its type can't change."),
                "ledger.account.type_locked_by_children",
                account=str(account),
            )
        if account.system_role:
            raise _error(
                _("A system account takes postings, so it can't have sub-accounts."),
                "ledger.account.parent_is_system",
            )
    if account.parent_id is None:
        return
    parent = _base()._base_manager.filter(pk=account.parent_id).first()
    if parent is None or parent.organisation_id != account.organisation_id:
        raise _error(
            _("The parent account doesn't exist in this organisation."),
            "ledger.account.parent_missing",
        )
    if account.pk is not None and (
        parent.pk == account.pk or account.pk in {a.pk for a in ancestors(parent)}
    ):
        raise _error(
            _("An account can't be placed under itself or one of its own sub-accounts."),
            "ledger.account.parent_cycle",
        )
    if parent.type != account.type:
        raise _error(
            _("A sub-account has the same type as its parent (%(type)s)."),
            "ledger.account.parent_type_mismatch",
            type=parent.get_type_display(),
        )
    if parent.system_role:
        raise _error(
            _("%(account)s is a system account: it takes postings and can't have sub-accounts."),
            "ledger.account.parent_is_system",
            account=str(parent),
        )
    if parent.is_archived or parent.deleted_at is not None:
        raise _error(
            _("%(account)s is archived: it can't get new sub-accounts."),
            "ledger.account.parent_archived",
            account=str(parent),
        )
    if has_postings(parent):
        raise _error(
            _(
                "%(account)s has transactions, so it can't become a parent account: postings "
                "go only to accounts without sub-accounts."
            ),
            "ledger.account.parent_has_postings",
            account=str(parent),
        )
    if depth(parent) + subtree_height(account) > MAX_DEPTH:
        raise _error(
            _("Sub-accounts go at most %(max)d levels deep."),
            "ledger.account.too_deep",
            max=MAX_DEPTH,
        )


def assert_postable(account: Account) -> None:
    """Raise unless a journal line may post to the account (C-02 and document validators)."""
    if account.deleted_at is not None or account.is_archived:
        raise _error(
            _("%(account)s is archived: choose an active account."),
            "ledger.account.archived",
            account=str(account),
        )
    if has_children(account):
        raise _error(
            _("%(account)s has sub-accounts: post to one of its sub-accounts instead."),
            "ledger.account.not_leaf",
            account=str(account),
        )
