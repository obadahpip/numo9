"""Cancellation and the full data export (U-04-T11).

**Cancellation** — ``cancel(organisation)`` sets the Stripe subscription to cancel **at the end
of the paid period** (``cancel_at_period_end``; nothing is refunded, access continues until then)
and starts the data export; ``resume(organisation)`` undoes it before the period ends. When the
period ends Stripe deletes the subscription and the organisation becomes *cancelled* (read and
export only, U-04-T07).

**Export** — the organisation job ``numo9.billing.export_organisation`` writes one ZIP to the
organisation's prefix in the files bucket (``exports/``) and records its key in the job result;
``export_link`` gives a fresh 5-minute signed URL (A-06) each time it is asked. The ZIP holds:

- ``README.txt`` — what is in the file, when it was made, the organisation;
- ``csv/<dataset>.csv`` — one CSV (UTF-8 with BOM, opens in Excel) per dataset;
- ``numo9-export.xlsx`` — the same datasets, one sheet each;
- ``json/ledger.json`` — every journal entry with its lines (the ledger, machine-readable);
- ``documents/`` — the organisation's stored documents (PDFs, images…) as uploaded; quarantined
  or unscanned files are left out and listed in ``csv/documents.csv``.

Datasets are registered (``register_dataset(name, rows)``) by the module that owns them; Phase 0
has the organisation settings, tax registrations, lock dates, contacts, the chart of accounts,
journal lines, documents and Numo9 invoices. ``datasets()`` lists them all: the export test checks
the ZIP holds every one.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from numo9.entitlements.models import SubscriptionStatus
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.jobs.models import JobRun
from numo9.jobs.queues import IO
from numo9.jobs.runtime import current_job, org_job, report_progress, start_job
from numo9.tenancy.context import current_org, org_context
from numo9.tenancy.models import Organisation

from .customers import locked_subscription
from .gateway import BillingGateway, get_gateway

EXPORT_JOB = "numo9.billing.export_organisation"
ZIP_MIME = "application/zip"


@dataclass(frozen=True)
class Dataset:
    name: str
    columns: tuple[str, ...]
    rows: Callable[[Organisation], Iterable[tuple[Any, ...]]]


_datasets: dict[str, Dataset] = {}


def register_dataset(
    name: str, columns: tuple[str, ...]
) -> Callable[[Callable[[Organisation], Iterable[tuple[Any, ...]]]], Any]:
    def decorator(rows: Callable[[Organisation], Iterable[tuple[Any, ...]]]) -> Any:
        _datasets[name] = Dataset(name, columns, rows)
        return rows

    return decorator


def datasets() -> list[Dataset]:
    return [_datasets[name] for name in sorted(_datasets)]


# ---- Phase 0 datasets ---------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


@register_dataset(
    "organisation_settings",
    ("legal_name", "display_name", "province", "postal_code", "fiscal_year_end", "currency"),
)
def _settings(organisation: Organisation) -> Iterable[tuple[Any, ...]]:
    from numo9.orgsettings.service import get_settings

    s = get_settings(organisation)
    yield (
        s.legal_name,
        s.display_name,
        s.mailing_province,
        s.mailing_postal_code,
        f"{s.fye_month:02d}-{s.fye_day:02d}",
        s.base_currency,
    )


@register_dataset(
    "tax_registrations", ("type", "number", "effective_from", "effective_to", "status")
)
def _registrations(organisation: Organisation) -> Iterable[tuple[Any, ...]]:
    from numo9.orgsettings.models import TaxRegistration

    for r in TaxRegistration.objects.filter(deleted_at__isnull=True).order_by("type", "pk"):
        yield (r.type, r.number, r.effective_from, r.effective_to, r.status)


@register_dataset("lock_dates", ("module", "level", "date", "reason"))
def _locks(organisation: Organisation) -> Iterable[tuple[Any, ...]]:
    from numo9.orgsettings.models import LockDate

    for lock in LockDate.objects.filter(deleted_at__isnull=True).order_by("module", "level"):
        yield (lock.module, lock.level, lock.date, lock.reason)


@register_dataset(
    "contacts",
    ("number", "display_name", "legal_name", "roles", "bn", "email", "currency", "status"),
)
def _contacts(organisation: Organisation) -> Iterable[tuple[Any, ...]]:
    from numo9.contacts.models import Contact

    for c in Contact.objects.filter(deleted_at__isnull=True).order_by("number"):
        email = c.people.filter(deleted_at__isnull=True).values_list("email", flat=True).first()
        yield (
            c.number,
            c.display_name,
            c.legal_name,
            c.roles,
            c.bn,
            email or "",
            c.currency,
            c.status,
        )


@register_dataset("chart_of_accounts", ("code", "name", "type", "subtype", "gifi", "status"))
def _accounts(organisation: Organisation) -> Iterable[tuple[Any, ...]]:
    from numo9.ledger.models import Account

    for a in Account.objects.filter(deleted_at__isnull=True).order_by("code"):
        yield (a.code, a.name, a.type, a.subtype, a.gifi_id or "", a.status)


@register_dataset(
    "journal_lines",
    ("journal", "date", "status", "line", "account", "debit", "credit", "book", "description"),
)
def _journal_lines(organisation: Organisation) -> Iterable[tuple[Any, ...]]:
    from numo9.ledger.models import JournalLine

    lines = (
        JournalLine.objects.filter(entry__status__in=("posted", "reversed"))
        .select_related("entry", "account")
        .order_by("entry__number", "line_no")
    )
    for line in lines:
        yield (
            line.entry.number,
            line.entry.date,
            line.entry.status,
            line.line_no,
            line.account.code,
            line.debit,
            line.credit,
            line.book,
            line.description,
        )


@register_dataset("documents", ("name", "type", "size", "status", "uploaded_at", "in_zip_as"))
def _documents(organisation: Organisation) -> Iterable[tuple[Any, ...]]:
    for document, path in _document_files(organisation):
        yield (
            document.name,
            document.mime,
            document.size,
            document.status,
            document.created_at,
            path,
        )


@register_dataset(
    "numo9_invoices", ("number", "status", "issued_at", "total", "paid", "currency", "pdf")
)
def _invoices(organisation: Organisation) -> Iterable[tuple[Any, ...]]:
    from .models import PlatformInvoice

    for i in PlatformInvoice.objects.order_by("issued_at", "pk"):
        yield (
            i.number,
            i.status,
            i.issued_at,
            f"{i.total_cents / 100:.2f}",
            f"{i.amount_paid_cents / 100:.2f}",
            i.currency,
            i.pdf_url,
        )


def _document_files(organisation: Organisation) -> list[tuple[Any, str]]:
    from numo9.files.models import Document
    from numo9.files.storage import safe_filename

    out: list[tuple[Any, str]] = []
    used: set[str] = set()
    for document in Document.objects.filter(deleted_at__isnull=True).order_by("created_at", "pk"):
        if not document.is_clean:
            out.append((document, ""))
            continue
        name = safe_filename(document.name) or "document"
        path = f"documents/{name}"
        n = 1
        while path in used:
            n += 1
            stem, dot, ext = name.rpartition(".")
            path = f"documents/{stem or name}-{n}{dot}{ext if stem else ''}"
        used.add(path)
        out.append((document, path))
    return out


def _ledger_json(organisation: Organisation) -> bytes:
    from numo9.ledger.models import JournalEntry
    from numo9.ledger.sequence import format_journal_number

    entries = (
        JournalEntry.objects.filter(status__in=("posted", "reversed"))
        .prefetch_related("lines__account")
        .order_by("number")
    )
    body = [
        {
            "number": format_journal_number(organisation, e.number),
            "date": e.date.isoformat(),
            "type": e.type,
            "status": e.status,
            "narration": e.narration,
            "source": {"type": e.source_type, "id": e.source_id} if e.source_type else None,
            "lines": [
                {
                    "line": line.line_no,
                    "account": line.account.code,
                    "debit": f"{line.debit:.2f}",
                    "credit": f"{line.credit:.2f}",
                    "book": line.book,
                    "description": line.description,
                }
                for line in sorted(e.lines.all(), key=lambda line: line.line_no)
            ],
        }
        for e in entries
    ]
    return json.dumps(
        {"organisation": organisation.name, "journals": body}, ensure_ascii=False, indent=2
    ).encode("utf-8")


def build_zip(organisation: Organisation) -> bytes:
    """The export ZIP of the active organisation (see the module docstring)."""
    from openpyxl import Workbook

    from numo9.files.storage import open_object

    buffer = io.BytesIO()
    workbook = Workbook()
    workbook.remove(workbook.active)
    all_sets = datasets()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "README.txt",
            f"Numo9 export of {organisation.name}\n"
            f"Made {timezone.now().isoformat(timespec='seconds')}\n\n"
            "csv/          one CSV file per dataset (UTF-8)\n"
            "numo9-export.xlsx   the same datasets, one sheet each\n"
            "json/ledger.json    every journal entry with its lines\n"
            "documents/    the stored documents as uploaded\n",
        )
        for done, dataset in enumerate(all_sets, 1):
            rows = [tuple(_plain(v) for v in row) for row in dataset.rows(organisation)]
            text = io.StringIO()
            writer = csv.writer(text)
            writer.writerow(dataset.columns)
            writer.writerows(rows)
            archive.writestr(f"csv/{dataset.name}.csv", "﻿" + text.getvalue())
            sheet = workbook.create_sheet(dataset.name[:31])
            sheet.append(list(dataset.columns))
            for row in rows:
                sheet.append([str(v) if not isinstance(v, int | float) else v for v in row])
            if current_job() is not None:
                report_progress(done, len(all_sets) + 2)
        xlsx = io.BytesIO()
        workbook.save(xlsx)
        archive.writestr("numo9-export.xlsx", xlsx.getvalue())
        archive.writestr("json/ledger.json", _ledger_json(organisation))
        for document, path in _document_files(organisation):
            if path:
                with open_object(document.file_key) as handle:
                    archive.writestr(path, handle.read())
    return buffer.getvalue()


@org_job(name=EXPORT_JOB, queue=IO, max_retries=3)
def export_organisation(**kwargs: Any) -> dict[str, Any]:
    from numo9.files.storage import new_key, put_bytes

    organisation = current_org()
    assert organisation is not None  # noqa: S101 - organisation jobs run in their context
    data = build_zip(organisation)
    stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    key = new_key(organisation, f"exports/numo9-export-{stamp}.zip")
    put_bytes(key, data, ZIP_MIME)
    return {"key": key, "size": len(data), "datasets": [d.name for d in datasets()]}


def start_export(organisation: Organisation, user: Any = None) -> JobRun:
    run: JobRun = start_job(export_organisation, organisation=organisation, created_by=user)
    return run


def latest_export(organisation: Organisation) -> JobRun | None:
    with org_context(organisation):
        run: JobRun | None = (
            JobRun.objects.filter(task_name=EXPORT_JOB).order_by("-created_at", "-pk").first()
        )
    return run


def export_link(run: JobRun) -> Any:
    """A fresh signed download URL for a finished export, or None."""
    from numo9.files.storage import signed_key_url

    key = (run.result or {}).get("key") if isinstance(run.result, dict) else None
    if run.status != "succeeded" or not key:
        return None
    organisation = run.organisation
    name = f"numo9-export-{organisation.name}.zip" if organisation else "numo9-export.zip"
    return signed_key_url(key, name=name, mime=ZIP_MIME, download=True)


def _set_cancel(
    organisation: Organisation, cancel: bool, user: Any, gateway: BillingGateway | None
) -> Any:
    gateway = gateway or get_gateway()
    with org_context(organisation), transaction.atomic():
        subscription = locked_subscription(organisation)
        if not subscription.stripe_subscription_id or subscription.status not in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAST_DUE,
        ):
            raise api_error(errors.BILLING_NOT_PAYING)
        gateway.set_cancel_at_period_end(
            subscription=subscription.stripe_subscription_id,
            cancel=cancel,
            idempotency_key=f"numo9-cancel-{subscription.public_id}-{int(cancel)}-"
            f"{timezone.now():%Y%m%d%H%M}",
        )
        subscription.cancel_at_period_end = cancel
        subscription.save(update_fields=["cancel_at_period_end", "updated_at"])
        return subscription


def cancel(
    organisation: Organisation, user: Any = None, gateway: BillingGateway | None = None
) -> tuple[Any, JobRun]:
    """Cancel at the period end and start the export (its link is on the billing page)."""
    subscription = _set_cancel(organisation, True, user, gateway)
    return subscription, start_export(organisation, user)


def resume(
    organisation: Organisation, user: Any = None, gateway: BillingGateway | None = None
) -> Any:
    return _set_cancel(organisation, False, user, gateway)
