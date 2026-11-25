"""D-07-T08 — bulk statement runs reusing B-02: outstanding and activity statements for chosen
contacts (or every customer with a balance), PDF + email, skipped contacts with the reason;
more than 20 contacts run as a background job.

Acceptance (integration, data validation): each statement's total = the contact's AR aging.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from numo9.contacts import subledger
from numo9.contacts.models import (
    ContactPerson,
    StatementRunStatus,
    StatementSend,
)
from numo9.contacts.statement_runs import (
    ASYNC_THRESHOLD,
    JOB,
    create_run,
    execute_run,
    preview_run,
    statement_run_job,
)
from numo9.contacts.statements import AGING_BUCKETS
from numo9.contacts.subledger import FixtureDocument, FixtureSource
from numo9.notifications.models import EmailMessage
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.job_helpers import deliver
from tests.journal_helpers import people
from tests.test_statement_vs_ar_aging import ar_aging, total

pytestmark = [pytest.mark.django_db, pytest.mark.data_validation]
D, day = Decimal, dt.date
AS_AT = day(2026, 6, 30)


@pytest.fixture
def source() -> Iterator[FixtureSource]:
    made = FixtureSource("receivables")
    subledger.register_source(made)
    yield made
    subledger.unregister_source(made)


def emailed(org: Organisation, who: Any, address: str) -> None:
    ContactPerson.objects.create(
        organisation=org, contact=who, first_name="AP", email=address, include_in_emails=True
    )


@pytest.fixture
def world(source: FixtureSource) -> dict[str, Any]:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    owner = people(org)["owner"]
    with org_context(org):
        maple = contact(org, "Maple Leaf Supply Ltd.", roles=["customer"])
        birch = contact(org, "Birch Bakery Co.", roles=["customer"])
        cedar = contact(org, "Cedar Café", roles=["customer"])
        quiet = contact(org, "Quiet Ltd.", roles=["customer"])
        paper = contact(org, "Paper Only Inc.", roles=["customer"])
        paper.statement_pref = "post"
        paper.save()
        nobody = contact(org, "No Email Co.", roles=["customer"])
        for who, address in ((maple, "ap@maple.ca"), (birch, "ap@birch.ca"), (quiet, "q@q.ca")):
            emailed(org, who, address)
        emailed(org, paper, "p@paper.ca")
    source.documents.extend(
        [
            FixtureDocument(
                maple.pk,
                "INV-1",
                day(2026, 1, 10),
                D("500.00"),
                day(2026, 2, 9),
                payments=[(day(2026, 3, 10), D("200.00"), "PMT-1")],
            ),
            FixtureDocument(maple.pk, "INV-2", day(2026, 5, 5), D("120.00"), day(2026, 6, 4)),
            FixtureDocument(birch.pk, "INV-3", day(2025, 10, 1), D("1130.00"), day(2025, 10, 31)),
            FixtureDocument(cedar.pk, "INV-5", day(2026, 6, 1), D("42.00"), day(2026, 7, 1)),
            FixtureDocument(paper.pk, "INV-6", day(2026, 6, 1), D("10.00"), day(2026, 7, 1)),
            FixtureDocument(nobody.pk, "INV-7", day(2026, 6, 1), D("15.00"), day(2026, 7, 1)),
        ]
    )
    return {
        "org": org,
        "owner": owner,
        "source": source,
        "maple": maple,
        "birch": birch,
        "cedar": cedar,
        "quiet": quiet,
        "paper": paper,
        "nobody": nobody,
    }


def by_name(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["name"]: r for r in rows}


def test_preview_lists_who_gets_one_and_why_not(world: dict[str, Any]) -> None:
    run = create_run(world["org"], "outstanding", AS_AT, world["owner"])
    rows = by_name(preview_run(run))
    assert {n: (r["status"], r.get("reason")) for n, r in rows.items()} == {
        "Maple Leaf Supply Ltd.": ("ready", None),
        "Birch Bakery Co.": ("ready", None),
        "Cedar Café": ("skipped", "no_recipient"),
        "Quiet Ltd.": ("skipped", "no_balance"),
        "Paper Only Inc.": ("skipped", "statements_off"),
        "No Email Co.": ("skipped", "no_recipient"),
    }
    # each statement's total is the contact's AR aging (data validation)
    aging = ar_aging(world["source"], AS_AT)
    for key in ("maple", "birch", "cedar"):
        who = world[key]
        row = rows[who.display_name]
        assert D(row["amount_due"]) == total(aging[who.pk])
        assert {k: D(v) for k, v in row["aging"].items()} == aging[who.pk]
    assert set(rows["Maple Leaf Supply Ltd."]["aging"]) == {k for k, _l, _h in AGING_BUCKETS}


def test_run_sends_pdf_statements_and_keeps_the_results(world: dict[str, Any], s3: str) -> None:
    org = world["org"]
    run = create_run(org, "outstanding", AS_AT, world["owner"])
    done = execute_run(run, world["owner"])
    assert done.status == StatementRunStatus.DONE
    assert (done.sent_count, done.skipped_count, done.failed_count) == (2, 4, 0)
    sent = [r for r in done.results if r["status"] == "sent"]
    with org_context(org):
        sends = StatementSend.objects.filter(public_id__in=[r["send"] for r in sent])
        assert sorted(s.contact.display_name for s in sends) == [
            "Birch Bakery Co.",
            "Maple Leaf Supply Ltd.",
        ]
        aging = ar_aging(world["source"], AS_AT)
        for send in sends:
            assert send.amount_due == total(aging[send.contact_id])
            assert send.file_name.endswith(".pdf")
        assert EmailMessage.objects.filter(kind="contacts.statement").count() == 2
    # a run is sent once
    with pytest.raises(ValidationError):
        execute_run(done, world["owner"])


def test_activity_run_for_chosen_contacts(world: dict[str, Any], s3: str) -> None:
    run = create_run(
        world["org"],
        "activity",
        AS_AT,
        world["owner"],
        start=day(2026, 1, 1),
        contacts=[str(world["maple"].public_id), str(world["quiet"].public_id)],
        include_zero=True,
    )
    done = execute_run(run, world["owner"])
    rows = by_name(done.results)
    assert set(rows) == {"Maple Leaf Supply Ltd.", "Quiet Ltd."}
    assert rows["Maple Leaf Supply Ltd."]["status"] == "sent"
    assert rows["Quiet Ltd."]["status"] == "sent"  # include_zero: a nil statement
    assert D(rows["Maple Leaf Supply Ltd."]["amount_due"]) == D("420.00")


@pytest.mark.parametrize(
    ("kind", "start", "code"),
    [
        ("monthly", None, "contacts.run.kind"),
        ("activity", None, "contacts.run.period"),
        ("activity", day(2026, 7, 1), "contacts.run.period"),
    ],
)
def test_refused_runs(world: dict[str, Any], kind: str, start: Any, code: str) -> None:
    with pytest.raises(ValidationError) as caught:
        create_run(world["org"], kind, AS_AT, world["owner"], start=start)
    assert caught.value.code == code


def test_unknown_contact_is_refused(world: dict[str, Any]) -> None:
    import uuid

    with pytest.raises(ValidationError) as caught:
        create_run(world["org"], "outstanding", AS_AT, world["owner"], contacts=[str(uuid.uuid4())])
    assert caught.value.code == "contacts.run.contacts"


def test_many_contacts_run_as_a_background_job(
    world: dict[str, Any], s3: str, sent: list[dict[str, Any]]
) -> None:
    org = world["org"]
    with org_context(org):
        for n in range(ASYNC_THRESHOLD):
            who = contact(org, f"Customer {n:02d}", roles=["customer"])
            emailed(org, who, f"ap{n}@customers.ca")
            world["source"].documents.append(
                FixtureDocument(who.pk, f"INV-{100 + n}", day(2026, 6, 1), D("10.00"))
            )
    run = create_run(org, "outstanding", AS_AT, world["owner"])
    started = execute_run(run, world["owner"])
    assert started.status == StatementRunStatus.RUNNING and started.job_run is not None
    jobs = [m for m in sent if m["task"] == JOB]
    assert len(jobs) == 1
    result = deliver(statement_run_job, jobs[0])
    assert result["sent"] == ASYNC_THRESHOLD + 2
    with org_context(org):
        started.refresh_from_db()
        assert started.status == StatementRunStatus.DONE
        assert started.sent_count == ASYNC_THRESHOLD + 2
