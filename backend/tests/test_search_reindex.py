"""A-09-T09 — backfill command ``reindex_search --org``.

Acceptance: reindex matches counts — after a rebuild the index holds exactly one document per
searchable record of the organisation (per type), whatever was there before (missing documents
written, stale ones removed, other organisations untouched); ``--check`` reports the drift
without writing and fails on it.
"""

from __future__ import annotations

import io
from collections import Counter

import pytest
from django.core.management import CommandError, call_command

from numo9.accounts.models import User
from numo9.search.models import SearchDocument
from numo9.search.reindex import drift, reindex
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.contact_helpers import contact
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


def counts(org: Organisation) -> Counter[str]:
    with org_context(org):
        return Counter(SearchDocument.objects.values_list("object_type", flat=True))


@pytest.fixture
def maple() -> Organisation:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        for n in range(3):
            contact(org, f"Customer {n}")
        account(org, "1000", "Chequing", subtype="bank")
        account(org, "5400", "Rent")
    user = User.objects.create_user("dana@example.com", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    return org


EXPECTED = {
    "contacts.contact": 3,
    "ledger.account": 2,
    "accounts.user": 1,
    "tenancy.organisation": 1,
}


def test_reindex_matches_counts_after_drift(maple: Organisation) -> None:
    birch = Organisation.objects.create(name="Birch")
    with org_context(birch):
        contact(birch, "Birch customer")
    birch_before = counts(birch)
    assert {k: v for k, v in counts(maple).items() if k in EXPECTED} == EXPECTED

    with org_context(maple):  # drift: a lost document and a stale one
        SearchDocument.objects.filter(object_type="contacts.contact").first().delete()  # type: ignore[union-attr]
        SearchDocument.objects.create(
            organisation=maple, object_type="contacts.contact", object_id="gone", title="x", url="/"
        )
    report = drift(maple)
    assert (report.missing, report.stale, report.consistent) == (1, 1, False)

    out = io.StringIO()
    with pytest.raises(CommandError, match="drift in 1"):
        call_command("reindex_search", "--org", str(maple.public_id), "--check", stdout=out)
    assert "1 missing, 1 stale" in out.getvalue()

    call_command("reindex_search", "--org", str(maple.public_id), stdout=out)
    assert counts(maple) == Counter(EXPECTED)
    assert drift(maple).consistent
    assert counts(birch) == birch_before  # other organisations untouched
    call_command("reindex_search", "--check", stdout=io.StringIO())  # all consistent


def test_reindex_is_idempotent_and_reports(maple: Organisation) -> None:
    first = reindex(maple)
    second = reindex(maple)
    assert first.indexed == second.indexed == sum(EXPECTED.values())
    assert second.removed == 0
    assert dict(second.counts) == EXPECTED


def test_unknown_or_bad_organisation_is_refused() -> None:
    with pytest.raises(CommandError, match="Not an organisation id"):
        call_command("reindex_search", "--org", "nope")
    with pytest.raises(CommandError, match="Unknown organisation"):
        call_command("reindex_search", "--org", "6ca1b880-64f7-4053-80e3-0c3618895553")
