"""Saved list views (V-01-T08 directory views, generalised for D-09-T03).

One set of rules for every saved view — the practice directory's ``SavedView`` and the
organisation lists' ``SavedListView`` (invoices, bills, quotes, contacts …):

- a view is **personal** (only its user lists, changes or deletes it; anyone else gets 404);
- names are unique per user and list, case ignored (``workspace.view_name_taken``);
- at most ``MAX_VIEWS`` (50) per user and list (``workspace.view_limit``);
- one view per user and list opens by default: setting a new default clears the previous one in
  the same transaction (``save_view``).

``LIST_KEYS`` names the organisation lists a view can be saved for; a deliverable that adds a
list registers its key with ``register_list`` (the API refuses an unknown key, so a typo never
creates views nobody can open). ``filters`` keep the list's own query parameters — short text
values or lists of them — and each list validates them when it applies a view.
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, models, transaction
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from .models import SavedViewFields

MAX_VIEWS = 50
#: Fields a client may set on a view (both kinds); the scope (user, practice/list) never moves.
FIELDS = ("name", "filters", "columns", "sort", "density", "is_default")
#: Bounds of a list view's ``filters`` (the directory validates its own filters precisely).
MAX_FILTERS = 20
MAX_FILTER_VALUES = 50
MAX_FILTER_TEXT = 200

#: Organisation lists that keep saved views: key → what the list is called (for messages).
LIST_KEYS: dict[str, Promise] = {
    "contacts": _("Contacts"),
    "sales.invoices": _("Invoices"),
    "sales.quotes": _("Quotes"),
    "sales.credit_notes": _("Credit notes"),
    "sales.payments": _("Payments received"),
    "purchases.bills": _("Bills"),
    "purchases.orders": _("Purchase orders"),
    "purchases.expense_claims": _("Expense claims"),
    "accounting.journals": _("Journals"),
    "banking.transactions": _("Bank transactions"),
}


def register_list(key: str, label: Promise) -> None:
    """Let views be saved for another organisation list (``area.list`` keys)."""
    LIST_KEYS[key] = label


class ViewNameTaken(Exception):
    pass


def save_view[V: SavedViewFields](
    view: V, data: dict[str, Any], siblings: models.QuerySet[Any]
) -> V:
    """Apply ``data`` (``FIELDS`` only) and save; ``siblings`` are the user's views of the same
    list (or practice). Raises ``ViewNameTaken`` when another of them has the name."""
    for name in FIELDS:
        if name in data:
            setattr(view, name, data[name])
    try:
        with transaction.atomic():
            if view.is_default:  # one default per user and list
                siblings.filter(is_default=True).exclude(pk=view.pk).update(is_default=False)
            view.save()
    except IntegrityError:
        raise ViewNameTaken(view.name) from None
    return view


def clean_list_filters(value: Any) -> dict[str, Any]:
    """A list view's filters: ``{"tab": "overdue", "status": ["draft", "void"]}`` — text keys,
    text values or lists of text, bounded sizes; empty values dropped, list values de-duplicated.
    Raises ``ValueError(key, value)`` for anything else."""
    if not isinstance(value, dict) or len(value) > MAX_FILTERS:
        raise ValueError("filters", "")
    clean: dict[str, Any] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not key or len(key) > 60:
            raise ValueError(str(key)[:60], "")
        if isinstance(raw, str):
            if len(raw) > MAX_FILTER_TEXT:
                raise ValueError(key, raw[:100])
            if raw.strip():
                clean[key] = raw.strip()
        elif isinstance(raw, bool):
            clean[key] = "true" if raw else "false"
        elif isinstance(raw, list):
            if len(raw) > MAX_FILTER_VALUES:
                raise ValueError(key, str(len(raw)))
            items: list[str] = []
            for item in raw:
                if not isinstance(item, str) or len(item) > MAX_FILTER_TEXT:
                    raise ValueError(key, str(item)[:100])
                if item.strip():
                    items.append(item.strip())
            if items:
                clean[key] = list(dict.fromkeys(items))
        else:
            raise ValueError(key, str(raw)[:100])
    return clean
