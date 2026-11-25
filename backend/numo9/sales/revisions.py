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
"""

from __future__ import annotations

import datetime as dt
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
