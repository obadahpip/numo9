"""Bill approval and posting (E-02-T05), release of holdbacks (E-02-T06) and void (E-02-T09).

``bill_spec(bill)`` — the journal a bill posts: the D-01 posting preview of its lines, purchase
side (``numo9.documents.posting.preview`` via ``bills.bill_preview``):

- Dr each line's expense or asset account — its net **plus the tax it can't claim**
  (non-recoverable PST, the restricted half of a 50 % meals ITC, all of it before a GST/HST
  registration);
- Dr the input tax control accounts — GST/HST receivable (ITC), QST receivable (ITR) — for the
  claimable part;
- Cr Accounts payable — the total less the holdback;
- Cr Holdbacks payable — the holdback (amount or % of the total), owed to the supplier later
  and moved to AP when released (E-02-T06).

``approve(bill, user)`` — in **one transaction**: lock the bill, refuse what can't be approved
(not a draft or awaiting approval; no supplier invoice number when the organisation requires one;
a number already on another bill of the same supplier, gap-24; a line with an amount but no
account; a total of zero or below — that is a supplier credit), check the **routing rule**
(E-02-T07: only the routed role's holders) and the person's **bill approval limit** (A-03; the
writer of a bill waiting for approval can't approve it), store the
server's figures, take the number (``BILL-0001``) and post through the posting engine (C-02: AP
lock date, closed periods, every journal rule) with the bill as source. All or nothing. What the
preview showed is what posts.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.documents.posting import Preview
from numo9.ledger.models import Account, AccountSubtype, AccountType, LedgerError, SystemRole
from numo9.ledger.renumber import acting_as
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import DocType, LockModule
from numo9.orgsettings.numbering import allocate_number
from numo9.rbac.approvals import assert_can_approve
from numo9.rbac.models import ApprovalDocumentType
from numo9.tenancy.context import org_context

from .bills import bill_preview, store_figures
from .models import Bill, BillStatus
from .uniqueness import number_conflict

SOURCE_TYPE = "purchases.bill"
DOC_TYPE = ApprovalDocumentType.BILL
APPROVABLE = (BillStatus.DRAFT, BillStatus.AWAITING_APPROVAL)
ZERO = Decimal("0.00")
HOLDBACK_CODES = [str(code) for code in range(2030, 2050)]


class BillRefused(LedgerError):
    """A bill action the rules refuse (``code`` names the rule)."""


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _refuse(message: str, code: str, **params: Any) -> BillRefused:
    return BillRefused(message, code=code, params=params or None)


def holdback_account(organisation: Any) -> Account:
    """The Holdbacks payable account (``holdback_payable`` role): the template's, or — for a
    chart loaded before E-02 — created on first use (2030, or the next free code to 2049)."""
    found: Account | None = Account.objects.filter(system_role=SystemRole.HOLDBACK_PAYABLE).first()
    if found is not None:
        return found
    taken = set(Account.objects.filter(code__in=HOLDBACK_CODES).values_list("code", flat=True))
    code = next((c for c in HOLDBACK_CODES if c not in taken), None)
    if code is None:
        raise _refuse(
            _("Add a Holdbacks payable account to the chart of accounts to post holdbacks."),
            "purchases.bill.holdback_account",
        )
    account = Account(
        organisation=organisation,
        code=code,
        name_i18n={"en-ca": "Holdbacks payable", "fr-ca": "Retenues de garantie à payer"},
        type=AccountType.LIABILITY,
        subtype=AccountSubtype.CURRENT_LIABILITY,
        gifi_id="2623",
        system_role=SystemRole.HOLDBACK_PAYABLE,
        require_contact=True,
    )
    account.save()
    return account


def bill_lines(bill: Bill, shown: Preview) -> tuple[LineSpec, ...]:
    """The preview's journal lines with the holdback moved from AP to Holdbacks payable."""
    held = Decimal(bill.holdback_amount)
    lines = list(shown.lines)
    if held <= 0:
        return tuple(lines)
    ap = Account.objects.get(system_role=SystemRole.AP)
    for index, line in enumerate(lines):
        account_id = line.account.pk if isinstance(line.account, Account) else line.account
        if account_id == ap.pk and line.credit >= held:
            lines[index] = LineSpec(
                line.account,
                credit=line.credit - held,
                description=line.description,
                contact=line.contact,
                tracking=dict(line.tracking or {}),
            )
            lines.insert(
                index + 1,
                LineSpec(
                    holdback_account(bill.organisation),
                    credit=held,
                    description=_("Holdback"),
                    contact=line.contact,
                ),
            )
            return tuple(line for line in lines if line.debit or line.credit)
    raise _refuse(  # pragma: no cover — a bill's AP credit is its total
        _("The holdback is more than the amount owed on the bill."),
        "purchases.bill.holdback_too_large",
    )


