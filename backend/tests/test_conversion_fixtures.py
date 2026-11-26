"""C-05-T13 — conversion fixtures: balanced and unbalanced sets, REFINED included; each behaves
as its ``Expect`` says (finalises, or is refused naming the difference; opening equity missing
for REFINED)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.conversion.difference import difference
from numo9.conversion.finalise import ConversionRefused, finalise
from numo9.conversion.fixtures import SETS, build
from numo9.ledger.models import JournalEntry, JournalLine
from numo9.tenancy.context import org_context
from tests.sales_helpers import sales_books

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("key", sorted(SETS))
def test_set_behaves_as_expected(key: str) -> None:
    org = sales_books(f"Fixture {key} Ltd")["org"]
    spec = SETS[key]
    session = build(org, key)
    result = difference(session)
    assert f"{result.difference:.2f}" == spec.expect.difference
    assert result.opening_equity_missing is spec.expect.opening_equity_missing
    assert result.can_finalise is spec.expect.finalises
    if spec.expect.finalises:
        done = finalise(session, None)
        with org_context(org):
            entry = JournalEntry.objects.get(pk=done.opening_entry_id)
            totals = [(line.debit, line.credit) for line in JournalLine.objects.filter(entry=entry)]
        assert entry.is_opening and entry.date == spec.conversion_date
        assert sum(d for d, _c in totals) == sum(c for _d, c in totals) > Decimal("0")
    else:
        with pytest.raises(ConversionRefused) as caught:
            finalise(session, None)
        assert caught.value.code == spec.expect.code
        if spec.expect.code == "conversion.unbalanced":
            assert f"Difference {spec.expect.difference}" in caught.value.messages[0]
        with org_context(org):
            assert not JournalEntry.objects.exists()


def test_refined_has_no_equity_and_names_its_shareholder() -> None:
    org = sales_books("REFINED Interiors Inc.")["org"]
    session = finalise(build(org, "refined"), None)
    with org_context(org):
        lines = {
            line.account.code: line
            for line in JournalLine.objects.filter(
                entry_id=session.opening_entry_id
            ).select_related("account", "contact")
        }
    assert set(lines) == {"1010", "2600"}
    assert lines["2600"].contact is not None
    assert all(line.account.type != "equity" for line in lines.values())
