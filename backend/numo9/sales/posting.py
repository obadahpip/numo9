"""Invoice approval and posting (D-03a-T03).

``invoice_preview(invoice)`` — the journal the invoice will post: the D-01 posting preview of its
lines (``numo9.documents.posting.preview``) — Dr Accounts receivable, Cr each line's revenue
account, Cr **each tax control account separately** (GST/HST payable, PST payable, QST payable).

``approve(invoice, user)`` — in **one transaction**: lock the invoice, refuse what can't be
approved (not a draft or awaiting approval; a line with an amount but no account; a total of
zero or below — a negative invoice is a credit note; the customer's credit limit in block mode
without an approved override, D-03a-T06), store the server's figures on the header
and lines, take the number (D-03a-T02), and post the preview's journal through the posting
engine (C-02: lock dates of the AR module, closed periods, every journal rule) with the invoice
as its source. All or nothing: a refused posting leaves the invoice a draft without a number.
The posted journal **is** the preview's lines — what the screen showed is what posts.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.contacts.credit import assert_credit
from numo9.documents.posting import Preview, PreviewLine, preview
from numo9.ledger.models import LedgerError
from numo9.ledger.renumber import acting_as
from numo9.ledger.services import post_journal
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import org_context

from .credit import DOCUMENT_TYPE as CREDIT_DOCUMENT
from .models import CreditNote, Invoice, InvoiceStatus
from .numbering import assign_number

SOURCE_TYPE = "sales.invoice"
ZERO = Decimal("0.00")


class InvoiceRefused(LedgerError):
    """An invoice action the rules refuse (``code`` names the rule)."""


def preview_lines(invoice: Invoice | CreditNote) -> list[PreviewLine]:
    return [
        PreviewLine(
            account=line.account,
            quantity=line.quantity,
            unit_price=line.unit_price,
            discount_type=line.discount_type,
            discount_value=line.discount_value,
            tax_code=line.tax_code,
            description=line.description,
            tracking=dict(line.tracking or {}),
        )
        for line in invoice.lines.select_related("account", "tax_code").order_by("position", "pk")
    ]


def invoice_preview(invoice: Invoice) -> Preview:
    with org_context(invoice.organisation):
        return preview(
            "invoice",
            invoice.date,
            preview_lines(invoice),
            tax_mode=invoice.tax_mode,
            discount_type=invoice.discount_type,
            discount_value=invoice.discount_value,
            contact=invoice.contact,
        )


def store_figures(invoice: Invoice | CreditNote, result: Any) -> None:
    """The calculator's figures on the header and each line (server-authoritative)."""
    lines = list(invoice.lines.order_by("position", "pk"))
    for line, figures in zip(lines, result.lines, strict=True):
        line.net = figures.exclusive  # before tax, after every discount
        line.tax_amount = figures.tax
        line.amount = figures.net  # the line's Amount column (gross − line discount)
        line.save(update_fields=["net", "tax_amount", "amount", "updated_at"])
    invoice.subtotal = result.subtotal
    invoice.discount_total = result.discount_total
    invoice.tax_total = result.tax_total
    invoice.total = result.total


def recalculate(invoice: Invoice) -> Invoice:
    """Store the calculator's figures on a draft (what the editor does on save): the totals the
    lists, the duplicate check (D-03a-T08) and the exposure read."""
    with org_context(invoice.organisation), transaction.atomic():
        from numo9.documents.posting import result_for

        result = result_for(
            "invoice",
            preview_lines(invoice),
            tax_mode=invoice.tax_mode,
            discount_type=invoice.discount_type,
            discount_value=invoice.discount_value,
        )
        store_figures(invoice, result)
        invoice.save(
            update_fields=["subtotal", "discount_total", "tax_total", "total", "updated_at"]
        )
        return invoice


def _refuse(message: str, code: str, **params: Any) -> InvoiceRefused:
    return InvoiceRefused(message, code=code, params=params or None)


