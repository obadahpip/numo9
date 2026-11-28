"""F-04-T07 — apply service: a rule codes a statement line into a draft bank transaction (F-01)
with the ``applied_rule`` link; auto-apply posts directly and flags ``auto_coded``.

Acceptance (integration): an auto-applied line posts a balanced journal and keeps the rule
reference; a review rule leaves a draft (no journal) that posts when confirmed; rules never touch
Matched or locked-period lines; every application is logged (line link, application row, audit
event, counters); contact strategy, reference template and transfer rules (never to the line's
own account) work.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.banking.models import (
    BankRuleAllocation,
    BankRuleApplication,
    BankTransactionStatus,
    ContactStrategy,
    StatementLineStatus,
)
from numo9.banking.rules.apply import apply_rules, confirm_line, uncoded_lines
from numo9.banking.services import create_bank_account
from numo9.ledger.models import JournalLine, SystemRole
from numo9.ledger.template import load_template
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.bank_rule_helpers import rule, statement_line
from tests.contact_helpers import contact
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


@pytest.fixture
def books(org: Organisation) -> dict[str, Any]:
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    savings = create_bank_account(org, type="savings", display_name="TD Savings")
    with org_context(org):
        fuel = account(org, "5901", "Fuel")
    return {"bank": bank, "savings": savings, "fuel": fuel}


def fuel_rule(org: Organisation, fuel: Any, **fields: Any) -> Any:
    item = rule(
        org,
        "Petro-Canada",
        conditions=[("description", "contains", "petro"), ("amount", "between", "20", "200")],
        reference_template="{payee} {date}",
        **fields,
    )
    BankRuleAllocation.objects.create(
        organisation=org, rule=item, account=fuel, percent=D("100"), tax_code="purchase.ON.standard"
    )
    return item


def txn_of(line: Any) -> Any:
    """The line's transaction (asserted present)."""
    assert line.bank_transaction is not None
    return line.bank_transaction


def journal(org: Organisation, txn: Any) -> list[tuple[str, D, D]]:
    with org_context(org):
        rows = JournalLine.objects.filter(entry=txn.journal_entry).order_by("line_no")
        return [(row.account.code, row.debit, row.credit) for row in rows]


def test_auto_applied_line_posts_balanced_journal_keeps_rule(
    org: Organisation, books: dict[str, Any]
) -> None:
    with org_context(org):
        item = fuel_rule(org, books["fuel"], auto_apply=True)
        line = statement_line(
            org, books["bank"], "-113.00", "PETRO-CANADA #12", payee="Petro-Canada"
        )
        result = apply_rules(uncoded_lines())
        line.refresh_from_db()
        assert [(r.pk, t.pk) for _l, r, t in result.applied] == [
            (item.pk, line.bank_transaction_id)
        ]
        assert (line.status, line.auto_coded, line.applied_rule) == (
            StatementLineStatus.CODED,
            True,
            item,
        )
        txn = txn_of(line)
        assert (txn.status, txn.kind, txn.total, txn.reference) == (
            BankTransactionStatus.POSTED,
            "spend",
            D("113.00"),
            "Petro-Canada 2026-06-15",
        )
        rows = journal(org, txn)
        assert sum(r[1] for r in rows) == sum(r[2] for r in rows) == D("113.00")
        itc = JournalLine.objects.filter(entry=txn.journal_entry).get(
            account__system_role=SystemRole.ITC_RECEIVABLE
        )
        assert itc.debit == D("13.00")
        assert ("5901", D("100.00"), D("0")) in rows
        # Logged: application row, audit event, counters.
        application = BankRuleApplication.objects.get()
        assert (application.rule, application.statement_line, application.mode) == (
            item,
            line,
            "auto",
        )
        event = AuditEvent.objects.filter(action="banking.rule.applied").get()
        assert event.meta["rule"] == str(item.public_id)
        item.refresh_from_db()
        assert item.applied_count == 1 and item.last_applied_at is not None