def bill_spec(bill: Bill, shown: Preview | None = None) -> JournalSpec:
    """The journal the bill posts (module docstring)."""
    shown = shown or bill_preview(bill)
    spec = shown.spec(
        source_type=SOURCE_TYPE,
        source_id=str(bill.public_id),
        narration=_("Bill %(number)s — %(contact)s")
        % {
            "number": bill.number or bill.supplier_invoice_no or _("draft"),
            "contact": bill.contact.display_name,
        },
    )
    return JournalSpec(
        date=spec.date,
        lines=bill_lines(bill, shown),
        type=spec.type,
        narration=spec.narration,
        source_type=spec.source_type,
        source_id=spec.source_id,
    )


def _check_supplier_invoice(locked: Bill) -> None:
    from numo9.orgsettings.service import get_settings

    if not locked.supplier_invoice_no.strip():
        if get_settings(locked.organisation).bill_requires_supplier_invoice_no:
            raise _refuse(
                _("Enter the supplier's invoice number before approving the bill."),
                "purchases.bill.supplier_invoice_required",
            )
        return
    taken = number_conflict(locked.contact, locked.supplier_invoice_no, exclude=locked)
    if taken is not None:
        raise _refuse(
            _("%(supplier)s's invoice %(number)s is already on %(bill)s."),
            "purchases.bill.duplicate_number",
            supplier=locked.contact.display_name,
            number=locked.supplier_invoice_no,
            bill=taken.number or _("a draft bill"),
        )


def approve(bill: Bill, user: Any, *, with_variance: bool = False) -> Bill:
    """Approve and post (module docstring); returns the bill awaiting payment. A bill whose PO
    match panel (E-02-T08) has an amber or red line is approved only ``with_variance`` — "Approve
    with variance" (E-02-T13), recorded in the audit event."""
    from numo9.audit import service as audit

    person = _person(user)
    with org_context(bill.organisation), transaction.atomic(), acting_as(person):
        locked = Bill._base_manager.select_for_update().get(pk=bill.pk)
        if locked.status not in APPROVABLE:
            raise _refuse(
                _("%(bill)s is already %(status)s."),
                "purchases.bill.not_draft",
                bill=str(locked),
                status=str(BillStatus(locked.status).label).lower(),
            )
        _check_supplier_invoice(locked)
        shown = bill_preview(locked)
        if not shown.complete:
            raise _refuse(
                _("Every line with an amount needs an account before the bill is approved."),
                "purchases.bill.incomplete",
            )
        if shown.result.total <= ZERO:
            raise _refuse(
                _(
                    "A bill's total must be more than zero: for money the supplier owes you, "
                    "enter a supplier credit."
                ),
                "purchases.bill.total_not_positive",
            )
        if locked.status == BillStatus.AWAITING_APPROVAL:
            authors = {locked.created_by_id, locked.submitted_by_id} - {None}
            if getattr(person, "pk", None) in authors:
                raise _refuse(
                    _("You wrote or submitted this bill: someone else must approve it."),
                    "purchases.bill.self_approval",
                )
        from .routing import may_approve, route

        routing = route(locked, total=Decimal(shown.result.total))
        if not may_approve(locked, person, routing):
            raise _refuse(
                _("%(why)s: you aren't one of them."),
                "purchases.bill.not_routed_to_you",
                why=routing.explanation,
            )
        assert_can_approve(
            person,
            DOC_TYPE,
            Decimal(shown.result.total),
            organisation=locked.organisation,
            exclude=[p for p in (locked.created_by, locked.submitted_by) if p is not None],
        )
        from .bill_from_po import apply_billed, has_variance

        variance = locked.purchase_order_id is not None and has_variance(locked)
        if variance and not with_variance:
            raise _refuse(
                _(
                    "The bill doesn't match its purchase order and receipts: review the match "
                    "panel and approve with variance."
                ),
                "purchases.bill.variance",
            )
        store_figures(locked, shown.result)
        locked.number = locked.number or allocate_number(DocType.BILL, locked.organisation)
        entry = post_journal(
            bill_spec(locked, shown),
            organisation=locked.organisation,
            user=person,
            module=LockModule.AP,
        )
        apply_billed(locked, 1)
        previous = locked.status
        locked.status = BillStatus.AWAITING_PAYMENT
        locked.journal_entry = entry
        locked.approved_by = person
        locked.approved_at = timezone.now()
        locked.version += 1
        locked.save()
        audit.record(
            "purchases.bill.approved",
            obj=locked,
            changes={"status": [previous, BillStatus.AWAITING_PAYMENT]},
            meta={
                "number": locked.number,
                "total": f"{locked.total:.2f}",
                "holdback": f"{locked.holdback_amount:.2f}",
                "with_variance": variance,
            },
            actor=person,
        )
        return locked


