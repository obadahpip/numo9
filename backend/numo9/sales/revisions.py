"""Invoice revisions — the parts every later D-03b task shares (ADR-0006).

- ``display_number(number, revision)`` — ``101`` for revision 0, ``101-1``, ``101-2`` after.
- ``pdf_snapshot(invoice)`` / ``restore(snapshot)`` — the invoice's PDF context as JSON (amounts
  and dates tagged so they come back as ``Decimal`` and ``date``): what a revision keeps so a
  superseded version can be printed exactly as it was issued (D-03b-T14).
- ``issued_on(revision)`` — the day a revision was issued (kept in its snapshot, else the day
  its row was created, in the organisation's time zone).
- ``record_revision_event(revision, before=, after=, reason=, journal_reversal=, journal_post=,
  user=)`` (D-03b-T15) — the audit event of a revision: the fields that changed with old and new
  values (header fields, totals, tax per component, and each line added, removed or changed),
  the reason, and the ids and numbers of the reversed and posted journals.
  ``field_diffs(before, after)`` computes the changes from two snapshots.
- ``document_snapshot(invoice)`` / ``start_revisions(invoice, entry, user)`` (D-03b-T03) — the
  invoice as entered (header, lines, totals) and revision 0 at first approval;
  ``backfill_revision_zero(apps)`` gives one to posted invoices approved before.
- ``build_revision(invoice)`` (D-03b-T04) — the current revision cloned into an editable
  ``RevisionDraft``; ``draft.document()`` is its snapshot form (equal to the current revision's
  until something is changed).
"""

from __future__ import annotations

import copy
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from .models import Invoice, InvoiceRevision


def display_number(number: str, revision: int) -> str:
    return f"{number}-{revision}" if revision else number


# ---- snapshots ----------------------------------------------------------------------------------