def test_review_rule_leaves_draft_then_confirm_posts(
    org: Organisation, books: dict[str, Any]
) -> None:
    with org_context(org):
        item = fuel_rule(org, books["fuel"])
        line = statement_line(org, books["bank"], "-56.50", "PETRO-CANADA")
        apply_rules(uncoded_lines())
        line.refresh_from_db()
        txn = txn_of(line)
        assert (line.status, line.auto_coded, line.applied_rule) == (
            StatementLineStatus.UNCODED,
            False,
            item,
        )
        assert (txn.status, txn.journal_entry, txn.total) == ("draft", None, D("56.50"))
        # A line with a draft is not coded twice.
        assert apply_rules(uncoded_lines()).applied == []
        posted = confirm_line(line)
        line.refresh_from_db()
        assert (posted.status, line.status) == ("posted", StatementLineStatus.CODED)
        rows = journal(org, posted)
        assert sum(r[1] for r in rows) == sum(r[2] for r in rows) == D("56.50")


def test_matched_and_locked_lines_untouched(org: Organisation, books: dict[str, Any]) -> None:
    with org_context(org):
        fuel_rule(org, books["fuel"], auto_apply=True)
        matched = statement_line(
            org, books["bank"], "-40.00", "PETRO", status=StatementLineStatus.MATCHED
        )
        old = statement_line(org, books["bank"], "-40.00", "PETRO", date=dt.date(2026, 3, 1))
        LockDate(
            organisation=org, module="bank", level="everyone", date=dt.date(2026, 3, 31)
        ).save()
        result = apply_rules([matched, old])
        assert result.applied == []
        assert sorted(reason for _l, reason in result.skipped) == ["locked", "status"]
        for line in (matched, old):
            line.refresh_from_db()
            assert (line.bank_transaction, line.applied_rule) == (None, None)
        assert not BankRuleApplication.objects.exists()


def test_contact_strategies_and_transfer(org: Organisation, books: dict[str, Any]) -> None:
    with org_context(org):
        shell = contact(org, "Shell Canada", roles=["supplier"])
        fixed = fuel_rule(
            org,
            books["fuel"],
            auto_apply=True,
            contact_strategy=ContactStrategy.FIXED,
            contact=shell,
        )
        line = statement_line(org, books["bank"], "-30.00", "PETRO")
        apply_rules(uncoded_lines())
        line.refresh_from_db()
        assert txn_of(line).contact == shell
        fixed.active = False
        fixed.save()

        by_payee = rule(
            org,
            "By payee",
            type="receive",
            conditions=[("payee", "equals", "shell canada")],
            contact_strategy=ContactStrategy.MATCH_PAYEE,
            auto_apply=True,
        )
        BankRuleAllocation.objects.create(
            organisation=org, rule=by_payee, account=books["fuel"], percent=D("100")
        )
        refund = statement_line(org, books["bank"], "12.00", "Refund", payee="SHELL CANADA")
        apply_rules(uncoded_lines())
        refund.refresh_from_db()
        assert (txn_of(refund).kind, txn_of(refund).contact) == ("receive", shell)

        move = rule(
            org,
            "To savings",
            type="transfer",
            conditions=[("description", "starts_with", "TFR")],
            transfer_account=books["savings"],
            auto_apply=True,
        )
        out = statement_line(org, books["bank"], "-500.00", "TFR TO 1234")
        back = statement_line(org, books["savings"], "-20.00", "TFR TO 9999")
        result = apply_rules([out, back])
        assert [line.pk for line, _r, _t in result.applied] == [out.pk]
        assert [reason for _l, reason in result.skipped] == ["banking.rule.transfer_same_account"]
        out.refresh_from_db()
        rows = journal(org, out.bank_transaction)
        assert (books["savings"].gl_account.code, D("500.00"), D("0")) in rows
        assert out.applied_rule == move
