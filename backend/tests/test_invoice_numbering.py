"""D-03a-T02 — invoice numbers at approval: from the organisation's pattern, kept once given,
rolled back with a failed posting (gap-free), and unique and gap-free under concurrent approvals.
"""

from __future__ import annotations

import datetime as dt
import threading

import pytest
from django.db import connection, transaction

from numo9.orgsettings.models import DocType
from numo9.orgsettings.numbering import get_sequence
from numo9.sales.models import Invoice
from numo9.sales.numbering import assign_number
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact


def drafts(org: Organisation, count: int) -> list[Invoice]:
    with org_context(org):
        customer = contact(org, "Maple Leaf Ltd", roles=["customer"])
        items = [
            Invoice(organisation=org, contact=customer, date=dt.date(2026, 6, 15))
            for _ in range(count)
        ]
        for item in items:
            item.save()
        return items


@pytest.mark.django_db
def test_pattern_kept_and_rolled_back() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    first, second, third = drafts(org, 3)
    with org_context(org):
        sequence = get_sequence(DocType.INVOICE, org)
        sequence.prefix, sequence.padding = "RI-", 5
        sequence.save()
    assert assign_number(first) == "RI-00001"
    assert assign_number(first) == "RI-00001"  # kept: never a second number
    with pytest.raises(RuntimeError), transaction.atomic():
        assign_number(second)
        raise RuntimeError("the posting failed")
    with org_context(org):
        second.refresh_from_db()
    assert second.number == ""
    assert assign_number(third) == "RI-00002"  # the rolled-back number is handed out again


@pytest.mark.django_db(transaction=True)
def test_concurrent_approvals_no_gaps_no_duplicates() -> None:
    org = Organisation.objects.create(name="Race Ltd.")
    invoices = drafts(org, 1000)
    workers = 10
    barrier = threading.Barrier(workers)
    errors: list[BaseException] = []

    def work(chunk: list[Invoice]) -> None:
        try:
            barrier.wait(timeout=30)
            for invoice in chunk:
                with transaction.atomic():
                    assign_number(invoice)
        except BaseException as error:  # noqa: BLE001 — reported below
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=work, args=(invoices[i::workers],)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert errors == []
    with org_context(org):
        numbers = sorted(Invoice.objects.values_list("number", flat=True))
    assert numbers == [f"INV-{n:04d}" for n in range(1, 1001)]
