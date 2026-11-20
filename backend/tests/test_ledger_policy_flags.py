"""C-03-T04 — account flags on journal lines: ``require_contact``, ``require_tracking``,
``require_attachment`` (C-01) enforced by ``JournalPolicy`` when posting.

Acceptance: a line on an account with require_contact and no contact → error naming the account
(and the same for tracking and attachment, parameterised); satisfying the flag posts — the
attachment passed with the journal or attached to the draft before it is posted; a document
detached before posting no longer counts.
"""

from __future__ import annotations

from typing import Any

import pytest

from numo9.files.attachments import attach, attachments_of, detach
from numo9.ledger.models import JournalStatus
from numo9.ledger.policy import JournalRuleError
from numo9.ledger.services import post_entry, post_journal, save_draft
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.journal_helpers import chart, document, pay

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.mark.parametrize(
    ("flag", "code", "message"),
    [
        ("require_contact", "ledger.journal.contact_required", "Line 1: 6100"),
        ("require_tracking", "ledger.journal.tracking_required", "Line 1: 6100"),
        ("require_attachment", "ledger.journal.attachment_required", "6100"),
    ],
)
def test_flag_without_what_it_requires_names_the_account(
    org: Organisation, flag: str, code: str, message: str
) -> None:
    with org_context(org):
        accounts = chart(org)
        setattr(accounts["office"], flag, True)
        accounts["office"].save()
        with pytest.raises(JournalRuleError) as raised:
            post_journal(pay(accounts["office"], accounts["chequing"], "50.00"))
    assert [e.code for e in raised.value.error_list] == [code]
    assert message in raised.value.messages[0]
    assert "Office supplies" in raised.value.messages[0]


@pytest.mark.parametrize(
    ("flag", "extra"),
    [
        ("require_contact", "contact"),
        ("require_tracking", "tracking"),
        ("require_attachment", "attachments"),
    ],
)
def test_flag_satisfied_posts(org: Organisation, flag: str, extra: str) -> None:
    with org_context(org):
        accounts = chart(org)
        setattr(accounts["office"], flag, True)
        accounts["office"].save()
        options: dict[str, dict[str, Any]] = {
            "contact": {"contact": contact(org, "Staples")},
            "tracking": {"tracking": {"region": "Ontario"}},
            "attachments": {},
        }
        given = options[extra]
        spec = pay(accounts["office"], accounts["chequing"], "50.00", **given)
        documents = [document(org)] if extra == "attachments" else []
        assert post_journal(spec, attachments=documents).status == JournalStatus.POSTED
        if extra == "attachments":
            (entry,) = [e for e in _journals(org) if e.status == JournalStatus.POSTED]
            assert attachments_of("ledger.JournalEntry", entry.public_id).count() == 1


def _journals(org: Organisation) -> list[Any]:
    from numo9.ledger.models import JournalEntry

    return list(JournalEntry.objects.all())


def test_attachment_on_the_draft_counts_until_detached(org: Organisation) -> None:
    with org_context(org):
        accounts = chart(org)
        accounts["rent"].require_attachment = True
        accounts["rent"].save()
        draft = save_draft(pay(accounts["rent"], accounts["chequing"], "1130.00"))
        link = attach(document(org, "lease.pdf"), "ledger.JournalEntry", draft.public_id)
        detach(link)  # uploaded then removed before posting
        with pytest.raises(JournalRuleError):
            post_entry(draft)
        attach(document(org, "lease-signed.pdf"), "ledger.JournalEntry", draft.public_id)
        assert post_entry(draft).status == JournalStatus.POSTED
