"""Renumber an account (C-01-T07): code change, conflict check, audit, cache bust.

Every record that refers to an account (sub-accounts, journal lines, items, bank accounts,
defaults) holds its id, never its code, so renumbering changes one field and every reference
stays as it was; reports read codes through the chart (``numo9.ledger.cache``), whose cache is
busted, so they show the new code at once. System accounts can be renumbered too — into the
organisation's own scheme (gap-29).

The change is written as one audit event ``ledger.account.renumbered`` with
``{"code": [old, new]}``, attributed to the person (or job) making it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from numo9.audit.context import audit_context, user_label
from numo9.audit.mixins import raw_state
from numo9.audit.models import ActorKind
from numo9.audit.service import record

from .cache import bust_now_and_on_commit
from .models import ACCOUNT_CODE, Account, LedgerError

RENUMBERED = "ledger.account.renumbered"


@contextmanager
def acting_as(actor: Any) -> Iterator[None]:
    """Attribute the block's audit events to ``actor`` (a user) when one is given."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        with nullcontext():
            yield
        return
    with audit_context(kind=ActorKind.USER.value, user=actor, label=user_label(actor)):
        yield


def _code_taken(code: str, holder: Account) -> LedgerError:
    return LedgerError(
        _("Code %(code)s is already used by %(account)s. Choose another code."),
        code="ledger.account.code_taken",
        params={"code": code, "account": str(holder)},
    )


def renumber_account(account: Account, new_code: str, *, actor: Any = None) -> Account:
    """Give ``account`` the code ``new_code``; refuse a code another account of the
    organisation already has (codes are compared without case)."""
    code = (new_code or "").strip()
    if not ACCOUNT_CODE.match(code):
        raise LedgerError(
            _(
                "An account code is 1 to 10 letters, digits, dots or dashes, starting with a "
                "letter or a digit (e.g. 6100)."
            ),
            code="ledger.account.code_invalid",
        )
    manager = Account._base_manager
    with transaction.atomic():
        locked = manager.select_for_update().get(pk=account.pk)
        old = locked.code
        if old == code:
            return account
        holder = (
            manager.filter(organisation_id=locked.organisation_id, code__iexact=code)
            .exclude(pk=locked.pk)
            .first()
        )
        if holder is not None:
            raise _code_taken(code, holder)
        now = timezone.now()
        try:
            with transaction.atomic():
                manager.filter(pk=locked.pk).update(code=code, updated_at=now)
        except IntegrityError as exc:  # a concurrent renumber took the code first
            holder = manager.filter(
                organisation_id=locked.organisation_id, code__iexact=code
            ).first()
            raise _code_taken(code, holder or locked) from exc
        account.code = code
        account.updated_at = now
        with acting_as(actor):
            record(RENUMBERED, obj=account, changes={"code": [old, code]})
        account._audit_before = raw_state(account)
        bust_now_and_on_commit(locked.organisation_id)
    return account
