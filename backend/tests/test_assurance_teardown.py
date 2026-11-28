"""K-09-T25 — the teardown migration fixture (a REFINED-like organisation as the Xero teardown
found it, docs/xero_teardown.md §10.A): **every** issue is flagged by one nightly run.

The fixture is ``tests.assurance_helpers.refined()``: the chart as migrated (every expense account
defaulting to the exempt purchase code, none mapped to GIFI), the two manual journals brought in
as history (journal 1 dated 3 Jun, posted 15 Jun; journal 2 15 Jun), a GST/HST registration with
no Business Number, no lock date, an empty conversion at 1 Jan 2025 and the owner with
user-management rights who last signed in four months ago.

- ``gap-59`` (GL Exceptions flags nothing): negative petty cash, journal-only expenses (to cash,
  no contact, no attachment), all-exempt lines, no BN, no lock date, 0 GIFI, the backdated
  journal and the dormant admin are all findings — with their numbers;
- ``gap-36`` (assurance ignores journals; no SoD, round-number, weekend, duplicate-payment
  checks): the same run checks journals for segregation of duties, round amounts, weekend
  postings in the organisation's time zone and duplicate payments;
- ``gap-53`` (symptoms, not fixes): the negative cash comes with its correcting entry, Dr 1000
  Petty Cash 994.17 / Cr 2900 Shareholder Loan 994.17, saved through the API as a **draft** that
  shows in the journals Draft list (``?status=draft``) and is never posted by the engine; posting
  it resolves the finding. The all-exempt lines come with a find & recode proposal.

The browser half (the Assurance page on the same teardown data) is
frontend/e2e/gap-36-53-59.spec.ts.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from numo9.assurance.models import ExceptionFinding, RunTrigger
from numo9.assurance.runner import run
from numo9.ledger.models import JournalApproval, JournalEntry
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from tests.assurance_helpers import NOW, at, post, refined
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db

#: The issues of docs/xero_teardown.md §10.A and the rule that must flag each one.
TEARDOWN_ISSUES = {
    "negative petty cash": "NEG_CASH",
    "journal-only expenses (to cash)": "JOURNAL_TO_CASH",
    "journal-only expenses (no contact)": "EXPENSE_JOURNAL_NO_CONTACT",
    "journal-only expenses (no receipt)": "EXPENSE_JOURNAL_NO_ATTACHMENT",
    "all-exempt tax": "EXEMPT_ON_TAXABLE_ACCOUNT",
    "no BN": "MISSING_BN",
    "no lock date": "MISSING_LOCK_DATE",
    "0 GIFI": "UNMAPPED_GIFI",
    "backdated journal": "BACKDATED",
    "dormant admin": "DORMANT_USER_WITH_ADMIN",
    "no opening balances": "UNBALANCED_CONVERSION",
}


def _nightly(org: Any) -> None:
    with at(NOW):
        run(org, trigger=RunTrigger.NIGHTLY, now=NOW)


def _open(org: Any) -> dict[str, list[ExceptionFinding]]:
    found: dict[str, list[ExceptionFinding]] = {}
    with org_context(org):
        for finding in ExceptionFinding.objects.filter(status="open").order_by("pk"):
            found.setdefault(finding.rule_code, []).append(finding)
    return found


@pytest.mark.gap("gap-59")
def test_every_teardown_issue_is_flagged() -> None:
    books = refined()
    org = books["org"]
    j1, j2 = str(books["journal1"].public_id), str(books["journal2"].public_id)
    _nightly(org)
    found = _open(org)
    missing = {issue: rule for issue, rule in TEARDOWN_ISSUES.items() if rule not in found}
    assert missing == {}, f"teardown issues not flagged: {missing}"

    (cash,) = found["NEG_CASH"]
    assert (cash.severity, cash.subject_label, cash.amount) == (
        "critical",
        "1000 · Petty Cash",
        Decimal("-994.17"),
    )
    assert cash.details["lowest_on"] == "2026-06-15"
    assert cash.details["first_negative_on"] == "2026-06-03"
    for rule in ("JOURNAL_TO_CASH", "EXPENSE_JOURNAL_NO_CONTACT", "EXPENSE_JOURNAL_NO_ATTACHMENT"):
        assert {f.subject_id: f.amount for f in found[rule]} == {
            j1: Decimal("417.22"),
            j2: Decimal("576.95"),
        }, rule
    exempt = found["EXEMPT_ON_TAXABLE_ACCOUNT"]
    assert len(exempt) == 5  # every expense line of both journals
    assert sum((f.amount or Decimal(0)) for f in exempt) == Decimal("994.17")
    (late,) = found["BACKDATED"]
    assert late.subject_id == j1 and late.details["gap"] == 12  # 3 Jun, posted 15 Jun
    (bn,) = found["MISSING_BN"]
    assert bn.severity == "critical" and bn.details["types"] == ["rt"]
    (lock,) = found["MISSING_LOCK_DATE"]
    assert lock.details["lock"] == ""
    (gifi,) = found["UNMAPPED_GIFI"]
    assert gifi.details["unmapped"] == gifi.details["total"] == 7  # 0 GIFI
    (dormant,) = found["DORMANT_USER_WITH_ADMIN"]
    assert dormant.subject_label == "Dana Lee" and dormant.details["idle"] >= 60
    (conversion,) = found["UNBALANCED_CONVERSION"]
    assert "no_equity" in conversion.details["problems"]

    # A second nightly run adds nothing: one finding per issue and subject.
    count = sum(len(v) for v in found.values())
    _nightly(org)
    assert sum(len(v) for v in _open(org).values()) == count


@pytest.mark.gap("gap-36")
def test_assurance_checks_journals_for_sod_round_weekend_and_duplicates() -> None:
    from tests.contact_helpers import contact
    from tests.ledger_helpers import account

    books = refined()
    org = books["org"]
    acc = books["accounts"]
    with org_context(org):
        staff = people(org)
        # SoD: a legacy approval row with the creator as approver (Numo9 itself refuses it).
        JournalApproval.objects.create(
            organisation=org,
            entry=books["journal1"],
            total=Decimal("417.22"),
            submitted_by=staff["owner"],
            decision="approved",
            decided_by=staff["owner"],
            decided_at=timezone.now(),
        )
        # Round amount, posted by a person on Saturday 20 Jun 2026 22:30 in Toronto (Sunday UTC).
        weekend_round = post(
            acc,
            dt.date(2026, 6, 20),
            "Year-end estimate",
            (("5920", "5000.00", "0"), ("2900", "0", "5000.00")),
            when=dt.datetime(2026, 6, 21, 2, 30, tzinfo=dt.UTC),
            user=staff["owner"],
        )
        # The same supplier paid the same amount twice within three days.
        acc["1010"] = account(org, "1010", "Chequing", subtype="bank")
        acc["2100"] = account(org, "2100", "Accounts payable", subtype="current_liability")
        post(
            acc,
            dt.date(2026, 6, 1),
            "Deposit",
            (("1010", "5000.00", "0"), ("4000", "0", "5000.00")),
        )
        cedar = contact(org, "Cedar Supply Co.", roles=["supplier"])

        def pay(day: dt.date) -> JournalEntry:
            return post_journal(
                JournalSpec(
                    date=day,
                    type="payment",
                    lines=(
                        LineSpec(acc["2100"], debit=Decimal("250.00"), contact=cedar),
                        LineSpec(acc["1010"], credit=Decimal("250.00")),
                    ),
                ),
                user=None,
            )

        with at(dt.datetime(2026, 7, 3, 14, tzinfo=dt.UTC)):
            pay(dt.date(2026, 7, 1))
            repeat = pay(dt.date(2026, 7, 3))
    _nightly(org)
    found = _open(org)
    subjects = {rule: {f.subject_id for f in found.get(rule, [])} for rule in found}
    assert str(books["journal1"].public_id) in subjects["SOD_SAME_CREATOR_APPROVER"]
    assert str(weekend_round.public_id) in subjects["ROUND_AMOUNT"]
    assert str(weekend_round.public_id) in subjects["WEEKEND_POSTING"]
    assert subjects["DUPLICATE_PAYMENT"] == {str(repeat.public_id)}
    # …and the teardown's journals are still checked by the journal rules in the same run.
    assert str(books["journal2"].public_id) in subjects["JOURNAL_TO_CASH"]


@pytest.mark.gap("gap-53")
def test_the_fix_is_a_draft_journal_in_the_draft_list_and_posting_it_resolves() -> None:
    books = refined()
    org = books["org"]
    _nightly(org)
    with org_context(org):
        adviser = people(org)["adviser"]
    client = Client()
    client.force_login(adviser)
    base = f"/api/v1/o/{org.public_id}/"
    findings = client.get(f"{base}assurance/findings").json()["findings"]
    cash = next(f for f in findings if f["rule"] == "NEG_CASH")
    assert cash["has_fix"] is True

    fix = client.get(f"{base}assurance/findings/{cash['id']}/fix").json()["fix"]
    assert fix["kind"] == "journal" and fix["reasoning"]
    assert [(line["code"], line["debit"], line["credit"]) for line in fix["lines"]] == [
        ("1000", "994.17", "0.00"),
        ("2900", "0.00", "994.17"),
    ]
    # The drawer sends the (edited) grid: a description added to the first line.
    lines = [
        {
            "account": line["account"],
            "debit": line["debit"],
            "credit": line["credit"],
            "description": "Owner paid personally" if i == 0 else "",
        }
        for i, line in enumerate(fix["lines"])
    ]
    with at(NOW):
        made = client.post(
            f"{base}assurance/findings/{cash['id']}/fix",
            {"lines": lines, "narration": "Owner funded Petty Cash"},
            content_type="application/json",
        )
    assert made.status_code == 201, made.content
    draft_id = made.json()["draft"]["id"]
    assert made.json()["draft"]["status"] == "draft"
    assert made.json()["finding"]["status"] == "open"  # nothing posted yet

    drafts = client.get(f"{base}journals?status=draft").json()["results"]
    assert [(d["id"], d["status"], d["total"], d["narration"]) for d in drafts] == [
        (draft_id, "draft", "994.17", "Owner funded Petty Cash")
    ]
    assert client.get(f"{base}journals").json()["count"] == 2  # posted: the teardown's two only

    with at(NOW):
        posted = client.post(f"{base}journals/{draft_id}/post", {}, content_type="application/json")
    assert posted.status_code == 200, posted.content
    detail = client.get(f"{base}assurance/findings/{cash['id']}").json()
    assert detail["status"] == "resolved"
    assert [h["action"] for h in detail["history"]][-2:] == ["fix_drafted", "resolved"]

    exempt = next(f for f in findings if f["rule"] == "EXEMPT_ON_TAXABLE_ACCOUNT")
    recode = client.get(f"{base}assurance/findings/{exempt['id']}/fix").json()["fix"]
    assert recode["kind"] == "recode" and recode["reasoning"]
    conditions = {c["field"]: c["value"] for c in recode["recode"]["criteria"]["conditions"]}
    assert conditions["tax_code"] == "purchase.exempt"  # a prefilled find & recode, not a symptom