def approve(invoice: Invoice, user: Any) -> Invoice:
    """Approve and post (module docstring); returns the approved invoice."""
    person = user if getattr(user, "is_authenticated", False) else None
    with org_context(invoice.organisation), transaction.atomic(), acting_as(person):
        locked = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
        if locked.status not in (InvoiceStatus.DRAFT, InvoiceStatus.AWAITING_APPROVAL):
            raise _refuse(
                _("%(invoice)s is already %(status)s."),
                "sales.invoice.not_draft",
                invoice=str(locked),
                status=str(InvoiceStatus(locked.status).label).lower(),
            )
        shown = invoice_preview(locked)
        if not shown.complete:
            raise _refuse(
                _("Every line with an amount needs an account before the invoice is approved."),
                "sales.invoice.incomplete",
            )
        if shown.result.total <= ZERO:
            raise _refuse(
                _(
                    "An invoice's total must be more than zero: for money owed to the customer, "
                    "issue a credit note."
                ),
                "sales.invoice.total_not_positive",
            )
        # D-03a-T06: the customer's credit limit — warn posts with the warning, block refuses
        # unless an approved override for this invoice covers it (used up here).
        credit = assert_credit(
            locked.contact,
            shown.result.total,
            user=person,
            document_type=CREDIT_DOCUMENT,
            document_ref=str(locked.public_id),
        )
        store_figures(locked, shown.result)
        number = assign_number(locked)
        entry = post_journal(
            shown.spec(
                source_type=SOURCE_TYPE,
                source_id=str(locked.public_id),
                narration=_("Invoice %(number)s — %(contact)s")
                % {"number": number, "contact": locked.contact.display_name},
            ),
            organisation=locked.organisation,
            user=person,
            module=LockModule.AR,
        )
        locked.number = number
        locked.status = InvoiceStatus.APPROVED
        locked.journal_entry = entry
        locked.approved_by = person
        locked.approved_at = timezone.now()
        locked.version += 1
        locked.save()
        locked.credit_warning = credit.message  # type: ignore[attr-defined]
        return locked


# ---- void (D-03a-T07) --------------------------------------------------------------------------

VOIDABLE = (InvoiceStatus.APPROVED, InvoiceStatus.SENT)


def void(invoice: Invoice, user: Any, *, date: Any = None, reason: str = "") -> Invoice:
    """Void a posted invoice: its journal is reversed (C-02 ``reverse``) on ``date`` — the
    invoice's own date by default, checked against the AR lock date and closed periods — the
    status becomes Void, the **number is kept**, and the void is audited with the reason. An
    invoice with payments can't be voided (remove the payments first); a draft is deleted, not
    voided."""
    from numo9.audit import service as audit
    from numo9.ledger.services import reverse

    person = user if getattr(user, "is_authenticated", False) else None
    with org_context(invoice.organisation), transaction.atomic(), acting_as(person):
        locked = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
        if locked.status not in VOIDABLE or locked.amount_paid:
            raise _refuse(
                _("%(invoice)s can't be voided: %(why)s"),
                "sales.invoice.not_voidable",
                invoice=str(locked),
                why=_("remove its payments first.")
                if locked.amount_paid
                else _("only approved or sent invoices can be voided."),
            )
        assert locked.journal_entry is not None  # noqa: S101 — posted statuses have one (DB check)
        reversal = reverse(
            locked.journal_entry,
            date=date or locked.date,
            narration=_("Void of invoice %(number)s") % {"number": locked.number},
            user=person,
            module=LockModule.AR,
        )
        previous = locked.status
        locked.status = InvoiceStatus.VOID
        locked.void_entry = reversal
        locked.voided_at = timezone.now()
        locked.version += 1
        locked.save()
        audit.record(
            "sales.invoice.voided",
            obj=locked,
            changes={"status": [previous, InvoiceStatus.VOID]},
            meta={"number": locked.number, "reason": " ".join((reason or "").split())},
            actor=person,
        )
        return locked
