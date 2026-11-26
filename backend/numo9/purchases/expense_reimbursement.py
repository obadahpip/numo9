"""Reimbursement bill of an approved expense claim (E-04-T06).

When a claim is approved (``expense_claims.approve``), in the same transaction:

- ``employee_contact(claim)`` — the claimant's **employee contact**: the one used on their earlier
  claims, else a contact with the employee role whose person has the claimant's email, else one
  created from the user (display name = their name, role employee, the email as primary person);
- ``create_reimbursement_bill(claim, user)`` — a bill to that contact, dated the approval day,
  **tax inclusive**, one line per claim line (receipt: its amount, category account, tax code,
  merchant; mileage: the allowance on its category, else the Vehicle expenses account — GIFI
  9281 — without tax), the claim number as supplier invoice number (unique per supplier, so a
  claim can't be billed twice) and the claim title as reference. It is numbered (``BILL-0001``)
  and **posted** at once (the claim's approval is the bill's): Dr each category with the net plus
  the tax that can't be claimed, Dr ITC / ITR for the claimable part, **Cr Unpaid expense claims**
  (the ``unpaid_expense_claims`` control account, not AP) with the employee's contact — through
  the posting engine (AP lock date, closed periods). The bill is **Awaiting payment** and is paid
  like any bill (E-06 or a bank payment); ``claim.bill`` and ``claim.contact`` link it.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import Any

from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.documents.models import TaxMode
from numo9.ledger.models import Account, AccountSubtype, AccountType, LedgerError, SystemRole
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import DocType, LockModule
from numo9.orgsettings.numbering import allocate_number

from .models import Bill, BillLine, BillStatus, ExpenseClaim, ExpenseLineKind

SOURCE_TYPE = "purchases.bill"
VEHICLE_GIFI = "9281"
CLAIM_CODES = ["2050", *(str(code) for code in range(2051, 2070))]


class ReimbursementRefused(LedgerError):
    """The reimbursement bill can't be made (``code`` names the rule)."""


def claims_account(organisation: Any) -> Account:
    """The Unpaid expense claims control account (``unpaid_expense_claims`` role): the chart's,
    or — for a chart without it — created on first use (2050, or the next free code to 2069)."""
    found: Account | None = Account.objects.filter(
        system_role=SystemRole.UNPAID_EXPENSE_CLAIMS
    ).first()
    if found is not None:
        return found
    taken = set(Account.objects.filter(code__in=CLAIM_CODES).values_list("code", flat=True))
    code = next((c for c in CLAIM_CODES if c not in taken), None)
    if code is None:
        raise ReimbursementRefused(
            _("Add an Unpaid expense claims account to the chart of accounts to reimburse claims."),
            code="purchases.expense.claims_account",
        )
    account = Account(
        organisation=organisation,
        code=code,
        name_i18n={"en-ca": "Unpaid expense claims", "fr-ca": "Notes de frais à payer"},
        type=AccountType.LIABILITY,
        subtype=AccountSubtype.CURRENT_LIABILITY,
        gifi_id="2620",
        system_role=SystemRole.UNPAID_EXPENSE_CLAIMS,
        require_contact=True,
    )
    account.save()
    return account


def employee_contact(claim: ExpenseClaim) -> Any:
    """The claimant's employee contact (module docstring); created when there is none."""
    from numo9.contacts.models import Contact, ContactPerson, ContactRole

    if claim.contact_id is not None:
        return claim.contact
    earlier = (
        ExpenseClaim.objects.filter(claimant=claim.claimant, contact__isnull=False)
        .exclude(pk=claim.pk)
        .order_by("-created_at")
        .first()
    )
    if earlier is not None and earlier.contact is not None and earlier.contact.deleted_at is None:
        return earlier.contact
    user = claim.claimant
    email = (user.email or "").strip().lower()
    if email:
        person = (
            ContactPerson.objects.filter(
                email=email,
                deleted_at__isnull=True,
                contact__deleted_at__isnull=True,
                contact__roles__contains=[ContactRole.EMPLOYEE],
            )
            .select_related("contact")
            .order_by("pk")
            .first()
        )
        if person is not None:
            return person.contact
    contact = Contact(
        organisation=claim.organisation,
        display_name=(user.name or email or str(user.public_id))[:200],
        roles=[ContactRole.EMPLOYEE],
    )
    contact.save()
    if email:
        first, _sep, last = (user.name or "").partition(" ")
        ContactPerson(
            organisation=claim.organisation,
            contact=contact,
            first_name=first[:100],
            last_name=last[:100],
            email=email,
        ).save()
    return contact


