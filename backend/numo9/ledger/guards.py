"""System-role guard (C-01-T06).

A system account is the account the engine posts to for a role (Accounts receivable, GST/HST
payable, Retained earnings…). Rules, checked on every save and delete:

- **one account per role** per organisation (also a database constraint): a second account with
  the role is refused naming the account that has it;
- the role fits the account's sub-type (``ROLE_SUBTYPES``: AR is a Current asset, GST/HST payable
  a Sales tax control…);
- once saved, a system account's **role, type and sub-type never change**;
- a system account **can't be archived or deleted** (soft or hard, one by one or in bulk): the
  error names the role. Its **code and name may change** — renumbering into the organisation's
  own scheme is allowed (gap-29, C-01-T07).

Any account with transactions can't be deleted either (archive it, C-01-T08).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models
from django.utils.translation import gettext_lazy as _

from .postings import has_postings

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise

    from .models import Account


def _models() -> Any:
    from . import models as ledger_models

    return ledger_models


def _error(message: StrOrPromise, code: str, **params: object) -> Exception:
    from .models import LedgerError

    return LedgerError(message, code=code, params=params or None)


def _role_label(role: str) -> str:
    return str(_models().SystemRole(role).label)


def check_system_role_rules(account: Account) -> None:
    m = _models()
    if account.system_role:
        if account.system_role not in m.SystemRole.values:
            raise _error(_("Unknown system role."), "ledger.account.system_role_invalid")
        if account.subtype not in m.ROLE_SUBTYPES[account.system_role]:
            raise _error(
                _("The %(role)s account must have the sub-type %(subtypes)s."),
                "ledger.account.system_role_subtype",
                role=_role_label(account.system_role),
                subtypes=", ".join(
                    str(m.AccountSubtype(s).label)
                    for s in sorted(m.ROLE_SUBTYPES[account.system_role])
                ),
            )
        holder = (
            m.Account._base_manager.filter(
                organisation_id=account.organisation_id, system_role=account.system_role
            )
            .exclude(pk=account.pk)
            .first()
        )
        if holder is not None:
            raise _error(
                _("%(account)s is already the %(role)s account: there is one per organisation."),
                "ledger.account.system_role_taken",
                account=str(holder),
                role=_role_label(account.system_role),
            )
    if account.pk is None:
        return
    stored = (
        m.Account._base_manager.filter(pk=account.pk)
        .values("system_role", "type", "subtype", "status", "deleted_at")
        .first()
    )
    if stored is None or not stored["system_role"]:
        return
    role = _role_label(stored["system_role"])
    if account.system_role != stored["system_role"]:
        raise _error(
            _("This is the %(role)s account: its system role can't be changed or removed."),
            "ledger.account.system_role_locked",
            role=role,
        )
    if account.type != stored["type"] or account.subtype != stored["subtype"]:
        raise _error(
            _("This is the %(role)s account: its type and sub-type can't change."),
            "ledger.account.system_type_locked",
            role=role,
        )
    if account.status == m.AccountStatus.ARCHIVED and stored["status"] != account.status:
        raise _error(
            _("%(account)s is the %(role)s account: system accounts can't be archived."),
            "ledger.account.system_archive",
            account=str(account),
            role=role,
        )
    if account.deleted_at is not None and stored["deleted_at"] is None:
        raise _error(
            _("%(account)s is the %(role)s account: system accounts can't be deleted."),
            "ledger.account.system_delete",
            account=str(account),
            role=role,
        )


def refuse_delete(account: Account) -> None:
    if account.system_role:
        raise _error(
            _("%(account)s is the %(role)s account: system accounts can't be deleted."),
            "ledger.account.system_delete",
            account=str(account),
            role=_role_label(account.system_role),
        )
    if has_postings(account):
        raise _error(
            _("%(account)s has transactions: archive it instead of deleting it."),
            "ledger.account.delete_has_postings",
            account=str(account),
        )


def refuse_bulk_delete(queryset: models.QuerySet[Account]) -> None:
    system = queryset.exclude(system_role="").first()
    if system is not None:
        refuse_delete(system)
    for account in queryset.iterator():
        if has_postings(account):
            refuse_delete(account)
