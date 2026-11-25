"""Find & recode (C-07-T03): the entries of void invoices and credit notes are excluded."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.ledger.recode_exclusions import register_exclusion, voided_documents

from .models import CreditNote, Invoice

VOID_INVOICES = voided_documents("sales.invoice", Invoice, _("Invoice"))
VOID_CREDIT_NOTES = voided_documents("sales.credit_note", CreditNote, _("Credit note"))


def register_recode_exclusions() -> None:
    register_exclusion(VOID_INVOICES)
    register_exclusion(VOID_CREDIT_NOTES)
