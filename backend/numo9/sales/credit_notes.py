"""Credit note approval and posting (D-06-T03).

``credit_note_preview(note)`` — the journal the credit note will post: the D-01 posting preview of
its lines as a ``credit_note`` — the invoice's lines **on the other side**: Dr each line's revenue
account, Dr **each tax control account separately** (GST/HST payable, PST payable, QST payable),
Cr Accounts receivable with the customer. The tax reverses in the period of the **credit note's
date** (G-03 rule: the journal's date is the credit note's).

``approve(note, user)`` — in one transaction: lock the credit note, refuse what can't be
approved (not a draft or awaiting approval; a line with an amount but no account; a total of zero
or below), store the server's figures, take the number (``CN-0001``, A-05 sequence, gap-free —
a refused posting gives it back) and post the preview's journal through the posting engine (C-02:
AR lock date, closed periods, every journal rule) with the credit note as its source. A credit
note for an invoice must be the same customer's, and an invoice that is posted and not void.
"""

from __future__ import annotations

import contextlib
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.documents.posting import Preview, preview
from numo9.ledger.renumber import acting_as
from numo9.ledger.services import post_journal
from numo9.orgsettings.models import DocType, LockModule
from numo9.orgsettings.numbering import allocate_number
from numo9.tenancy.context import org_context

from .models import CreditNote, CreditNoteStatus, InvoiceStatus
from .period_checks import assert_postable
from .posting import InvoiceRefused, preview_lines, store_figures

SOURCE_TYPE = "sales.credit_note"
KIND = "credit_note"
ZERO = Decimal("0.00")


class CreditNoteRefused(InvoiceRefused):
    """A credit note action the rules refuse (``code`` names the rule)."""


def _refuse(message: str, code: str, **params: Any) -> CreditNoteRefused:
    return CreditNoteRefused(message, code=code, params=params or None)


def credit_note_preview(note: CreditNote) -> Preview:
    with org_context(note.organisation):
        return preview(
            KIND,
            note.date,
            preview_lines(note),
            tax_mode=note.tax_mode,
            discount_type=note.discount_type,
            discount_value=note.discount_value,
            contact=note.contact,
        )


def recalculate(note: CreditNote) -> CreditNote:
    """Store the calculator's figures on a draft (the editor's save)."""
    from numo9.documents.posting import result_for

    with org_context(note.organisation), transaction.atomic():
        result = result_for(
            KIND,
            preview_lines(note),
            tax_mode=note.tax_mode,
            discount_type=note.discount_type,
            discount_value=note.discount_value,
        )
        store_figures(note, result)
        note.save(update_fields=["subtotal", "discount_total", "tax_total", "total", "updated_at"])
        return note


def assign_number(note: CreditNote) -> str:
    """The credit note's number, taken once (the invoice rule, D-03a-T02)."""
    with org_context(note.organisation), transaction.atomic():
        locked = CreditNote._base_manager.select_for_update().get(pk=note.pk)
        if locked.number:
            note.number = locked.number
            return locked.number
        number = allocate_number(DocType.CREDIT_NOTE, note.organisation)
        CreditNote._base_manager.filter(pk=note.pk).update(number=number)
        note.number = number
        return number


def approve(note: CreditNote, user: Any, *, late_adjustment: bool = False) -> CreditNote:
    """Approve and post (module docstring); returns the approved credit note.

    D-06-T06 — the rule of invoices (D-03a-T04, D-03b-T10): a date on or before the AR lock is
    refused naming the lock; a date in a filed GST/HST (or QST) period is refused naming the
    period, unless ``late_adjustment`` — then the credit note posts on its own date and its tax
    goes on the next open return (line 107, less net tax: G-03-T08)."""
    from numo9.tax.returns import late_adjustments

    person = user if getattr(user, "is_authenticated", False) else None
    with (
        org_context(note.organisation),
        transaction.atomic(),
        acting_as(person),
        late_adjustments() if late_adjustment else contextlib.nullcontext(),
    ):
        locked = CreditNote._base_manager.select_for_update().get(pk=note.pk)
        if locked.status not in (CreditNoteStatus.DRAFT, CreditNoteStatus.AWAITING_APPROVAL):
            raise _refuse(
                _("%(note)s is already %(status)s."),
                "sales.credit_note.not_draft",
                note=str(locked),
                status=str(CreditNoteStatus(locked.status).label).lower(),
            )
        invoice = locked.invoice
        if invoice is not None and (
            invoice.contact_id != locked.contact_id
            or not invoice.is_posted
            or invoice.status == InvoiceStatus.VOID
        ):
            raise _refuse(
                _("A credit note can credit only an approved invoice of the same customer."),
                "sales.credit_note.invoice_mismatch",
            )
        shown = credit_note_preview(locked)
        if not shown.complete:
            raise _refuse(
                _("Every line with an amount needs an account before the credit note is approved."),
                "sales.credit_note.incomplete",
            )
        if shown.result.total <= ZERO:
            raise _refuse(
                _("A credit note's total must be more than zero."),
                "sales.credit_note.total_not_positive",
            )
        assert_postable(locked, shown.lines, shown.date, person, "approve")
        store_figures(locked, shown.result)
        number = assign_number(locked)
        entry = post_journal(
            shown.spec(
                source_type=SOURCE_TYPE,
                source_id=str(locked.public_id),
                narration=_("Credit note %(number)s — %(contact)s")
                % {"number": number, "contact": locked.contact.display_name},
            ),
            organisation=locked.organisation,
            user=person,
            module=LockModule.AR,
        )
        locked.number = number
        locked.status = CreditNoteStatus.APPROVED
        locked.journal_entry = entry
        locked.approved_by = person
        locked.approved_at = timezone.now()
        locked.version += 1
        locked.save()
        return locked
