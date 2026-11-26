"""Control rules (K-09-T12, T13): segregation of duties and duplicate payments and invoices.

**SOD_SAME_CREATOR_APPROVER** — the same person created (or submitted) and approved a manual
journal (C-04 approval rounds) or a bill (E-02 approval). Numo9 refuses that today; it arrives
with legacy imports and data from before the approval rules, so the engine flags it. Pay runs
register their own source in ``SOD_SOURCES`` when payroll is built (placeholder).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from decimal import Decimal
from typing import Any

from django.db.models import F, Q, Sum
from django.utils.translation import gettext_lazy

from numo9.ledger.models import (
    AccountSubtype,
    AccountType,
    ApprovalDecision,
    JournalApproval,
    JournalEntry,
    JournalLine,
    JournalStatus,
)

from ..models import ExceptionFinding, Severity
from .base import Context, Hit, Param, Rule, register
from .common import ACCOUNTING_VIEW, ENTRY, ZERO, Numbers, entry_hit, entry_total, is_cash

BILL = "purchases.Bill"


def _person(user: Any) -> str:
    return str(user.name or user.email) if user is not None else ""


def journal_hits(ctx: Context) -> Iterable[Hit]:
    rounds = (
        JournalApproval.objects.filter(
            decision=ApprovalDecision.APPROVED,
            decided_by__isnull=False,
            entry__status=JournalStatus.POSTED,
        )
        .filter(Q(decided_by=F("submitted_by")) | Q(decided_by=F("entry__created_by")))
        .select_related("entry", "decided_by")
        .prefetch_related("entry__lines")
        .order_by("entry__date", "entry_id", "-submitted_at")
    )
    if ctx.scope is not None:
        rounds = rounds.filter(entry__public_id__in=sorted(ctx.scope.entries))
    numbers = Numbers(ctx.organisation)
    seen: set[int] = set()
    for row in rounds:
        if row.entry_id in seen:
            continue
        seen.add(row.entry_id)
        label = numbers.label(row.entry)
        yield Hit(
            ENTRY,
            str(row.entry.public_id),
            label,
            entry_total(row.entry),
            {
                "document": label,
                "entry": str(row.entry.public_id),
                "person": _person(row.decided_by),
                "date": row.entry.date.isoformat(),
            },
        )


def bill_hits(ctx: Context) -> Iterable[Hit]:
    from numo9.purchases.models import BILL_POSTED_STATUSES, Bill

    bills = (
        Bill.objects.filter(status__in=sorted(BILL_POSTED_STATUSES), approved_by__isnull=False)
        .filter(Q(approved_by=F("created_by")) | Q(approved_by=F("submitted_by")))
        .select_related("approved_by", "journal_entry")
        .order_by("date", "pk")
    )
    if ctx.scope is not None:
        bills = bills.filter(journal_entry__public_id__in=sorted(ctx.scope.entries))
    for bill in bills:
        yield Hit(
            BILL,
            str(bill.public_id),
            bill.number,
            bill.total,
            {
                "document": bill.number,
                "entry": str(bill.journal_entry.public_id) if bill.journal_entry else "",
                "person": _person(bill.approved_by),
                "date": bill.date.isoformat(),
            },
        )


#: Sources of "created and approved by the same person": journals, bills; payroll adds pay runs.
SOD_SOURCES: list[Callable[[Context], Iterable[Hit]]] = [journal_hits, bill_hits]


@register
class SameCreatorApprover(Rule):
    code = "SOD_SAME_CREATOR_APPROVER"
    name = gettext_lazy("Created and approved by the same person")
    description = gettext_lazy(
        "One person entered and approved the same journal, bill or pay run: no second pair of eyes."
    )
    explanation = gettext_lazy(
        "%(document)s (%(date)s) was entered and approved by %(person)s. Approval needs a second "
        "person."
    )
    default_severity = Severity.WARNING
    incremental = True
    money_keys = ()
    date_keys = ("date",)

    def covers(self, ctx: Context, finding: ExceptionFinding) -> bool:
        if ctx.scope is None:
            return True
        return str(finding.details.get("entry", "")) in ctx.scope.entries

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        for source in SOD_SOURCES:
            yield from source(ctx)


# ---- duplicates (K-09-T13) ---------------------------------------------------------------------


def _money_out() -> dict[int, Decimal]:
    """Posted journals (not reversed, not reversals) taking money out of bank or cash: entry
    pk → the amount out."""
    rows = (
        JournalLine.objects.filter(
            account__type=AccountType.ASSET,
            account__subtype=AccountSubtype.BANK,
            book__in=ACCOUNTING_VIEW,
            entry__status=JournalStatus.POSTED,
            entry__reversal_of__isnull=True,
        )
        .values("entry_id")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
    )
    out: dict[int, Decimal] = {}
    for row in rows:
        amount = (row["credit"] or ZERO) - (row["debit"] or ZERO)
        if amount > 0:
            out[row["entry_id"]] = amount
    return out


@register
class DuplicatePayment(Rule):
    """Two payments out of a bank or cash account to the same contact for the same amount within
    ``window_days`` of each other (the later one is the finding). Every source counts: bill
    payments, spend money, refunds and manual journals — read from the ledger."""

    code = "DUPLICATE_PAYMENT"
    name = gettext_lazy("Possible duplicate payment")
    description = gettext_lazy("The same contact was paid the same amount twice within a few days.")
    explanation = gettext_lazy(
        "%(journal)s pays %(contact)s %(paid)s on %(date)s; %(other)s paid the same amount on "
        "%(other_date)s. If it is a duplicate, void or reverse it and ask for the money back."
    )
    default_severity = Severity.WARNING
    money_keys = ("paid",)
    date_keys = ("date", "other_date")
    params = {"window_days": Param("int", 3, gettext_lazy("Days apart"), minimum=0, maximum=60)}

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        out = _money_out()
        if not out:
            return
        contacts: dict[int, Any] = {}
        lines = (
            JournalLine.objects.filter(entry_id__in=list(out), contact__isnull=False)
            .select_related("contact")
            .order_by("entry_id", "line_no")
        )
        for line in sorted(lines, key=lambda x: is_cash(x.account)):  # the payee's line first
            contacts.setdefault(line.entry_id, line.contact)
        entries = {e.pk: e for e in JournalEntry.objects.filter(pk__in=list(contacts))}
        groups: dict[tuple[int, Decimal], list[JournalEntry]] = {}
        for pk, contact in contacts.items():
            groups.setdefault((contact.pk, out[pk]), []).append(entries[pk])
        window = dt.timedelta(days=ctx.params["window_days"])
        numbers = Numbers(ctx.organisation)
        for (_contact, amount), payments in groups.items():
            payments.sort(key=lambda e: (e.date, e.pk))
            for earlier, later in zip(payments, payments[1:], strict=False):
                if later.date - earlier.date > window:
                    continue
                contact = contacts[later.pk]
                yield entry_hit(
                    later,
                    numbers,
                    amount,
                    paid=f"{amount:.2f}",
                    contact=contact.display_name,
                    contact_id=str(contact.public_id),
                    other=numbers.label(earlier),
                    other_entry=str(earlier.public_id),
                    other_date=earlier.date.isoformat(),
                )


def normalise_invoice_no(value: str) -> str:
    """``INV-00123`` ≡ ``inv 123``: letters and digits only, upper case, no leading zeros in
    the digit runs."""
    import re

    text = re.sub(r"[^0-9A-Za-z]", "", value or "").upper()
    return re.sub(r"0+(\d)", r"\1", text)


@register
class DuplicateSupplierInvoice(Rule):
    """Two bills of the same supplier (not void) with the same supplier invoice number once
    normalised (case, spaces, dashes, leading zeros — the exact number is unique already,
    gap-24), or totals within ``tolerance_pct`` and dates within ``window_days`` (E-02-T03's
    look-alike test). The later bill is the finding."""

    code = "DUPLICATE_SUPPLIER_INVOICE"
    name = gettext_lazy("Possible duplicate supplier invoice")
    description = gettext_lazy("A supplier's invoice may have been entered twice.")
    explanation = gettext_lazy(
        "%(bill)s from %(supplier)s (%(date)s, %(total)s) looks like %(other)s (%(other_date)s, "
        "%(other_total)s): %(why)s."
    )
    default_severity = Severity.WARNING
    money_keys = ("total", "other_total")
    date_keys = ("date", "other_date")
    params = {
        "window_days": Param("int", 10, gettext_lazy("Days apart"), minimum=0, maximum=90),
        "tolerance_pct": Param(
            "decimal", Decimal("1.00"), gettext_lazy("Total within %"), minimum=Decimal("0")
        ),
    }

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        from django.utils.translation import gettext as _

        from numo9.purchases.models import Bill, BillStatus

        bills = list(
            Bill.objects.exclude(status=BillStatus.VOID)
            .filter(deleted_at__isnull=True)
            .select_related("contact")
            .order_by("contact_id", "date", "pk")
        )
        window = dt.timedelta(days=ctx.params["window_days"])
        tolerance = ctx.params["tolerance_pct"] / Decimal("100")
        by_supplier: dict[int, list[Any]] = {}
        for bill in bills:
            by_supplier.setdefault(bill.contact_id, []).append(bill)
        for group in by_supplier.values():
            flagged: set[int] = set()
            for i, later in enumerate(group):
                for earlier in group[:i]:
                    if later.pk in flagged:
                        break
                    same_number = bool(later.supplier_invoice_no) and normalise_invoice_no(
                        later.supplier_invoice_no
                    ) == normalise_invoice_no(earlier.supplier_invoice_no)
                    close = (
                        abs(later.date - earlier.date) <= window
                        and abs(later.total - earlier.total) <= abs(earlier.total) * tolerance
                    )
                    if not (same_number or close):
                        continue
                    flagged.add(later.pk)
                    label = later.number or later.supplier_invoice_no or _("A draft bill")
                    yield Hit(
                        "purchases.Bill",
                        str(later.public_id),
                        label,
                        later.total,
                        {
                            "bill": label,
                            "supplier": later.contact.display_name,
                            "date": later.date.isoformat(),
                            "total": f"{later.total:.2f}",
                            "supplier_invoice_no": later.supplier_invoice_no,
                            "other": earlier.number or earlier.supplier_invoice_no,
                            "other_id": str(earlier.public_id),
                            "other_date": earlier.date.isoformat(),
                            "other_total": f"{earlier.total:.2f}",
                            "why": _("the same invoice number")
                            if same_number
                            else _("a similar total within a few days"),
                        },
                    )
