"""D-03b-T06 — concurrency of revisions: the save locks the invoice row and compares the version
the editor opened. Two simultaneous saves of the same version: one succeeds, the other gets a
``RevisionConflict`` (409, with the current version), and nothing of the loser is written — no
lost update. A save from a stale version is refused the same way."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
from django.db import connection, transaction

from numo9.sales.models import Invoice
from numo9.sales.posting import approve
from numo9.sales.revise import RevisionConflict, lock_for_revision
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books


def _save(invoice: Invoice, version: int, reference: str, hold: float = 0.0) -> Invoice:
    """A revision save, reduced to what concurrency is about: lock, compare, write, bump."""
    with org_context(invoice.organisation), transaction.atomic():
        locked = lock_for_revision(invoice, version)
        time.sleep(hold)  # keep the lock while the other save arrives
        locked.reference = reference
        locked.version += 1
        locked.save(update_fields=["reference", "version"])
        return locked


@pytest.mark.django_db
def test_a_stale_version_is_a_conflict() -> None:
    books = sales_books()
    owner = people(books["org"])["owner"]
    invoice = approve(draft(books, [("1", "100.00", "sales.ON.standard")]), owner)
    opened = invoice.version
    _save(invoice, opened, "PO-1")
    with pytest.raises(RevisionConflict) as refused:
        _save(invoice, opened, "PO-2")
    error = refused.value
    assert (error.code, error.status_code, error.current_version) == (
        "sales.revision.conflict",
        409,
        opened + 1,
    )
    assert "reload it" in str(error.messages[0])
    with org_context(books["org"]):
        invoice.refresh_from_db()
    assert (invoice.reference, invoice.version) == ("PO-1", opened + 1)


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_saves_one_wins() -> None:
    books = sales_books("Race Interiors Inc.")
    owner = people(books["org"])["owner"]
    invoice = approve(draft(books, [("1", "100.00", "sales.ON.standard")]), owner)
    opened = invoice.version
    barrier = threading.Barrier(2)
    results: dict[str, Any] = {}

    def editor(name: str) -> None:
        try:
            barrier.wait(timeout=30)
            results[name] = _save(invoice, opened, name, hold=0.3)
        except RevisionConflict as error:
            results[name] = error
        except BaseException as error:  # noqa: BLE001 — reported below
            results[name] = error
        finally:
            connection.close()

    threads = [threading.Thread(target=editor, args=(name,)) for name in ("alice", "bob")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    won = [name for name, result in results.items() if isinstance(result, Invoice)]
    lost = [name for name, result in results.items() if isinstance(result, RevisionConflict)]
    assert len(won) == 1 and len(lost) == 1, results
    with org_context(books["org"]):
        invoice.refresh_from_db()
    assert (invoice.reference, invoice.version) == (won[0], opened + 1)  # no lost update