def mileage_account(line: Any) -> Account | None:
    if line.account_id is not None:
        return line.account  # type: ignore[no-any-return]
    found: Account | None = (
        Account.objects.filter(gifi__code=VEHICLE_GIFI, type=AccountType.EXPENSE)
        .order_by("code")
        .first()
    )
    return found


def _bill_lines(claim: ExpenseClaim, bill: Bill) -> None:
    for position, line in enumerate(claim.lines.select_related("account", "tax_code")):
        if Decimal(line.amount) <= 0:
            continue
        if line.kind == ExpenseLineKind.MILEAGE:
            account = mileage_account(line)
            description = _("Mileage %(date)s: %(trip)s") % {
                "date": line.date.isoformat(),
                "trip": str(line),
            }
            tax_code = None
        else:
            account = line.account
            parts = [line.date.isoformat(), line.merchant, line.description]
            description = " · ".join(p for p in parts if p)
            tax_code = line.tax_code
        if account is None:
            raise ReimbursementRefused(
                _("Choose a category for every line of the claim."),
                code="purchases.expense.category_missing",
            )
        BillLine(
            organisation=claim.organisation,
            document=bill,
            position=position,
            description=description,
            quantity=Decimal("1"),
            unit_price=Decimal(line.amount),
            account=account,
            tax_code=tax_code,
            tracking=dict(line.tracking or {}),
        ).save()


def reimbursement_lines(lines: tuple[LineSpec, ...], control: Account) -> tuple[LineSpec, ...]:
    """The bill's journal lines with Accounts payable replaced by ``control``."""
    ap = Account.objects.get(system_role=SystemRole.AP)
    out = []
    for line in lines:
        account_id = line.account.pk if isinstance(line.account, Account) else line.account
        out.append(dataclasses.replace(line, account=control) if account_id == ap.pk else line)
    return tuple(out)


def create_reimbursement_bill(claim: ExpenseClaim, user: Any) -> Bill:
    """Make and post the claim's reimbursement bill (module docstring). Call inside the
    approval's transaction and organisation context; ``claim`` is the locked row."""
    from numo9.audit import service as audit
    from numo9.ledger.renumber import acting_as

    from .bills import bill_preview, store_figures

    if claim.bill_id is not None:
        return claim.bill  # type: ignore[return-value]
    day = timezone.localdate()
    contact = employee_contact(claim)
    with acting_as(user):
        bill = Bill(
            organisation=claim.organisation,
            contact=contact,
            date=day,
            due_date=day,
            currency=claim.currency,
            tax_mode=TaxMode.INCLUSIVE,
            supplier_invoice_no=claim.number,
            reference=claim.title[:255],
            notes=_("Reimbursement of expense claim %(number)s") % {"number": claim.number},
            created_by=user,
            submitted_by=claim.submitted_by,
            submitted_at=claim.submitted_at,
        )
        bill.save()
        _bill_lines(claim, bill)
        shown = bill_preview(bill)
        if not shown.complete or shown.result.total <= 0:
            raise ReimbursementRefused(
                _("Choose a category for every line of the claim."),
                code="purchases.expense.category_missing",
            )
        store_figures(bill, shown.result)
        bill.number = allocate_number(DocType.BILL, claim.organisation)
        spec = shown.spec(
            source_type=SOURCE_TYPE,
            source_id=str(bill.public_id),
            narration=_("Expense claim %(number)s — %(contact)s")
            % {"number": claim.number, "contact": contact.display_name},
        )
        entry = post_journal(
            JournalSpec(
                date=spec.date,
                lines=reimbursement_lines(tuple(spec.lines), claims_account(claim.organisation)),
                type=spec.type,
                narration=spec.narration,
                source_type=spec.source_type,
                source_id=spec.source_id,
            ),
            organisation=claim.organisation,
            user=user,
            module=LockModule.AP,
        )
        bill.status = BillStatus.AWAITING_PAYMENT
        bill.journal_entry = entry
        bill.approved_by = user
        bill.approved_at = timezone.now()
        bill.save()
        audit.record(
            "purchases.bill.reimbursement_posted",
            obj=bill,
            changes={"status": [BillStatus.DRAFT, BillStatus.AWAITING_PAYMENT]},
            meta={
                "number": bill.number,
                "claim": claim.number,
                "total": f"{bill.total:.2f}",
                "journal": entry.number,
            },
            actor=user,
        )
    claim.contact = contact
    claim.bill = bill
    return bill


def is_reimbursement(bill: Bill) -> bool:
    """The bill reimburses an expense claim (its credit is Unpaid expense claims, not AP)."""
    return ExpenseClaim.objects.filter(bill=bill).exists()
