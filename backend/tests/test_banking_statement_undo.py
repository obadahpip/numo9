"""F-02-T10 — undo import: deletes the batch's lines only if none is CODED or MATCHED.

Acceptance: undo after one match → refused (409) listing that line. Also: undo of an untouched
import removes exactly its lines (other imports' lines stay), the batch stays in the history as
undone, the same file can then be imported again; ignored lines don't block; an import that isn't
committed (or is already undone) can't be undone.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.banking.models import (
    BankAccount,
    StatementImportStatus,
    StatementLine,
    StatementLineStatus,
)
from numo9.banking.services import create_bank_account
from numo9.banking.statements.errors import StatementError
from numo9.banking.statements.mappings import builtin, ensure_builtin_mappings
from numo9.banking.statements.service import ImportInUse, commit_import, undo_import
from numo9.banking.statements.source import FileStatementSource
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.statement_helpers import batch, fixture

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


@pytest.fixture
def bank(org: Organisation) -> BankAccount:
    return create_bank_account(org, type="chequing", display_name="Chequing")


def rbc(org: Organisation, data: bytes | None = None) -> FileStatementSource:
    mapping = builtin(ensure_builtin_mappings(org), "rbc")
    assert mapping is not None
    return FileStatementSource(data or fixture("rbc_chequing.csv"), "rbc.csv", mapping.layout())


def test_undo_after_one_match_is_refused_listing_that_line(
    org: Organisation, bank: BankAccount
) -> None:
    done = commit_import(batch(bank), rbc(org))
    matched = StatementLine.objects.filter(statement_import=done).order_by("date", "pk")[2]
    StatementLine.objects.filter(pk=matched.pk).update(status=StatementLineStatus.MATCHED)
    with pytest.raises(ImportInUse) as refused:
        undo_import(done)
    assert refused.value.status_code == 409 and refused.value.code == "banking.import.in_use"
    assert [line.pk for line in refused.value.lines] == [matched.pk]
    assert "1 of its lines are already coded or matched" in refused.value.text
    assert StatementLine.objects.filter(statement_import=done).count() == 5
    done.refresh_from_db()
    assert done.status == StatementImportStatus.COMMITTED


def test_coded_lines_block_too_and_are_listed_in_date_order(
    org: Organisation, bank: BankAccount
) -> None:
    done = commit_import(batch(bank), rbc(org))
    lines = list(StatementLine.objects.filter(statement_import=done).order_by("-date", "pk"))
    StatementLine.objects.filter(pk=lines[0].pk).update(status=StatementLineStatus.CODED)
    StatementLine.objects.filter(pk=lines[-1].pk).update(status=StatementLineStatus.MATCHED)
    with pytest.raises(ImportInUse) as refused:
        undo_import(done)
    assert [line.pk for line in refused.value.lines] == [lines[-1].pk, lines[0].pk]


def test_undo_removes_only_this_imports_lines(org: Organisation, bank: BankAccount) -> None:
    head = b"\n".join(fixture("rbc_chequing.csv").splitlines()[:3])
    first = commit_import(batch(bank), rbc(org, head))
    second = commit_import(batch(bank), rbc(org))
    assert second.lines_new == 3
    ignored = StatementLine.objects.filter(statement_import=second).first()
    assert ignored is not None
    StatementLine.objects.filter(pk=ignored.pk).update(status=StatementLineStatus.IGNORED)
    undone = undo_import(second)
    assert undone.status == StatementImportStatus.UNDONE and undone.undone_at is not None
    assert StatementLine.objects.filter(bank_account=bank).count() == 2
    assert set(StatementLine.objects.values_list("statement_import", flat=True)) == {first.pk}
    again = commit_import(batch(bank), rbc(org))  # the file can be imported again
    assert again.lines_new == 3


def test_only_a_committed_import_can_be_undone(org: Organisation, bank: BankAccount) -> None:
    pending = batch(bank)
    with pytest.raises(StatementError) as refused:
        undo_import(pending)
    assert refused.value.code == "banking.import.not_committed" and refused.value.status_code == 409
    done = commit_import(pending, rbc(org))
    undo_import(done)
    with pytest.raises(StatementError):
        undo_import(done)
