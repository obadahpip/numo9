"""D-03b-T08 — the revision number is allocated inside the posting transaction, under the invoice
row lock: "101-1", "101-2", … are sequential and gap-free — a failed save leaves no hole, and
editors saving the same invoice at the same time (each retrying after a conflict) end with
consecutive suffixes, one per save, never twice the same."""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection

from numo9.sales.models import Invoice, InvoiceRevision
from numo9.sales.posting import approve
from numo9.sales.revise import RevisionConflict, next_revision, revise
from numo9.sales.revisions import build_revision
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

D = Decimal


def _opened(invoice: Invoice, quantity: str, reason: str) -> Any:
    with org_context(invoice.organisation):
        fresh = Invoice.objects.get(pk=invoice.pk)
        draft_ = build_revision(fresh)
    draft_.lines[0]["quantity"] = D(quantity)
    draft_.reason = reason
    return draft_


def _numbers(invoice: Invoice) -> list[tuple[int, str]]:
    with org_context(invoice.organisation):
        return list(
            InvoiceRevision.objects.filter(invoice=invoice)
            .order_by("revision")
            .values_list("revision", "number_display")
        )


@pytest.mark.django_db
def test_suffixes_follow_each_other_and_a_failure_leaves_no_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from numo9.ledger import services

    books = sales_books()
    owner = people(books["org"])["owner"]
    invoice = approve(draft(books, [("10", "100.00", "sales.ON.standard")]), owner)
    with org_context(books["org"]):
        assert next_revision(invoice) == 1
    first = revise(invoice, _opened(invoice, "9", "Nine hours"), owner)
    real = services.post_journal

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("disk full")

    monkeypatch.setattr(services, "post_journal", broken)
    with pytest.raises(RuntimeError):
        revise(invoice, _opened(invoice, "8", "Eight hours"), owner)
    monkeypatch.setattr(services, "post_journal", real)
    second = revise(invoice, _opened(invoice, "8", "Eight hours"), owner)
    n = invoice.number
    assert (first.number_display, second.number_display) == (f"{n}-1", f"{n}-2")
    assert _numbers(invoice) == [(0, n), (1, f"{n}-1"), (2, f"{n}-2")]  # no hole for the failure
    assert f"{n}-2" in second.journal_post.narration


@pytest.mark.django_db(transaction=True)
def test_concurrent_editors_get_sequential_suffixes() -> None:
    books = sales_books("Queue Interiors Inc.")
    owner = people(books["org"])["owner"]
    invoice = approve(draft(books, [("10", "100.00", "sales.ON.standard")]), owner)
    editors = ("alice", "bob", "carol")
    barrier = threading.Barrier(len(editors))
    saved: dict[str, int] = {}
    errors: dict[str, BaseException] = {}
    conflicts: list[str] = []

    def editor(name: str, quantity: str) -> None:
        try:
            barrier.wait(timeout=30)
            for _attempt in range(10):  # reload and save again after a conflict
                try:
                    revision = revise(invoice, _opened(invoice, quantity, name), owner)
                except RevisionConflict:
                    conflicts.append(name)
                    continue
                saved[name] = revision.revision
                return
        except BaseException as error:  # noqa: BLE001 — reported below
            errors[name] = error
        finally:
            connection.close()

    threads = [
        threading.Thread(target=editor, args=(name, str(9 - index)))
        for index, name in enumerate(editors)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert not errors, errors
    assert sorted(saved.values()) == [1, 2, 3], saved  # one suffix each, none twice
    n = invoice.number
    assert _numbers(invoice) == [(0, n), (1, f"{n}-1"), (2, f"{n}-2"), (3, f"{n}-3")]
    with org_context(books["org"]):
        fresh = Invoice.objects.get(pk=invoice.pk)
        current = InvoiceRevision.objects.get(invoice=invoice, superseded_at__isnull=True)
    assert fresh.current_revision_id == current.pk and current.revision == 3
    assert fresh.version == invoice.version + 3
