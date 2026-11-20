"""C-03-T06 — expense-journal rule: when the organisation's toggles are on (C-03-T05), a manual
journal with any line on an expense account needs an attachment / a contact on every expense line.

Acceptance: an expense journal without an attachment is refused when the toggle is on and accepted
when it is off; the same for the contact (each expense line named); journals with no expense line
and journals posted by modules (sales, purchases…) are not affected.
"""

from __future__ import annotations

import pytest

from numo9.ledger.models import JournalStatus, JournalType
from numo9.ledger.policy import JournalRuleError
from numo9.ledger.services import post_journal
from numo9.orgsettings.service import get_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.journal_helpers import chart, document, pay

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def toggle(org: Organisation, **flags: bool) -> None:
    row = get_settings(org)
    for name, value in flags.items():
        setattr(row, name, value)
    row.save()


def test_attachment_required_only_when_on(org: Organisation) -> None:
    with org_context(org):
        accounts = chart(org)
        spec = pay(accounts["office"], accounts["petty"], "417.22")
        assert post_journal(spec).status == JournalStatus.POSTED  # off: accepted
        toggle(org, journal_expense_requires_attachment=True)
        with pytest.raises(JournalRuleError) as raised:
            post_journal(spec)
        assert [e.code for e in raised.value.error_list] == [
            "ledger.journal.expense_attachment_required"
        ]
        assert "6100" in raised.value.messages[0]
        assert post_journal(spec, attachments=[document(org)]).status == JournalStatus.POSTED


def test_contact_required_on_each_expense_line(org: Organisation) -> None:
    with org_context(org):
        accounts = chart(org)
        toggle(org, journal_expense_requires_contact=True)
        with pytest.raises(JournalRuleError) as raised:
            post_journal(pay(accounts["office"], accounts["petty"], "576.95"))
        assert [e.code for e in raised.value.error_list] == [
            "ledger.journal.expense_contact_required"
        ]
        assert raised.value.messages[0].startswith("Line 1:")
        staples = contact(org, "Staples")
        spec = pay(accounts["office"], accounts["petty"], "576.95", contact=staples)
        assert post_journal(spec).status == JournalStatus.POSTED


def test_no_expense_line_or_module_postings_are_not_affected(org: Organisation) -> None:
    with org_context(org):
        accounts = chart(org)
        toggle(org, journal_expense_requires_attachment=True, journal_expense_requires_contact=True)
        assert post_journal(pay(accounts["ar"], accounts["sales"], "113.00")).status == "posted"
        bill = pay(accounts["office"], accounts["chequing"], "50.00", type=JournalType.PURCHASE)
        assert post_journal(bill).status == JournalStatus.POSTED
