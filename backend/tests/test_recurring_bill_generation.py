"""E-03-T02 — the recurring-bill generator on the shared D-04 engine: one bill per occurrence.

Acceptance: exactly one bill per tick after a restart — two workers (threads, each its own
connection) and a worker that dies mid-run leave one bill per occurrence (the unique (template,
date) run row of the shared ``RecurringGenerator``). Modes: draft → a draft; approve → approved
and posted (numbered), or Awaiting approval when the author can't approve it; another refusal
keeps the draft (recorded, the owner told). The shared skip rules apply (an AP lock date); the
hourly job runs each organisation on its own date; ``replay_ticks --kind bills`` creates nothing
new; the generator is the shared base, not a copy.
"""

from __future__ import annotations

import datetime as dt
import threading
from decimal import Decimal
from io import StringIO
from typing import Any
from unittest import mock

import pytest
from django.conf import settings as django_settings
from django.core.management import call_command
from django.db import connection
from freezegun import freeze_time

from numo9.documents.recurring import GENERATORS, RecurringGenerator
from numo9.notifications.models import Notification
from numo9.orgsettings.models import LockDate
from numo9.purchases.models import (
    Bill,
    BillStatus,
    RecurringBillLine,
    RecurringBillRun,
    RecurringBillTemplate,
)
from numo9.purchases.recurring_bills import GENERATOR, JOB, generate_all, generate_due
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.bill_helpers import bill_books

D = dt.date


def make_template(books: dict[str, Any], **fields: Any) -> RecurringBillTemplate:
    org = books["org"]
    values: dict[str, Any] = {
        "organisation": org,
        "name": "Warehouse rent",
        "contact": books["supplier"],
        "supplier_invoice_no": "RENT-{{month}}-{{year}}",
        "reference": "Rent {{month}} {{year}}",
        "rrule": "FREQ=MONTHLY",
        "start_date": D(2026, 1, 31),
        "tax_mode": "no_tax",
        "created_by": books["owner"],
    }
    values.update(fields)
    with org_context(org):
        template = RecurringBillTemplate(**values)
        template.full_clean()
        template.save()
        RecurringBillLine(
            organisation=org,
            document=template,
            position=0,
            description="Kingsway warehouse, {{period_start}} – {{period_end}}",
            quantity=Decimal("1"),
            unit_price=Decimal("2400.00"),
            account=books["expense"],
        ).save()
        return template


def bills(org: Organisation) -> list[Bill]:
    with org_context(org):
        return list(Bill.objects.filter(recurring_run__isnull=False).order_by("date", "pk"))


@pytest.fixture
def books(db: Any) -> dict[str, Any]:
    return bill_books()


@pytest.mark.django_db
def test_it_is_the_shared_generator() -> None:
    assert isinstance(GENERATOR, RecurringGenerator)
    assert type(GENERATOR).run_occurrence is RecurringGenerator.run_occurrence
    assert GENERATORS["bills"] is GENERATOR


@pytest.mark.django_db
def test_draft_mode_one_bill_per_occurrence_and_a_rerun_adds_nothing(
    books: dict[str, Any],
) -> None:
    org = books["org"]
    template = make_template(books)
    runs = generate_due(org, D(2026, 3, 31))
    assert [(r.occurrence_date, r.status) for r in runs] == [
        (D(2026, 1, 31), "created"),
        (D(2026, 2, 28), "created"),
        (D(2026, 3, 31), "created"),
    ]
    made = bills(org)
    assert [(b.date, b.status, b.number, b.supplier_invoice_no) for b in made] == [
        (D(2026, 1, 31), BillStatus.DRAFT, "", "RENT-January-2026"),
        (D(2026, 2, 28), BillStatus.DRAFT, "", "RENT-February-2026"),
        (D(2026, 3, 31), BillStatus.DRAFT, "", "RENT-March-2026"),
    ]
    first = made[0]
    assert first.reference == "Rent January 2026" and first.total == Decimal("2400.00")
    assert first.due_date is not None and first.due_date >= first.date
    with org_context(org):
        assert first.lines.get().description == "Kingsway warehouse, 31 Jan 2026 – 27 Feb 2026"
    assert generate_due(org, D(2026, 3, 31)) == []
    assert len(bills(org)) == 3
    with org_context(org):
        template.refresh_from_db()
        assert (template.next_run, template.last_run) == (D(2026, 4, 30), D(2026, 3, 31))


