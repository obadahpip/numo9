"""Saving a revision of a posted invoice (D-03b, ADR-0006).

Concurrency (D-03b-T06): ``lock_for_revision(invoice, version)`` — inside the saving
transaction, ``SELECT … FOR UPDATE`` on the invoice, then compare its ``version`` with the one the
editor opened (``RevisionDraft.base_version``). A mismatch is a ``RevisionConflict`` (HTTP 409,
``sales.revision.conflict``, carrying the invoice's current version): someone else saved first,
nothing is written, and the editor offers to reload. Two simultaneous saves of the same version
are serialised by the row lock: the first saves, the second sees the new version and is refused —
never a lost update.

Numbering (D-03b-T08): ``next_revision(locked)`` gives the revision's number — one more than the
highest the invoice has — and is called only once the invoice row is locked, in the transaction
that posts the revision. Saves of the same invoice wait for each other on that lock, so the
suffixes are sequential ("101-1", "101-2", …) whatever the concurrency, and gap-free: a save that
fails rolls its number back with everything else, and the next one takes it.
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError

from .models import Invoice


class RevisionConflict(LedgerError):
    """Someone else saved the invoice since it was opened (409)."""

    status_code = 409

    def __init__(self, invoice: Invoice, version: int) -> None:
        super().__init__(
            _(
                "Someone else revised %(invoice)s since you opened it: reload it to see their "
                "changes."
            )
            % {"invoice": invoice.number or str(invoice)},
            code="sales.revision.conflict",
            params={"version": str(invoice.version), "opened": str(version)},
        )
        self.current_version = invoice.version


def lock_for_revision(invoice: Invoice | Any, version: int) -> Invoice:
    """Lock the invoice row and check the version (module docstring); call inside the saving
    transaction. Returns the locked invoice."""
    locked: Invoice = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
    if locked.version != version:
        raise RevisionConflict(locked, version)
    return locked


def next_revision(locked: Invoice) -> int:
    """The number of the invoice's next revision (module docstring): call with the invoice row
    locked (``lock_for_revision``), inside the transaction that records the revision."""
    from django.db.models import Max

    from .models import InvoiceRevision

    top = InvoiceRevision._base_manager.filter(invoice_id=locked.pk).aggregate(top=Max("revision"))
    return int(top["top"] if top["top"] is not None else -1) + 1


# ---- posting a revision (D-03b-T07) ------------------------------------------------------------

#: Posted invoices that can be revised (a void invoice can't).
REVISABLE = ("approved", "sent", "partially_paid", "paid")


class RevisionRefused(LedgerError):
    """A revision the posting rules refuse (``code`` names the rule)."""


def _apply(invoice: Invoice, draft: Any) -> None:
    """Write the draft's header and lines on the invoice rows (they hold the current revision)."""
    from .models import InvoiceLine
    from .revisions import DOCUMENT_FIELDS, DOCUMENT_LINE_FIELDS

    for name in DOCUMENT_FIELDS:
        if name in draft.header:
            setattr(invoice, name, draft.header[name])
    invoice.save()
    InvoiceLine._base_manager.filter(document=invoice).delete()
    for position, line in enumerate(draft.lines):
        values = {name: line[name] for name in DOCUMENT_LINE_FIELDS if name in line}
        values["position"] = position
        values.setdefault("tracking", {})
        InvoiceLine(organisation=invoice.organisation, document=invoice, **values).save()


