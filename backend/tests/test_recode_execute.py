"""C-07-T05 — running a recode batch: per entry reverse + re-post with the new coding in one
transaction; > 200 lines run as one background job with progress.

Acceptance: 500 lines → one batch, audit rows (recoded lines) = 500.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from numo9.audit.models import AuditEvent
from numo9.jobs.models import JobRun
from numo9.ledger.models import (
    Account,
    JournalEntry,
    JournalLine,
    JournalStatus,
    RecodeLineChange,
    RecodeStatus,
)
from numo9.ledger.recode_execute import (
    ASYNC_THRESHOLD,
    JOB,
    create_batch,
    execute,
    recode_job,
)
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from tests.job_helpers import deliver
from tests.recode_helpers import recode_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return recode_books()


def pid(books: dict[str, Any], key: str) -> str:
    return str(books[key].public_id)


def on_account(books: dict[str, Any], key: str) -> dict[str, Any]:
    return {"conditions": [{"field": "account", "op": "is", "value": pid(books, key)}]}


def balance(books: dict[str, Any], key: str) -> Decimal:
    with org_context(books["org"]):
        lines = JournalLine.objects.filter(account=books[key])
        return sum((line.debit - line.credit for line in lines), Decimal("0.00"))


def test_small_batch_reverses_and_reposts_each_entry(books: dict[str, Any]) -> None:
    org = books["org"]
    before = {key: balance(books, key) for key in ("expense", "expense2", "bank")}
    with org_context(org):
        batch = create_batch(
            org,
            on_account(books, "expense"),
            {"account": pid(books, "expense2"), "tracking": {"region": "north"}},
            books["adviser"],
            name="Move supplies",
        )
        assert batch.status == RecodeStatus.DRAFT and batch.line_count == 2
        done = execute(batch, books["adviser"])
    assert done.status == RecodeStatus.COMPLETED
    assert done.line_count == done.progress == 2 and done.problems == []
    with org_context(org):
        changes = list(RecodeLineChange.objects.filter(batch=done).select_related("entry"))
        assert {c.entry_id for c in changes} == {books["entries"][1].pk, books["entries"][3].pk}
        for change in changes:
            original = JournalEntry.objects.get(pk=change.entry_id)
            assert original.status == JournalStatus.REVERSED
            assert change.reversal_entry.reversal_of_id == original.pk
            repost = change.repost_entry
            assert repost.status == JournalStatus.POSTED and repost.date == original.date
            assert repost.type == original.type and repost.narration == original.narration
            moved = repost.lines.get(line_no=change.line_no)
            assert moved.account_id == books["expense2"].pk
            assert moved.tracking == {"region": "north"}
            assert (moved.debit, moved.credit) == (change.debit, change.credit)
            # every other line copied as it was
            assert [
                (line.account_id, line.debit, line.credit)
                for line in repost.lines.exclude(line_no=change.line_no).order_by("line_no")
            ] == [
                (line.account_id, line.debit, line.credit)
                for line in original.lines.exclude(line_no=change.line_no).order_by("line_no")
            ]
            assert change.before["account"] == pid(books, "expense")
            assert change.after["account"] == pid(books, "expense2")
    # amounts never change: what left expense arrived in expense2; bank untouched
    assert balance(books, "expense") == before["expense"] - Decimal("275.00")
    assert balance(books, "expense2") == before["expense2"] + Decimal("275.00")
    assert balance(books, "bank") == before["bank"]
    with org_context(org):
        executed = AuditEvent.objects.filter(
            action="ledger.recodebatch.executed", object_id=str(done.public_id)
        )
        assert executed.count() == 1


def test_a_batch_runs_once(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        batch = create_batch(
            org, on_account(books, "expense"), {"tax_code": ""}, books["adviser"], confirm_tax=True
        )
        execute(batch, books["adviser"])
        with pytest.raises(ValidationError) as caught:
            execute(batch, books["adviser"])
    assert caught.value.code == "ledger.recode.not_draft"


def test_nothing_to_recode_is_refused(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org), pytest.raises(ValidationError) as caught:
        create_batch(org, on_account(books, "expense"), {"account": pid(books, "expense")}, None)
    assert caught.value.code == "ledger.recode.nothing"


def test_a_tax_change_must_be_confirmed(books: dict[str, Any]) -> None:
    org = books["org"]
    criteria = on_account(books, "revenue")
    with org_context(org):
        with pytest.raises(ValidationError) as caught:
            create_batch(org, criteria, {"tax_code": "sales.ON.zero"}, books["adviser"])
        assert caught.value.code == "ledger.recode.confirm_tax"
        batch = create_batch(
            org, criteria, {"tax_code": "sales.ON.zero"}, books["adviser"], confirm_tax=True
        )
    assert batch.line_count == 1


def test_selection_narrows_the_batch(books: dict[str, Any]) -> None:
    org = books["org"]
    chosen = [{"entry": str(books["entries"][1].public_id), "line_no": 1}]
    with org_context(org):
        batch = create_batch(
            org,
            on_account(books, "expense"),
            {"account": pid(books, "expense2")},
            books["adviser"],
            selection=chosen,
        )
        done = execute(batch, books["adviser"])
        assert done.line_count == 1
        assert JournalEntry.objects.get(pk=books["entries"][3].pk).status == JournalStatus.POSTED


def test_a_refused_posting_is_a_problem_and_the_rest_runs(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        # the target account requires a contact: entry 2 has one (Bolt), entry 4 has none
        needs_contact = Account.objects.get(pk=books["expense2"].pk)
        needs_contact.require_contact = True
        needs_contact.save()
        batch = create_batch(
            org, on_account(books, "expense"), {"account": pid(books, "expense2")}, books["adviser"]
        )
        done = execute(batch, books["adviser"])
    assert done.status == RecodeStatus.COMPLETED and done.line_count == 1
    assert [(p["entry"], p["lines"], p["code"]) for p in done.problems] == [
        (str(books["entries"][3].public_id), [1], "ledger.journal.contact_required")
    ]
    with org_context(org):
        assert JournalEntry.objects.get(pk=books["entries"][3].pk).status == JournalStatus.POSTED


def _many_lines(books: dict[str, Any], entries: int, per_entry: int) -> None:
    """``entries`` journals of ``per_entry`` expense lines (1.00 … each) and one revenue line."""
    org = books["org"]
    with org_context(org):
        for n in range(entries):
            amounts = [Decimal(f"{n + 1}.{i:02d}") for i in range(per_entry)]
            post_journal(
                JournalSpec(
                    date=dt.date(2026, 5, 1 + n % 28),
                    narration=f"Bulk {n}",
                    lines=[
                        *(LineSpec(books["expense2"], debit=a) for a in amounts),
                        LineSpec(books["revenue"], credit=sum(amounts, Decimal("0"))),
                    ],
                ),
                user=books["adviser"],
            )


def test_500_lines_run_as_one_background_batch(books: dict[str, Any], sent: Any) -> None:
    org = books["org"]
    _many_lines(books, 125, 4)
    criteria = {
        "match": "all",
        "conditions": [
            {"field": "account", "op": "is", "value": pid(books, "expense2")},
            {"field": "reference", "op": "contains", "value": "Bulk"},
        ],
    }
    with org_context(org):
        batch = create_batch(org, criteria, {"account": pid(books, "expense")}, books["adviser"])
        assert batch.line_count == 500 > ASYNC_THRESHOLD
        started = execute(batch, books["adviser"])
    assert started.status == RecodeStatus.RUNNING and started.job_run is not None
    assert [m["task"] for m in sent] == [JOB]
    result = deliver(recode_job, sent[0])
    assert result["lines"] == 500 and result["status"] == RecodeStatus.COMPLETED
    with org_context(org):
        started.refresh_from_db()
        assert started.status == RecodeStatus.COMPLETED
        assert started.line_count == started.progress == 500
        assert RecodeLineChange.objects.filter(batch=started).count() == 500
        assert RecodeLineChange.objects.filter(batch=started).values(
            "entry"
        ).distinct().count() == (125)
        run = JobRun.objects.get(pk=started.job_run_id)
        assert run.status == "succeeded"
    # a redelivery does nothing more
    deliver(recode_job, sent[0])
    with org_context(org):
        assert RecodeLineChange.objects.filter(batch=started).count() == 500


def test_documents_point_at_the_repost(books: dict[str, Any]) -> None:
    """An invoice's posting reversed by a recode: the invoice now points at the re-post, so
    voiding it later reverses the live entry."""
    from numo9.sales.posting import approve, void
    from tests.sales_helpers import draft

    org = books["org"]
    with org_context(org):
        from numo9.orgsettings.service import get_settings

        settings = get_settings(org)
        settings.physical_province = "ON"
        settings.save()
        customer = books["acme"]
        from numo9.contacts.models import Address, AddressKind

        Address(
            organisation=org,
            contact=customer,
            kind=AddressKind.BILLING,
            country="CA",
            province="ON",
            city="Toronto",
        ).save()
    sales = {"org": org, "revenue": books["revenue"], "customers": {"ON": customer}}
    invoice = approve(
        draft(sales, [("1", "100.00", "sales.ON.standard")], date=dt.date(2026, 6, 15)),
        books["owner"],
    )
    original = invoice.journal_entry
    criteria = {
        "conditions": [
            {"field": "account", "op": "is", "value": pid(books, "revenue")},
            {"field": "date", "op": "on", "value": "2026-06-15"},
        ]
    }
    with org_context(org):
        revenue2 = (
            Account.objects.filter(type="revenue").exclude(pk=books["revenue"].pk).order_by("code")
        ).first()
        assert revenue2 is not None and original is not None
        batch = create_batch(org, criteria, {"account": str(revenue2.public_id)}, books["adviser"])
        done = execute(batch, books["adviser"])
        assert done.line_count == 1, done.problems
        invoice.refresh_from_db()
        assert invoice.journal_entry_id != original.pk
        assert invoice.journal_entry_id == done.lines.get().repost_entry_id
    voided = void(invoice, books["owner"], reason="Entered twice")
    with org_context(org):
        assert voided.void_entry is not None
        assert voided.void_entry.reversal_of_id == voided.journal_entry_id
