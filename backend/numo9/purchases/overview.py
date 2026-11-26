"""Purchases overview and bills list tabs (E-02-T15) — one query source for both.

The overview tiles and the list tabs count with the **same** filters (``tab_filter``), so the
"Overdue 3" tile always opens a list of 3 bills (D-09 business rule "tile counts come from the
same query as list tabs", gap-22). Tabs:

- ``all`` — every bill not deleted (voided included);
- ``draft``, ``awaiting_approval``, ``paid``, ``void`` — that status;
- ``awaiting_payment`` — posted and still owed: awaiting payment **or partially paid**;
- ``overdue`` — awaiting payment / partially paid, due date before **today in the organisation's
  time zone** and an open balance above zero.

Amounts: drafts and bills awaiting approval count their total; posted bills what is still owed
(``amount_due``: total − holdback still held − payments, the AP balance).

``aging`` puts what is owed by age of the due date — current (not due yet, or no due date),
1–30, 31–60, 61–90 and over 90 days past due; ``top_suppliers`` the five suppliers owed the most.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from .models import Bill, BillStatus

TABS: tuple[str, ...] = (
    "all",
    "draft",
    "awaiting_approval",
    "awaiting_payment",
    "overdue",
    "paid",
    "void",
)
#: The overview's status tiles, in order (a subset of the tabs).
TILES: tuple[str, ...] = ("draft", "awaiting_approval", "awaiting_payment", "overdue")
TAB_LABELS = {
    "all": _("All"),
    "draft": _("Draft"),
    "awaiting_approval": _("Awaiting approval"),
    "awaiting_payment": _("Awaiting payment"),
    "overdue": _("Overdue"),
    "paid": _("Paid"),
    "void": _("Void"),
}
OPEN_STATUSES = (BillStatus.AWAITING_PAYMENT, BillStatus.PARTIALLY_PAID)
#: (key, label, first day past due, last day past due or None).
AGING_BUCKETS: tuple[tuple[str, Any, int | None, int | None], ...] = (
    ("current", _("Current"), None, 0),
    ("1_30", _("1–30 days"), 1, 30),
    ("31_60", _("31–60 days"), 31, 60),
    ("61_90", _("61–90 days"), 61, 90),
    ("over_90", _("Over 90 days"), 91, None),
)
TOP_SUPPLIERS = 5
ZERO = Decimal("0.00")
_MONEY = DecimalField(max_digits=18, decimal_places=2)


def amount_due() -> ExpressionWrapper[Any]:
    """``Bill.amount_due`` in SQL: total − (holdback − released) − paid."""
    return ExpressionWrapper(
        F("total") - (F("holdback_amount") - F("holdback_released")) - F("amount_paid"),
        output_field=_MONEY,
    )


def live_bills() -> QuerySet[Bill]:
    """The bills the list and the overview show: not deleted, with ``due`` annotated."""
    bills: QuerySet[Bill] = Bill.objects.filter(deleted_at__isnull=True).annotate(due=amount_due())
    return bills


def tab_filter(tab: str, today: dt.date) -> Q:
    """The filter of one list tab (also the tile of the same key). Unknown tab → ``ValueError``."""
    if tab == "all":
        return Q()
    if tab == "awaiting_payment":
        return Q(status__in=OPEN_STATUSES)
    if tab == "overdue":
        return Q(status__in=OPEN_STATUSES, due_date__lt=today, due__gt=0)
    if tab in TABS:
        return Q(status=tab)
    raise ValueError(tab)


def _tab_amount(tab: str) -> Any:
    return "total" if tab in ("all", "draft", "awaiting_approval") else "due"


def tab_counts(bills: QuerySet[Bill], today: dt.date) -> dict[str, dict[str, Any]]:
    """Count and amount of every tab, in one query (``bills`` from ``live_bills``)."""
    aggregates: dict[str, Any] = {}
    for tab in TABS:
        condition = tab_filter(tab, today)
        aggregates[f"{tab}__n"] = Count("pk", filter=condition)
        aggregates[f"{tab}__amount"] = Coalesce(
            Sum(_tab_amount(tab), filter=condition), Value(ZERO), output_field=_MONEY
        )
    row = bills.aggregate(**aggregates)
    return {
        tab: {"count": row[f"{tab}__n"], "amount": Decimal(row[f"{tab}__amount"]).quantize(ZERO)}
        for tab in TABS
    }


def aging(bills: QuerySet[Bill], today: dt.date) -> list[dict[str, Any]]:
    """What is owed by age of the due date (open bills with a balance above zero)."""
    owed = bills.filter(Q(status__in=OPEN_STATUSES, due__gt=0))
    aggregates: dict[str, Any] = {}
    for key, _label, first, last in AGING_BUCKETS:
        if first is None:  # not due yet, or no due date
            condition = Q(due_date__isnull=True) | Q(due_date__gte=today)
        else:
            condition = Q(due_date__lte=today - dt.timedelta(days=first))
            if last is not None:
                condition &= Q(due_date__gte=today - dt.timedelta(days=last))
        aggregates[key] = Coalesce(Sum("due", filter=condition), Value(ZERO), output_field=_MONEY)
        aggregates[f"{key}__n"] = Count("pk", filter=condition)
    row = owed.aggregate(**aggregates)
    return [
        {
            "key": key,
            "label": str(label),
            "count": row[f"{key}__n"],
            "amount": Decimal(row[key]).quantize(ZERO),
        }
        for key, label, _first, _last in AGING_BUCKETS
    ]


def top_suppliers(bills: QuerySet[Bill], today: dt.date) -> list[dict[str, Any]]:
    """The suppliers owed the most (open balance), with their overdue part."""
    rows = (
        bills.filter(Q(status__in=OPEN_STATUSES, due__gt=0))
        .values("contact__public_id", "contact__display_name")
        .annotate(
            owed=Sum("due"),
            overdue=Coalesce(
                Sum("due", filter=Q(due_date__lt=today)), Value(ZERO), output_field=_MONEY
            ),
            bills=Count("pk"),
        )
        .order_by("-owed", "contact__display_name")[:TOP_SUPPLIERS]
    )
    return [
        {
            "id": str(row["contact__public_id"]),
            "name": row["contact__display_name"],
            "owed": Decimal(row["owed"]).quantize(ZERO),
            "overdue": Decimal(row["overdue"]).quantize(ZERO),
            "bills": row["bills"],
        }
        for row in rows
    ]
