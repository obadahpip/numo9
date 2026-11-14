"""Cached chart of accounts per organisation, busted on every change (C-01-T07).

Lists, pickers and reports read the chart through ``chart_rows(organisation)`` — one cached list
per organisation, chart version and language. Any account save or delete bumps the
organisation's chart version (now and again when the transaction commits), so the next read
rebuilds the list: a renumbered account shows its new code everywhere at once.
"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import translation

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import Account, AccountType

TIMEOUT = 60 * 60 * 24
TYPE_ORDER = list(AccountType.values)


def _version_key(organisation_id: int) -> str:
    return f"ledger:chart:{organisation_id}:version"


def chart_version(organisation_id: int) -> int:
    key = _version_key(organisation_id)
    version = cache.get(key)
    if version is None:
        cache.add(key, 1, None)
        version = cache.get(key, 1)
    return int(version)


def bust_chart_cache(organisation_id: int) -> None:
    key = _version_key(organisation_id)
    try:
        cache.incr(key)
    except ValueError:  # not set yet (or evicted): any new value invalidates old entries
        cache.set(key, chart_version(organisation_id) + 1, None)


def bust_now_and_on_commit(organisation_id: int) -> None:
    bust_chart_cache(organisation_id)
    transaction.on_commit(lambda: bust_chart_cache(organisation_id))


@receiver(post_save, sender=Account, dispatch_uid="ledger_account_saved")
@receiver(post_delete, sender=Account, dispatch_uid="ledger_account_deleted")
def _account_changed(sender: type[Account], instance: Account, **kwargs: Any) -> None:
    bust_now_and_on_commit(instance.organisation_id)


def _build_rows(organisation: Organisation, language: str) -> list[dict[str, Any]]:
    with org_context(organisation):
        accounts = list(
            Account.objects.filter(deleted_at__isnull=True).select_related("parent", "gifi")
        )
    by_parent: dict[int | None, list[Account]] = {}
    for account in accounts:
        by_parent.setdefault(account.parent_id, []).append(account)
    for siblings in by_parent.values():
        siblings.sort(key=lambda a: (TYPE_ORDER.index(a.type), a.code.lower()))
    rows: list[dict[str, Any]] = []

    def walk(parent_id: int | None, level: int) -> None:
        for account in by_parent.get(parent_id, []):
            children = by_parent.get(account.pk, [])
            rows.append(
                {
                    "id": str(account.public_id),
                    "code": account.code,
                    "name": account.name_in(language),
                    "type": account.type,
                    "subtype": account.subtype,
                    "parent": str(account.parent.public_id) if account.parent else None,
                    "depth": level,
                    "system_role": account.system_role,
                    "is_bank": account.is_bank,
                    "gifi": account.gifi_id,
                    "default_tax_key": account.default_tax_key,
                    "status": account.status,
                    "postable": not children and not account.is_archived,
                }
            )
            walk(account.pk, level + 1)

    walk(None, 1)
    return rows


def chart_rows(organisation: Organisation) -> list[dict[str, Any]]:
    """The organisation's accounts in chart order (type, then code; sub-accounts under their
    parent), cached until the chart changes."""
    language = (translation.get_language() or "en-ca").lower()
    key = f"ledger:chart:{organisation.pk}:{chart_version(organisation.pk)}:{language}"
    rows: list[dict[str, Any]] | None = cache.get(key)
    if rows is None:
        rows = _build_rows(organisation, language)
        cache.set(key, rows, TIMEOUT)
    return rows
