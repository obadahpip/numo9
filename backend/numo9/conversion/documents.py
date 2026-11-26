"""Opening documents of the conversion (C-05-T03): the invoices and bills still open at the
conversion date, entered **per document** so aging, statements, reminders and payments work on
them exactly as on documents raised in Numo9.

An opening document is an ordinary ``sales.Invoice`` / ``purchases.Bill`` with
``is_opening=True``, linked to the session by an ``OpeningDocument``:

- dated **before** the conversion date (it was raised in the old system), CAD only;
- ``total`` — the document's original total; ``outstanding`` — what was still owed at the
  conversion date (``total`` by default; less for a partly paid document: the difference is
  stored as ``amount_paid``, so the document opens Partially paid);
- open at once — an invoice is Approved (or Partially paid), a bill Awaiting payment (or Partially
  paid) — numbered: an invoice keeps the old system's number (required, unique among the
  organisation's invoices); a bill keeps the supplier's invoice number and takes an ``OB-0001``
  number of its own;
- one line, "Opening balance", no tax and no account: the document **posts nothing**. Its
  receivable or payable is in the conversion's Accounts receivable / Accounts payable line,
  posted by the opening journal at finalise (C-05-T05), which also checks that the control line
  equals the documents (C-05-T04);
- edited or removed while the conversion is a draft; once it is finalised, an opening document
  is paid like any other but can't be voided (its correction is a correcting opening journal,
  C-05-T07).

Every refusal is a ``ValidationError`` with a ``conversion.document.*`` code.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.tenancy.context import org_context

from .models import ConversionSession, OpeningDocument, OpeningDocumentKind

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
BILL_PREFIX = "OB-"


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _refuse(field: str, message: str, code: str) -> ValidationError:
    return ValidationError({field: ValidationError(message, code=code)})


def _amount(field: str, value: Any) -> Decimal:
    try:
        amount = Decimal(str(value if value not in (None, "") else "x"))
    except InvalidOperation:
        raise _refuse(field, _("Enter an amount."), "conversion.document.amount") from None
    if not amount.is_finite() or amount != amount.quantize(CENT):
        raise _refuse(field, _("Enter an amount."), "conversion.document.amount")
    return amount


def assert_draft(session: ConversionSession) -> None:
    if session.is_finalised:
        raise ValidationError(
            _("The conversion is finalised: correct it with a correcting opening journal."),
            code="conversion.session.finalised",
        )


def _check(
    session: ConversionSession,
    *,
    date: dt.date,
    due_date: dt.date | None,
    total: Any,
    outstanding: Any,
) -> tuple[Decimal, Decimal]:
    assert_draft(session)
    if date >= session.conversion_date:
        raise _refuse(
            "date",
            _(
                "An opening document is dated before the conversion date (%(date)s): enter "
                "documents raised from that date in Numo9."
            )
            % {"date": session.conversion_date.isoformat()},
            "conversion.document.date",
        )
    if due_date is not None and due_date < date:
        raise _refuse(
            "due_date",
            _("The due date can't be before the document's date."),
            "conversion.document.due_date",
        )
    total_ = _amount("total", total)
    if total_ <= ZERO:
        raise _refuse("total", _("The total must be more than zero."), "conversion.document.total")
    owed = total_ if outstanding in (None, "") else _amount("outstanding", outstanding)
    if owed <= ZERO or owed > total_:
        raise _refuse(
            "outstanding",
            _("What is still owed must be more than zero and no more than the total."),
            "conversion.document.outstanding",
        )
    return total_, owed


def _line_text(session: ConversionSession) -> str:
    return _("Opening balance at %(date)s") % {"date": session.conversion_date.isoformat()}


def add_opening_invoice(
    session: ConversionSession,
    *,
    contact: Any,
    number: str,
    date: dt.date,
    total: Any,
    outstanding: Any = None,
    due_date: dt.date | None = None,
    reference: str = "",
    user: Any = None,
) -> Any:
    """An invoice open at the conversion date (module docstring); returns the ``Invoice``."""
    from numo9.sales.models import Invoice, InvoiceLine, InvoiceStatus

    number = " ".join((number or "").split())
    with org_context(session.organisation), transaction.atomic():
        total_, owed = _check(
            session, date=date, due_date=due_date, total=total, outstanding=outstanding
        )
        if not number:
            raise _refuse(
                "number",
                _("Enter the invoice's number in the old system."),
                "conversion.document.number_required",
            )
        if Invoice.objects.filter(number__iexact=number).exists():
            raise _refuse(
                "number",
                _("There's already an invoice %(number)s.") % {"number": number},
                "conversion.document.number_taken",
            )
        person = _person(user)
        invoice = Invoice(
            organisation=session.organisation,
            contact=contact,
            date=date,
            due_date=due_date,
            reference=reference,
            tax_mode="no_tax",
            number=number,
            is_opening=True,
            status=InvoiceStatus.APPROVED if owed == total_ else InvoiceStatus.PARTIALLY_PAID,
            subtotal=total_,
            total=total_,
            amount_paid=total_ - owed,
            approved_by=person,
            approved_at=timezone.now(),
            created_by=person,
        )
        invoice.save()
        InvoiceLine(
            organisation=session.organisation,
            document=invoice,
            description=_line_text(session),
            quantity=Decimal("1"),
            unit_price=total_,
            net=total_,
            amount=total_,
        ).save()
        OpeningDocument(
            organisation=session.organisation,
            session=session,
            kind=OpeningDocumentKind.INVOICE,
            invoice=invoice,
            outstanding=owed,
        ).save()
        return invoice


def _next_bill_number(organisation: Any) -> str:
    from numo9.purchases.models import Bill

    used = Bill._base_manager.filter(
        organisation=organisation, number__startswith=BILL_PREFIX
    ).values_list("number", flat=True)
    highest = max(
        (int(n[len(BILL_PREFIX) :]) for n in used if n[len(BILL_PREFIX) :].isdigit()), default=0
    )
    return f"{BILL_PREFIX}{highest + 1:04d}"


def add_opening_bill(
    session: ConversionSession,
    *,
    contact: Any,
    supplier_invoice_no: str,
    date: dt.date,
    total: Any,
    outstanding: Any = None,
    due_date: dt.date | None = None,
    reference: str = "",
    user: Any = None,
) -> Any:
    """A bill unpaid at the conversion date (module docstring); returns the ``Bill``."""
    from numo9.purchases.models import Bill, BillLine, BillStatus

    supplier_invoice_no = " ".join((supplier_invoice_no or "").split())
    with org_context(session.organisation), transaction.atomic():
        total_, owed = _check(
            session, date=date, due_date=due_date, total=total, outstanding=outstanding
        )
        if not supplier_invoice_no:
            raise _refuse(
                "supplier_invoice_no",
                _("Enter the supplier's invoice number."),
                "conversion.document.number_required",
            )
        if (
            Bill.objects.filter(
                contact=contact,
                supplier_invoice_no__iexact=supplier_invoice_no,
                deleted_at__isnull=True,
            )
            .exclude(status=BillStatus.VOID)
            .exists()
        ):
            raise _refuse(
                "supplier_invoice_no",
                _("There's already a bill %(number)s from this supplier.")
                % {"number": supplier_invoice_no},
                "conversion.document.number_taken",
            )
        person = _person(user)
        bill = Bill(
            organisation=session.organisation,
            contact=contact,
            date=date,
            due_date=due_date,
            reference=reference,
            tax_mode="no_tax",
            number=_next_bill_number(session.organisation),
            supplier_invoice_no=supplier_invoice_no,
            is_opening=True,
            status=BillStatus.AWAITING_PAYMENT if owed == total_ else BillStatus.PARTIALLY_PAID,
            subtotal=total_,
            total=total_,
            amount_paid=total_ - owed,
            approved_by=person,
            approved_at=timezone.now(),
            created_by=person,
        )
        bill.save()
        BillLine(
            organisation=session.organisation,
            document=bill,
            description=_line_text(session),
            quantity=Decimal("1"),
            unit_price=total_,
            net=total_,
            amount=total_,
        ).save()
        OpeningDocument(
            organisation=session.organisation,
            session=session,
            kind=OpeningDocumentKind.BILL,
            bill=bill,
            outstanding=owed,
        ).save()
        return bill


def _entered(link: OpeningDocument) -> Decimal:
    return Decimal(link.outstanding)


def remove_opening_document(link: OpeningDocument) -> None:
    """Remove an opening document from a draft conversion. Records are never removed (soft
    delete): the document goes back to a draft without a number (so the number can be entered
    again) and is deleted with its link. A document already paid in Numo9 stays: remove its
    payments first."""
    from numo9.purchases.models import Bill, BillStatus
    from numo9.sales.models import Invoice, InvoiceStatus

    with org_context(link.organisation), transaction.atomic():
        assert_draft(link.session)
        is_invoice = link.kind == OpeningDocumentKind.INVOICE
        model: Any = Invoice if is_invoice else Bill
        locked = model._base_manager.select_for_update().get(pk=link.document.pk)
        if Decimal(locked.amount_paid) != Decimal(locked.total) - _entered(link):
            raise ValidationError(
                _("%(document)s has payments in Numo9: remove them first.")
                % {"document": str(locked)},
                code="conversion.document.paid",
            )
        locked.status = InvoiceStatus.DRAFT if is_invoice else BillStatus.DRAFT
        locked.number = ""
        locked.save(update_fields=["status", "number", "updated_at"])
        locked.soft_delete()
        link.soft_delete()


def opening_documents(session: ConversionSession, kind: str | None = None) -> list[Any]:
    """The session's opening invoices / bills (``kind``), oldest first."""
    with org_context(session.organisation):
        links = OpeningDocument.objects.filter(
            session=session, deleted_at__isnull=True
        ).select_related("invoice__contact", "bill__contact")
        if kind:
            links = links.filter(kind=kind)
        documents = [link.document for link in links]
    return sorted(documents, key=lambda d: (d.date, d.number, d.pk))