# ---- holdback release (E-02-T06) ---------------------------------------------------------------

RELEASABLE = (BillStatus.AWAITING_PAYMENT, BillStatus.PARTIALLY_PAID, BillStatus.PAID)


def release_holdback(
    bill: Bill, user: Any, *, amount: Decimal | None = None, date: Any = None
) -> Bill:
    """Release all or part of a bill's holdback: **Dr Holdbacks payable / Cr Accounts payable**
    (the supplier's contact on both), on ``date`` (today by default) through the posting engine
    (AP lock, periods); the amount becomes payable on the bill (``amount_due``). Refused for a
    bill that isn't posted, a void bill, nothing held, or more than is still held."""
    from django.utils import timezone as tz

    from numo9.audit import service as audit
    from numo9.ledger.models import JournalType

    person = _person(user)
    with org_context(bill.organisation), transaction.atomic(), acting_as(person):
        locked = Bill._base_manager.select_for_update().get(pk=bill.pk)
        held = locked.holdback_outstanding
        if locked.status not in RELEASABLE or held <= 0:
            raise _refuse(
                _("%(bill)s has no holdback to release."),
                "purchases.bill.no_holdback",
                bill=str(locked),
            )
        value = held if amount is None else Decimal(amount).quantize(Decimal("0.01"))
        if value <= 0 or value > held:
            raise _refuse(
                _("Release between 0.01 and %(held)s: that is what is still held."),
                "purchases.bill.holdback_amount",
                held=f"{held:.2f}",
            )
        day = date or tz.localdate()
        ap = Account.objects.get(system_role=SystemRole.AP)
        entry = post_journal(
            JournalSpec(
                date=day,
                type=JournalType.PURCHASE,
                narration=_("Holdback released — bill %(number)s, %(contact)s")
                % {"number": locked.number, "contact": locked.contact.display_name},
                source_type=SOURCE_TYPE,
                source_id=str(locked.public_id),
                lines=(
                    LineSpec(
                        holdback_account(locked.organisation),
                        debit=value,
                        contact=locked.contact,
                        description=_("Holdback released"),
                    ),
                    LineSpec(
                        ap, credit=value, contact=locked.contact, description=_("Holdback released")
                    ),
                ),
            ),
            organisation=locked.organisation,
            user=person,
            module=LockModule.AP,
        )
        before = locked.holdback_released
        locked.holdback_released = Decimal(locked.holdback_released) + value
        if locked.status == BillStatus.PAID:
            locked.status = BillStatus.PARTIALLY_PAID  # the released part is owed now
        locked.version += 1
        locked.save()
        audit.record(
            "purchases.bill.holdback_released",
            obj=locked,
            changes={"holdback_released": [f"{before:.2f}", f"{locked.holdback_released:.2f}"]},
            meta={"number": locked.number, "amount": f"{value:.2f}", "journal": entry.number},
            actor=person,
        )
        return locked
