"""Supplier credit posting (E-03-T05): the bill's journal on the other side.

``supplier_credit_preview(credit)`` — the D-01 posting preview of the credit's lines as a
``supplier_credit``: **Dr Accounts payable** (the supplier), **Cr** each line's expense or asset
account (net + the non-claimable tax), **Cr** the ITC / ITR control accounts for the claimable
tax — the input tax credit reverses in the period of the credit's date. The same claimable rules
as a bill (E-02-T04): the account's and tax code's restrictions, nothing claimable when the
organisation isn't registered for GST/HST on the date.

``approve(credit, user)`` — one transaction: lock, refuse what can't be approved (not a draft; a
line without an account; a total of zero or below; a credited bill of another supplier or not
posted), store the server's figures and post through the posting engine (AP lock date, closed
periods, every journal rule) with the credit as its source.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.documents.posting import Preview, preview, result_for
from numo9.ledger.models import LedgerError
from numo9.ledger.renumber import acting_as
from numo9.ledger.services import post_journal
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import org_context

from .bills import preview_lines
from .models import BillStatus, SupplierCredit, SupplierCreditStatus

SOURCE_TYPE = "purchases.supplier_credit"
KIND = "supplier_credit"
ZERO = Decimal("0.00")
POSTED_BILL = frozenset({BillStatus.AWAITING_PAYMENT, BillStatus.PARTIALLY_PAID, BillStatus.PAID})


class SupplierCreditRefused(LedgerError):
    """A supplier credit action the rules refuse (``code`` names the rule)."""


def _refuse(message: str, code: str, **params: Any) -> SupplierCreditRefused:
    return SupplierCreditRefused(message, code=code, params=params or None)


def store_figures(credit: SupplierCredit, result: Any) -> None:
    """The calculator's figures on the header and each line (server-authoritative)."""
    lines = list(credit.lines.order_by("position", "pk"))
    for line, figures in zip(lines, result.lines, strict=True):
        line.net = figures.exclusive
        line.tax_amount = figures.tax
        line.amount = figures.net
        line.save(update_fields=["net", "tax_amount", "amount", "updated_at"])
    credit.subtotal = result.subtotal
    credit.discount_total = result.discount_total
    credit.tax_total = result.tax_total
    credit.total = result.total


def supplier_credit_preview(credit: SupplierCredit) -> Preview:
    with org_context(credit.organisation):
        return preview(
            KIND,
            credit.date,
            preview_lines(credit),
            tax_mode=credit.tax_mode,
            discount_type=credit.discount_type,
            discount_value=credit.discount_value,
            contact=credit.contact,
        )


def recalculate(credit: SupplierCredit) -> SupplierCredit:
    with org_context(credit.organisation), transaction.atomic():
        result = result_for(
            KIND,
            preview_lines(credit),
            tax_mode=credit.tax_mode,
            discount_type=credit.discount_type,
            discount_value=credit.discount_value,
        )
        store_figures(credit, result)
        credit.save(
            update_fields=["subtotal", "discount_total", "tax_total", "total", "updated_at"]
        )
        return credit


def approve(credit: SupplierCredit, user: Any) -> SupplierCredit:
    person = user if getattr(user, "is_authenticated", False) else None
    with org_context(credit.organisation), transaction.atomic(), acting_as(person):
        locked = SupplierCredit._base_manager.select_for_update().get(pk=credit.pk)
        if locked.status != SupplierCreditStatus.DRAFT:
            raise _refuse(
                _("This supplier credit is already %(status)s."),
                "purchases.supplier_credit.not_draft",
                status=str(SupplierCreditStatus(locked.status).label).lower(),
            )
        bill = locked.bill
        if bill is not None and (
            bill.contact_id != locked.contact_id or bill.status not in POSTED_BILL
        ):
            raise _refuse(
                _("A supplier credit can credit only an approved bill of the same supplier."),
                "purchases.supplier_credit.bill_mismatch",
            )
        shown = supplier_credit_preview(locked)
        if not shown.complete:
            raise _refuse(
                _("Every line with an amount needs an account before the credit is approved."),
                "purchases.supplier_credit.incomplete",
            )
        if shown.result.total <= ZERO:
            raise _refuse(
                _("A supplier credit's total must be more than zero."),
                "purchases.supplier_credit.total_not_positive",
            )
        store_figures(locked, shown.result)
        reference = locked.supplier_reference or str(locked.public_id)[:8]
        entry = post_journal(
            shown.spec(
                source_type=SOURCE_TYPE,
                source_id=str(locked.public_id),
                narration=_("Supplier credit %(reference)s — %(contact)s")
                % {"reference": reference, "contact": locked.contact.display_name},
            ),
            organisation=locked.organisation,
            user=person,
            module=LockModule.AP,
        )
        locked.status = SupplierCreditStatus.APPROVED
        locked.journal_entry = entry
        locked.approved_by = person
        locked.approved_at = timezone.now()
        locked.version += 1
        locked.save()
        return locked