# ---- batches (C-05-T09, T12: the paste-friendly grids) -------------------------------------


def _find_contact(value: Any, role: str) -> Any:
    """A contact by public id, or by display name (case ignored) when exactly one has it."""
    import uuid

    from numo9.contacts.models import Contact

    text = " ".join(str(value or "").split())
    if not text:
        return None
    try:
        return Contact.objects.filter(public_id=uuid.UUID(text), deleted_at__isnull=True).first()
    except ValueError:
        pass
    named = list(Contact.objects.filter(display_name__iexact=text, deleted_at__isnull=True)[:3])
    if len(named) > 1:
        with_role = [c for c in named if role in (c.roles or [])]
        named = with_role if len(with_role) == 1 else named
    return named[0] if len(named) == 1 else None


def _date(value: Any) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    text = str(value or "").strip()
    return dt.date.fromisoformat(text) if text else None


def _errors(error: ValidationError) -> list[dict[str, str]]:
    if hasattr(error, "error_dict"):
        return [
            {"field": name, "code": item.code or "invalid", "message": " ".join(item.messages)}
            for name, items in error.error_dict.items()
            for item in items
        ]
    return [
        {"field": "", "code": item.code or "invalid", "message": " ".join(item.messages)}
        for item in error.error_list
    ]


def add_opening_rows(
    session: ConversionSession,
    kind: str,
    rows: list[dict[str, Any]],
    *,
    dry_run: bool = False,
    user: Any = None,
) -> dict[str, Any]:
    """Validate (and, unless ``dry_run``, add) a batch of opening invoices or bills — the rows of
    the grid, pasted from a spreadsheet: ``contact`` (id or name), ``number`` (invoices) or
    ``supplier_invoice_no`` (bills), ``date``, ``due_date``, ``total``, ``outstanding``,
    ``reference``. **All or nothing**: every row is validated (duplicates inside the batch
    included); when any row has a problem — or on a dry run — nothing is written. Returns
    ``{"rows": [{"row", "ok", "errors", "id"}], "ok", "errors", "written"}``."""
    if kind not in OpeningDocumentKind.values:
        raise _refuse("kind", _("Choose invoices or bills."), "conversion.document.kind")
    role = "customer" if kind == OpeningDocumentKind.INVOICE else "supplier"
    results: list[dict[str, Any]] = []
    with org_context(session.organisation), transaction.atomic():
        assert_draft(session)
        for index, row in enumerate(rows, start=1):
            result: dict[str, Any] = {"row": index, "ok": True, "errors": [], "id": None}
            try:
                with transaction.atomic():
                    contact = _find_contact(row.get("contact"), role)
                    if contact is None:
                        raise _refuse(
                            "contact",
                            _("There's no contact “%(name)s”: add it first, or use its exact name.")
                            % {"name": row.get("contact") or "—"},
                            "conversion.document.contact",
                        )
                    try:
                        date = _date(row.get("date"))
                        due_date = _date(row.get("due_date"))
                    except ValueError:
                        raise _refuse(
                            "date", _("Use dates like 2025-12-31."), "conversion.document.date"
                        ) from None
                    if date is None:
                        raise _refuse(
                            "date", _("Enter the document's date."), "conversion.document.date"
                        )
                    common = {
                        "contact": contact,
                        "date": date,
                        "due_date": due_date,
                        "total": row.get("total"),
                        "outstanding": row.get("outstanding"),
                        "reference": str(row.get("reference") or ""),
                        "user": user,
                    }
                    if kind == OpeningDocumentKind.INVOICE:
                        made = add_opening_invoice(
                            session, number=str(row.get("number") or ""), **common
                        )
                    else:
                        made = add_opening_bill(
                            session,
                            supplier_invoice_no=str(row.get("supplier_invoice_no") or ""),
                            **common,
                        )
                    result["id"] = str(made.opening_link.public_id)
            except ValidationError as error:
                result.update(ok=False, errors=_errors(error), id=None)
            results.append(result)
        failed = sum(1 for r in results if not r["ok"])
        if failed or dry_run:
            transaction.set_rollback(True)
            for result in results:
                result["id"] = None
    written = 0 if failed or dry_run else len(results)
    return {
        "dry_run": dry_run,
        "rows": results,
        "ok": len(results) - failed,
        "errors": failed,
        "written": written,
    }