@pytest.mark.django_db
def test_approve_mode_posts_each_bill(books: dict[str, Any]) -> None:
    org = books["org"]
    make_template(books, mode="approve")
    generate_due(org, D(2026, 2, 28))
    made = bills(org)
    assert [(b.status, b.number) for b in made] == [
        (BillStatus.AWAITING_PAYMENT, "BILL-0001"),
        (BillStatus.AWAITING_PAYMENT, "BILL-0002"),
    ]
    assert all(b.journal_entry_id for b in made)


@pytest.mark.django_db
def test_an_author_who_cannot_approve_sends_it_for_approval(books: dict[str, Any]) -> None:
    org = books["org"]
    make_template(books, mode="approve", created_by=books["clerk"])  # no bill approval limit
    (run,) = generate_due(org, D(2026, 1, 31))
    assert (run.status, run.code) == ("created", "purchases.recurring.awaiting_approval")
    (bill,) = bills(org)
    assert (bill.status, bill.number) == (BillStatus.AWAITING_APPROVAL, "")


@pytest.mark.django_db
def test_a_refused_approval_keeps_the_draft_and_tells_the_owner(
    books: dict[str, Any], django_capture_on_commit_callbacks: Any
) -> None:
    org = books["org"]
    template = make_template(books, mode="approve")
    with org_context(org):
        template.lines.update(account=None)
    with django_capture_on_commit_callbacks(execute=True):
        (run,) = generate_due(org, D(2026, 1, 31))
    assert (run.status, run.code) == ("created", "purchases.bill.incomplete")
    assert bills(org)[0].status == BillStatus.DRAFT
    with org_context(org):
        (note,) = Notification.objects.filter(recipient=books["owner"])
        assert note.title_key == "notifications.purchases.recurring.failed"
        assert note.link.endswith(f"/purchases/recurring-bills/{template.public_id}")


@pytest.mark.django_db
def test_an_ap_lock_skips_the_date(
    books: dict[str, Any], django_capture_on_commit_callbacks: Any
) -> None:
    org = books["org"]
    make_template(books)
    with org_context(org):
        LockDate(organisation=org, module="ap", level="everyone", date=D(2026, 1, 31)).save()
    with django_capture_on_commit_callbacks(execute=True):
        runs = generate_due(org, D(2026, 2, 28))
    assert [(r.occurrence_date, r.status, r.code) for r in runs] == [
        (D(2026, 1, 31), "skipped", "lock.violation"),
        (D(2026, 2, 28), "created", ""),
    ]
    with org_context(org):
        assert Notification.objects.filter(
            title_key="notifications.purchases.recurring.skipped"
        ).exists()


@pytest.mark.django_db
def test_a_worker_that_dies_mid_run_leaves_nothing_and_the_rerun_creates_one(
    books: dict[str, Any],
) -> None:
    org = books["org"]
    make_template(books)

    def dies(template: Any, document: Any) -> Any:
        raise SystemExit("worker killed")

    with mock.patch.object(GENERATOR, "finish", dies), pytest.raises(SystemExit):
        generate_due(org, D(2026, 1, 31))
    with org_context(org):
        assert RecurringBillRun.objects.count() == 0 and Bill.objects.count() == 0
    generate_due(org, D(2026, 1, 31))
    generate_due(org, D(2026, 1, 31))
    assert [b.date for b in bills(org)] == [D(2026, 1, 31)]


@pytest.mark.django_db
def test_the_hourly_job_and_the_replay(books: dict[str, Any]) -> None:
    with freeze_time("2026-01-02 12:00:00"):
        make_template(books)
    assert django_settings.CELERY_BEAT_SCHEDULE[JOB]["task"] == JOB
    with freeze_time("2026-02-01 03:00:00"):  # 22:00 on 31 January in Toronto
        assert generate_all() == {"created": 1, "skipped": 0, "failed": 0}
    out = StringIO()
    call_command("replay_ticks", "--date", "2026-01-31", "--kind", "bills", stdout=out)
    assert "2026-01-31: already ran" in out.getvalue()
    assert len(bills(books["org"])) == 1


@pytest.mark.django_db(transaction=True)
def test_two_workers_create_exactly_one_bill_per_occurrence() -> None:
    books = bill_books("Race Ltd.")
    org = books["org"]
    make_template(books)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait(timeout=10)
            generate_due(org, D(2026, 6, 30))
        except BaseException as error:  # noqa: BLE001 — reported below
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert errors == []
    assert [b.date for b in bills(org)] == [
        D(2026, 1, 31),
        D(2026, 2, 28),
        D(2026, 3, 31),
        D(2026, 4, 30),
        D(2026, 5, 31),
        D(2026, 6, 30),
    ]
    with org_context(org):
        assert RecurringBillRun.objects.count() == 6
        assert Bill.objects.count() == 6
