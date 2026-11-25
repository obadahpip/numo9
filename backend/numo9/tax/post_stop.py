"""Documents after a stop (G-03b-T05): tax charged or claimed while not registered.

A registration's **tax codes** are the codes with a component of its kind — GST/HST (RT) or QST.
``post_stop_documents(registration)`` lists the invoices, credit notes, bills and supplier
credits (not void, not deleted) dated in a **not-registered gap** (after a stop, before the
restart) that use one of them on a line: the review list of the stop's impact preview.

``stop_warning(organisation, date, tax_codes)`` is the warning a document gets in its editor
(G-03b-T12): ``REGISTRATION_STOPPED`` when ``date`` falls in a gap of a registration whose tax
codes are among ``tax_codes`` — never a block (a late document for a date before the stop is
fine; one after it needs a different code).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext as _

from .models import TaxCode

CODE = "REGISTRATION_STOPPED"
#: The tax component kinds each filing registration type collects and claims.
KINDS: dict[str, tuple[str, ...]] = {"rt": ("gst", "hst"), "qst": ("qst",)}


def registration_codes(registration: Any) -> Q:
    """A ``TaxCode`` filter: the codes with a component of the registration's kind."""
    return Q(components__component__kind__in=KINDS.get(registration.type, ()))


def _gap_filter(spans: list[tuple[dt.date, dt.date | None]], field: str = "date") -> Q:
    query = Q(pk__in=[])
    for start, end in spans:
        part = Q(**{f"{field}__gte": start})
        if end is not None:
            part &= Q(**{f"{field}__lte": end})
        query |= part
    return query


def _sources() -> list[tuple[str, Any, str]]:
    from numo9.purchases.models import Bill, SupplierCredit
    from numo9.sales.models import CreditNote, Invoice

    return [
        ("invoice", Invoice, "sales/invoices"),
        ("credit_note", CreditNote, "sales/credit-notes"),
        ("bill", Bill, "purchases/bills"),
        ("supplier_credit", SupplierCredit, "purchases/supplier-credits"),
    ]


def post_stop_documents(registration: Any) -> list[dict[str, Any]]:
    """The documents dated while not registered that use the registration's tax codes."""
    from .filing_service import gaps

    spans = gaps(registration)
    if not spans:
        return []
    codes = TaxCode.objects.filter(registration_codes(registration)).values("pk")
    org = registration.organisation
    out: list[dict[str, Any]] = []
    for kind, model, path in _sources():
        rows = (
            model.objects.filter(_gap_filter(spans), lines__tax_code__in=codes)
            .filter(deleted_at__isnull=True)
            .exclude(status="void")
            .distinct()
            .order_by("date", "pk")
        )
        for doc in rows:
            out.append(
                {
                    "kind": kind,
                    "id": str(doc.public_id),
                    "number": doc.number,
                    "date": doc.date.isoformat(),
                    "total": f"{doc.total:.2f}",
                    "url": f"/o/{org.public_id}/{path}/{doc.public_id}",
                }
            )
    out.sort(key=lambda r: (r["date"], r["kind"]))
    return out


def stop_warning(
    organisation: Any, date: dt.date, tax_codes: Iterable[Any]
) -> dict[str, Any] | None:
    """The ``REGISTRATION_STOPPED`` warning for a document dated ``date`` with ``tax_codes``
    (codes or their ids), or None."""
    from numo9.orgsettings.models import FILING_TYPES, TaxRegistration

    from .filing_service import gaps, in_gap

    ids = {getattr(code, "pk", code) for code in tax_codes if code is not None}
    if not ids:
        return None
    registrations = TaxRegistration.objects.filter(
        organisation=organisation, type__in=FILING_TYPES, deleted_at__isnull=True
    )
    for registration in registrations:
        spans = gaps(registration)
        if not spans or not in_gap(registration, date, spans):
            continue
        if TaxCode.objects.filter(registration_codes(registration), pk__in=ids).exists():
            stopped = max(start for start, _end in spans if start <= date) - dt.timedelta(days=1)
            return {
                "code": CODE,
                "registration": str(registration.public_id),
                "message": _(
                    "%(registration)s wasn't registered on %(date)s (filing stopped after "
                    "%(stop)s): this document shouldn't use its tax codes."
                )
                % {
                    "registration": str(registration),
                    "date": date.isoformat(),
                    "stop": stopped.isoformat(),
                },
            }
    return None