def revise(invoice: Invoice, draft: Any, user: Any = None, *, late_adjustment: bool = False) -> Any:
    """Save ``draft`` as the invoice's next revision, in **one transaction** (ADR-0006):

    1. lock the invoice and compare the version the draft was opened at (T06: conflict, 409);
    2. validate the change (T05) — a void invoice isn't revised;
    3. write the draft on the invoice rows and recalculate them (the server's figures);
    4. the lock rules (D-03b-T10) on the invoice date **and** on the date of the version it
       reverses: the AR lock refuses, naming it, late or not; a filed GST/HST (QST) period
       refuses naming the period and its confirmation — unless the period is unlocked or
       ``late_adjustment`` is set: then the journals post into the filed period and their tax
       difference is reported on the next open return (T11, G-03-T08): the reversal's tax and
       the new tax are carried there as late adjustments of the revision's two journals (the
       filed return never changes), their net — the revision's tax difference — in the audit
       event (``late_adjustment_summary``);
    5. **reverse** the previous revision's journal (on its own date: the old posting nets to
       zero where it was) and **post** the new revision's journal (on the invoice date), through
       the posting engine;
    6. record revision n + 1 ("101-1", numbered under the row lock, T08) with its snapshot,
       totals, reason and **both journals**; the previous one is superseded;
       ``current_revision`` and ``journal_entry`` move to it; the audit event has the field
       diffs (T15).

    Any failure rolls everything back: never a reversal without its re-post. A revision can't
    bring the total below what is already paid (until D-03b-T09 moves the excess to credit)."""
    import contextlib

    from django.db import transaction
    from django.utils import timezone

    from numo9.ledger.renumber import acting_as
    from numo9.ledger.services import post_journal, reverse
    from numo9.orgsettings.models import LockModule
    from numo9.tax.returns import late_adjustments
    from numo9.tenancy.context import org_context

    from .models import InvoiceRevision
    from .period_checks import assert_postable
    from .posting import SOURCE_TYPE, invoice_preview, store_figures
    from .revisions import (
        display_number,
        late_adjustment_summary,
        record_revision_event,
        revision_snapshot,
        validate_revision,
    )

    person = user if getattr(user, "is_authenticated", False) else None
    with (
        org_context(invoice.organisation),
        transaction.atomic(),
        acting_as(person),
        late_adjustments() if late_adjustment else contextlib.nullcontext(),
    ):
        locked = lock_for_revision(invoice, draft.base_version)
        if locked.status not in REVISABLE or locked.current_revision is None:
            raise RevisionRefused(
                _("%(invoice)s can't be revised: only a posted invoice that isn't void can."),
                code="sales.revision.not_revisable",
                params={"invoice": str(locked)},
            )
        validate_revision(locked, draft)
        previous = InvoiceRevision._base_manager.select_for_update().get(
            pk=locked.current_revision.pk
        )
        before = previous.snapshot
        _apply(locked, draft)
        shown = invoice_preview(locked)
        if not shown.complete:
            raise RevisionRefused(
                _("Every line with an amount needs an account before the revision is saved."),
                code="sales.revision.incomplete",
            )
        if shown.result.total <= 0:
            raise RevisionRefused(
                _("An invoice's total stays above zero: credit the customer with a credit note."),
                code="sales.revision.total_not_positive",
            )
        if shown.result.total < locked.amount_paid:
            raise RevisionRefused(
                _(
                    "%(paid)s is already paid on this invoice: a revision can't bring its total "
                    "below that."
                )
                % {"paid": f"{locked.amount_paid:.2f}"},
                code="sales.revision.below_paid",
            )
        assert_postable(locked, shown.lines, shown.date, person, "revise")
        store_figures(locked, shown.result)
        locked.save(update_fields=["subtotal", "discount_total", "tax_total", "total"])
        number = next_revision(locked)  # under the row lock: sequential, gap-free (T08)
        shown_as = display_number(locked.number, number)
        posted = previous.journal_post or locked.journal_entry
        if posted is None:  # pragma: no cover — a posted invoice has its journal (DB check)
            raise RevisionRefused(_("The invoice has no posted journal."), code="sales.revision")
        # T10: the reversal posts on the previous version's date — the same lock rules apply there
        # (an invoice dated in a filed period can't move out of it without a late adjustment).
        assert_postable(
            locked, posted.lines.select_related("account"), posted.date, person, "revise"
        )
        reversal = reverse(
            posted,
            date=posted.date,
            narration=_("Reversal of invoice %(number)s, revised as %(revision)s")
            % {"number": previous.number_display or locked.number, "revision": shown_as},
            user=person,
            module=LockModule.AR,
        )
        entry = post_journal(
            shown.spec(
                source_type=SOURCE_TYPE,
                source_id=str(locked.public_id),
                narration=_("Invoice %(number)s — %(contact)s")
                % {"number": shown_as, "contact": locked.contact.display_name},
            ),
            organisation=locked.organisation,
            user=person,
            module=LockModule.AR,
        )
        locked.refresh_from_db()
        revision = InvoiceRevision(
            organisation=locked.organisation,
            invoice=locked,
            revision=number,
            number_display=shown_as,
            snapshot=revision_snapshot(locked),
            total=locked.total,
            tax_total=locked.tax_total,
            reason=" ".join(draft.reason.split()),
            journal_reversal=reversal,
            journal_post=entry,
            created_by=person,
        )
        revision.save()
        previous.superseded_at = timezone.now()
        previous.save(update_fields=["superseded_at"])
        locked.current_revision = revision
        locked.journal_entry = entry
        locked.version += 1
        locked.save(update_fields=["current_revision", "journal_entry", "version"])
        record_revision_event(
            revision,
            before=before,
            after=revision.snapshot,
            reason=draft.reason,
            journal_reversal=reversal,
            journal_post=entry,
            user=person,
            late_adjustment=late_adjustment_summary(revision) if late_adjustment else None,
        )
        return revision
