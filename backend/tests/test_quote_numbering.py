"""D-02-T02 — quote numbers ``QU-0001`` from the organisation's numbering service, taken in the
create transaction: concurrent creates (threads on PostgreSQL, each its own connection) give
unique numbers with no gap; a create that fails gives its number back; the prefix is the
organisation's setting."""

from __future__ import annotations

import datetime as dt
import threading

import pytest
from django.db import IntegrityError, connection, connections

from numo9.orgsettings.models import DocType
from numo9.orgsettings.numbering import get_sequence
from numo9.sales.models import Quote
from numo9.sales.quotes import create_quote
from numo9.tenancy.context import org_context
from tests.sales_helpers import sales_books

DAY = dt.date(2026, 6, 15)
THREADS = 6
PER_THREAD = 5


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(connection.vendor != "postgresql", reason="row locks need PostgreSQL")
def test_concurrent_creates_get_unique_numbers() -> None:
    books = sales_books()
    org, customer = books["org"], books["customers"]["ON"]
    errors: list[BaseException] = []
    start = threading.Barrier(THREADS)

    def worker() -> None:
        try:
            start.wait()
            for _ in range(PER_THREAD):
                create_quote(org, contact=customer, date=DAY, expiry_date=DAY)
        except BaseException as error:  # reported below
            errors.append(error)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    with org_context(org):
        numbers = sorted(Quote.objects.values_list("number", flat=True))
    total = THREADS * PER_THREAD
    assert numbers == [f"QU-{n:04d}" for n in range(1, total + 1)]


@pytest.mark.django_db
def test_failed_create_gives_the_number_back_and_prefix_setting() -> None:
    books = sales_books()
    org, customer = books["org"], books["customers"]["ON"]
    assert create_quote(org, contact=customer, date=DAY, expiry_date=DAY).number == "QU-0001"
    with pytest.raises(IntegrityError):
        create_quote(org, contact=customer, date=DAY, expiry_date=DAY - dt.timedelta(days=1))
    assert create_quote(org, contact=customer, date=DAY, expiry_date=DAY).number == "QU-0002"
    with org_context(org):
        sequence = get_sequence(DocType.QUOTE, org)
        sequence.prefix = "Q26-"
        sequence.save()
    assert create_quote(org, contact=customer, date=DAY, expiry_date=DAY).number == "Q26-0003"