def _pack(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {"__decimal": str(value)}
    if isinstance(value, dt.datetime):
        return {"__datetime": value.isoformat()}
    if isinstance(value, dt.date):
        return {"__date": value.isoformat()}
    if isinstance(value, dict):
        return {str(key): _pack(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_pack(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)  # lazy translations, enums


def restore(value: Any) -> Any:
    """A packed snapshot back to amounts and dates."""
    if isinstance(value, dict):
        if set(value) == {"__decimal"}:
            return Decimal(value["__decimal"])
        if set(value) == {"__date"}:
            return dt.date.fromisoformat(value["__date"])
        if set(value) == {"__datetime"}:
            return dt.datetime.fromisoformat(value["__datetime"])
        return {key: restore(item) for key, item in value.items()}
    if isinstance(value, list):
        return [restore(item) for item in value]
    return value


def pdf_snapshot(invoice: Invoice, issued: dt.date | None = None) -> dict[str, Any]:
    """What a revision keeps of the invoice as issued: ``{"pdf": context, "issued_on": day}``."""
    from numo9.orgsettings.locks import local_date

    from .pdf import invoice_context

    if issued is None:
        from django.utils import timezone

        issued = local_date(invoice.organisation, timezone.now())
    return {"pdf": _pack(invoice_context(invoice)), "issued_on": issued.isoformat()}


def issued_on(revision: InvoiceRevision) -> dt.date:
    from numo9.orgsettings.locks import local_date

    kept = (revision.snapshot or {}).get("issued_on")
    if kept:
        return dt.date.fromisoformat(kept)
    return local_date(revision.organisation, revision.created_at)


# ---- audit (D-03b-T15) ------------------------------------------------------------------------

#: Header fields of a snapshot's PDF context compared between two revisions.
HEADER_FIELDS = (
    "issue_date", "due_date", "terms", "reference", "notes", "currency", "tax_included",
    "subtotal", "discount_total", "total",
)  # fmt: skip
LINE_FIELDS = ("description", "quantity", "unit", "discount_percent", "tax_code", "amount")


def _plain(value: Any) -> Any:
    value = restore(value)
    if isinstance(value, Decimal):
        return f"{value:.2f}" if value == value.quantize(Decimal("0.01")) else str(value)
    if isinstance(value, dt.date):
        return value.isoformat()
    return value


def _line(line: dict[str, Any]) -> dict[str, Any]:
    return {name: _plain(line.get(name)) for name in LINE_FIELDS if name in line}


def field_diffs(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    """``{field: [old, new]}`` between two snapshots: header fields, the customer, and lines by
    position (``lines[2]`` changed; a line only in one side is added or removed)."""
    old, new = before.get("pdf") or {}, after.get("pdf") or {}
    changes: dict[str, list[Any]] = {}
    for name in HEADER_FIELDS:
        a, b = _plain(old.get(name)), _plain(new.get(name))
        if a != b:
            changes[name] = [a, b]
    old_tax = {t["key"]: _plain(t.get("amount")) for t in old.get("taxes") or []}
    new_tax = {t["key"]: _plain(t.get("amount")) for t in new.get("taxes") or []}
    for key in sorted(set(old_tax) | set(new_tax)):  # tax per component, never one lump
        if old_tax.get(key) != new_tax.get(key):
            changes[f"tax[{key}]"] = [old_tax.get(key), new_tax.get(key)]
    a_customer = _plain((old.get("customer") or {}).get("legal_name"))
    b_customer = _plain((new.get("customer") or {}).get("legal_name"))
    if a_customer != b_customer:
        changes["customer"] = [a_customer, b_customer]
    old_lines = [_line(line) for line in old.get("lines") or []]
    new_lines = [_line(line) for line in new.get("lines") or []]
    for index in range(max(len(old_lines), len(new_lines))):
        a_line = old_lines[index] if index < len(old_lines) else None
        b_line = new_lines[index] if index < len(new_lines) else None
        if a_line != b_line:
            changes[f"lines[{index + 1}]"] = [a_line, b_line]
    return changes


def record_revision_event(
    revision: InvoiceRevision,
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    reason: str,
    journal_reversal: Any = None,
    journal_post: Any = None,
    user: Any = None,
) -> Any:
    """Write the audit event ``sales.invoice.revised`` on the invoice (module docstring)."""
    from numo9.audit.service import record

    invoice = revision.invoice

    def journal(entry: Any) -> dict[str, Any] | None:
        if entry is None:
            return None
        return {"id": str(entry.public_id), "number": entry.number}

    return record(
        "sales.invoice.revised",
        obj=invoice,
        actor=user if getattr(user, "is_authenticated", False) else None,
        changes=field_diffs(before, after),
        meta={
            "reason": " ".join((reason or "").split()),
            "revision": revision.revision,
            "number": display_number(invoice.number, revision.revision),
            "journal_reversal": journal(journal_reversal),
            "journal_post": journal(journal_post),
        },
    )


# ---- PDF stamp (D-03b-T14) --------------------------------------------------------------------


def previous_revision(revision: InvoiceRevision) -> InvoiceRevision | None:
    found: InvoiceRevision | None = (
        InvoiceRevision.objects.filter(invoice=revision.invoice, revision__lt=revision.revision)
        .order_by("-revision")
        .first()
    )
    return found


def stamp_context(invoice: Invoice, revision: InvoiceRevision) -> dict[str, Any]:
    """The revision's part of the PDF context: its display number, the stamp of a revision ≥ 1
    ("Revision 1 of invoice 101 — supersedes the version issued on …") and whether it is
    superseded (a later revision exists: the page is watermarked)."""
    current_id = invoice.current_revision_id
    superseded = current_id is not None and current_id != revision.pk
    context: dict[str, Any] = {
        "document_number": display_number(invoice.number, revision.revision),
        "superseded": superseded,
        "superseded_label": _("Superseded"),
        "revision_stamp": "",
        "revision_superseded_on": None,
    }
    if revision.revision:
        previous = previous_revision(revision)
        context["revision_stamp"] = _("Revision %(n)d of invoice %(number)s") % {
            "n": revision.revision,
            "number": invoice.number,
        }
        context["revision_superseded_on"] = issued_on(previous) if previous else None
    return context


# ---- the document snapshot and revision 0 (D-03b-T03, T04) --------------------------------------

#: The header fields a revision keeps (and the revision builder restores, D-03b-T04).
DOCUMENT_FIELDS = (
    "contact_id", "date", "due_date", "terms_id", "reference", "currency", "tax_mode",
    "ship_to_country", "ship_to_province", "discount_type", "discount_value", "notes",
)  # fmt: skip
DOCUMENT_LINE_FIELDS = (
    "position", "item_id", "description", "quantity", "unit_price", "discount_type",
    "discount_value", "account_id", "tax_code_id", "tax_overridden", "tracking",
)  # fmt: skip
TOTAL_FIELDS = ("subtotal", "discount_total", "tax_total", "total")


def document_snapshot(invoice: Any) -> dict[str, Any]:
    """The invoice as entered — header, lines and totals — packed (amounts and dates tagged)."""
    lines = invoice.lines.order_by("position", "pk")
    packed: dict[str, Any] = _pack(
        {
            "header": {name: getattr(invoice, name) for name in DOCUMENT_FIELDS},
            "lines": [
                {name: getattr(line, name) for name in DOCUMENT_LINE_FIELDS} for line in lines
            ],
            "totals": {name: getattr(invoice, name) for name in TOTAL_FIELDS},
        }
    )
    return packed


def revision_snapshot(invoice: Any, issued: dt.date | None = None) -> dict[str, Any]:
    """What a revision keeps: the document as entered and the PDF as issued."""
    return {"document": document_snapshot(invoice), **pdf_snapshot(invoice, issued)}


def start_revisions(invoice: Any, entry: Any, user: Any = None) -> InvoiceRevision:
    """Revision 0 of an invoice just approved (D-03b-T03): its snapshot and the journal of the
    approval; ``current_revision`` points at it."""
    revision = InvoiceRevision(
        organisation=invoice.organisation,
        invoice=invoice,
        revision=0,
        number_display=display_number(invoice.number, 0),
        snapshot=revision_snapshot(invoice),
        total=invoice.total,
        tax_total=invoice.tax_total,
        journal_post=entry,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    revision.save()
    type(invoice)._base_manager.filter(pk=invoice.pk).update(current_revision=revision)
    invoice.current_revision = revision
    return revision


#: Statuses of a posted invoice (every one has a current revision).
POSTED = ("approved", "sent", "partially_paid", "paid", "void")


def backfill_revision_zero(apps: Any) -> int:
    """Revision 0 for every posted invoice that has none (the data migration, D-03b-T03): the
    document snapshot from the invoice's rows, its totals and the approval journal. Returns how
    many it created. ``apps`` is a migration's app registry (or ``django.apps.apps``)."""
    invoices = apps.get_model("sales", "Invoice")
    revisions = apps.get_model("sales", "InvoiceRevision")
    invoice_lines = apps.get_model("sales", "InvoiceLine")
    made = 0
    for invoice in invoices._base_manager.filter(
        status__in=POSTED, current_revision__isnull=True
    ).iterator():
        lines = invoice_lines._base_manager.filter(document_id=invoice.pk).order_by(
            "position", "pk"
        )
        snapshot = {
            "document": _pack(
                {
                    "header": {name: getattr(invoice, name) for name in DOCUMENT_FIELDS},
                    "lines": [
                        {name: getattr(line, name) for name in DOCUMENT_LINE_FIELDS}
                        for line in lines
                    ],
                    "totals": {name: getattr(invoice, name) for name in TOTAL_FIELDS},
                }
            ),
            "issued_on": (
                invoice.approved_at.date() if invoice.approved_at else invoice.date
            ).isoformat(),
        }
        revision = revisions._base_manager.create(
            organisation_id=invoice.organisation_id,
            invoice_id=invoice.pk,
            revision=0,
            number_display=invoice.number,
            snapshot=snapshot,
            total=invoice.total,
            tax_total=invoice.tax_total,
            journal_post_id=invoice.journal_entry_id,
            created_by_id=invoice.approved_by_id,
        )
        invoices._base_manager.filter(pk=invoice.pk).update(current_revision=revision)
        made += 1
    return made


# ---- the revision builder (D-03b-T04) -----------------------------------------------------------


@dataclass
class RevisionDraft:
    """A posted invoice opened for revision: its current revision's header and lines, editable in
    memory (nothing is written until the revision is saved, D-03b-T07). ``base_version`` is the
    invoice's version when opened — the optimistic-concurrency token (D-03b-T06)."""

    invoice_id: int
    revision: int  # the revision it was cloned from
    base_version: int
    header: dict[str, Any]
    lines: list[dict[str, Any]]
    totals: dict[str, Any]
    reason: str = ""

    def document(self) -> dict[str, Any]:
        """The draft in the snapshot's form (packed)."""
        packed: dict[str, Any] = _pack(
            {"header": self.header, "lines": self.lines, "totals": self.totals}
        )
        return packed


def build_revision(invoice: Any) -> RevisionDraft:
    """Clone the invoice's current revision into an editable draft (module docstring)."""
    current = invoice.current_revision
    if current is None:
        raise ValueError(f"{invoice} has no current revision")
    document = restore((current.snapshot or {}).get("document") or {})
    return RevisionDraft(
        invoice_id=invoice.pk,
        revision=current.revision,
        base_version=invoice.version,
        header=copy.deepcopy(document.get("header") or {}),
        lines=copy.deepcopy(document.get("lines") or []),
        totals=copy.deepcopy(document.get("totals") or {}),
    )

