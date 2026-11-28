"""F-02-T09 — commit service (atomic batch insert) plus a background job for files of more than
2,000 lines, with progress.

Acceptance: a 50,000-line file imports in less than 60 s (measured here: reading, checking and
inserting) and its progress is visible in the job run. Also: the committed counts are the
preview's (F-02-T08); lines with errors refuse the import unless "skip errors"; a refused or
crashed import inserts nothing; a batch is committed once; the same file in a new import adds 0
lines; the layout becomes the bank account's mapping; files of up to 2,000 lines commit at once.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest

from numo9.banking.models import BankAccount, StatementImportStatus, StatementLine
from numo9.banking.services import create_bank_account
from numo9.banking.statements import service
from numo9.banking.statements.errors import StatementError
from numo9.banking.statements.mappings import builtin, ensure_builtin_mappings
from numo9.banking.statements.service import build_preview, commit_import, start_commit
from numo9.banking.statements.source import FileStatementSource
from numo9.banking.tasks import JOB, commit_statement_import
from numo9.files.models import DocumentSource
from numo9.files.services import store_received
from numo9.jobs.models import JobRun, JobStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.job_helpers import deliver
from tests.statement_helpers import batch, big_csv, fixture

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


@pytest.fixture
def bank(org: Organisation) -> BankAccount:
    return create_bank_account(org, type="chequing", display_name="Chequing")


def rbc_source(org: Organisation, data: bytes | None = None) -> FileStatementSource:
    rbc = builtin(ensure_builtin_mappings(org), "rbc")
    assert rbc is not None
    return FileStatementSource(data or fixture("rbc_chequing.csv"), "rbc.csv", rbc.layout())


def generic_source(org: Organisation, data: bytes) -> FileStatementSource:
    generic = builtin(ensure_builtin_mappings(org), "generic")
    assert generic is not None
    return FileStatementSource(data, "big.csv", generic.layout())


def test_committed_counts_equal_the_preview(org: Organisation, bank: BankAccount) -> None:
    head = b"\n".join(fixture("rbc_chequing.csv").splitlines()[:3])
    commit_import(batch(bank), rbc_source(org, head))
    source = rbc_source(org)
    preview = build_preview(bank, source)
    assert preview.counts == {"total": 5, "new": 3, "duplicate": 2, "error": 0}
    rbc = builtin(ensure_builtin_mappings(org), "rbc")
    done = commit_import(batch(bank), source, mapping=rbc)
    assert (done.lines_total, done.lines_new, done.lines_duplicate, done.lines_error) == (
        5,
        3,
        2,
        0,
    )
    assert done.status == StatementImportStatus.COMMITTED and done.committed_at is not None
    assert StatementLine.objects.filter(statement_import=done).count() == preview.counts["new"]
    assert done.mapping["columns"][2] == "date" and done.file_format == "csv"
    assert done.statement_mapping == rbc
    bank.refresh_from_db()
    assert bank.statement_mapping == rbc  # the choice is the account's from now on


def test_the_same_file_again_adds_nothing(org: Organisation, bank: BankAccount) -> None:
    commit_import(batch(bank), rbc_source(org))
    again = commit_import(batch(bank), rbc_source(org))
    assert (again.lines_new, again.lines_duplicate) == (0, 5)
    assert StatementLine.objects.filter(bank_account=bank).count() == 5


def test_errors_refuse_unless_skipped(org: Organisation, bank: BankAccount) -> None:
    tangerine = builtin(ensure_builtin_mappings(org), "tangerine")
    assert tangerine is not None
    source = FileStatementSource(fixture("tangerine_quoted.csv"), "t.csv", tangerine.layout())
    pending = batch(bank)
    with pytest.raises(StatementError) as refused:
        commit_import(pending, source)
    assert refused.value.code == "banking.import.has_errors"
    assert refused.value.text.startswith("Some lines can't be read (1).")
    pending.refresh_from_db()
    assert pending.status == StatementImportStatus.PENDING
    assert StatementLine.objects.count() == 0
    done = commit_import(pending, source, skip_errors=True)
    assert (done.lines_total, done.lines_new, done.lines_error) == (5, 4, 1)


def test_a_batch_is_committed_once(org: Organisation, bank: BankAccount) -> None:
    pending = batch(bank)
    commit_import(pending, rbc_source(org))
    with pytest.raises(StatementError) as refused:
        commit_import(pending, rbc_source(org))
    assert refused.value.code == "banking.import.not_pending" and refused.value.status_code == 409


def test_a_crash_half_way_inserts_nothing(org: Organisation, bank: BankAccount) -> None:
    calls = {"n": 0}
    real = StatementLine.objects.bulk_create

    def failing(rows: Any, *args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("database went away")
        return real(rows, *args, **kwargs)

    pending = batch(bank)
    with (
        mock.patch.object(StatementLine.objects, "bulk_create", failing),
        pytest.raises(RuntimeError),
    ):
        commit_import(pending, generic_source(org, big_csv(4500)))
    assert calls["n"] == 2
    assert StatementLine.objects.count() == 0
    pending.refresh_from_db()
    assert pending.status == StatementImportStatus.PENDING


def test_small_files_commit_at_once(org: Organisation, bank: BankAccount) -> None:
    done, run = start_commit(batch(bank, lines_total=5), rbc_source(org))
    assert run is None and done.status == StatementImportStatus.COMMITTED


def test_large_files_commit_in_the_job_with_progress(
    org: Organisation, bank: BankAccount, s3: str, sent: list[dict[str, Any]]
) -> None:
    data = big_csv(2500)
    with mock.patch("numo9.files.services.queue_scan"):
        document = store_received(org, "big.csv", data, source=DocumentSource.UPLOAD)
    pending = batch(bank, file=document, lines_total=2500)
    generic = builtin(ensure_builtin_mappings(org), "generic")
    source = generic_source(org, data)
    queued, run = start_commit(pending, source, mapping=generic)
    assert run is not None and queued.status == StatementImportStatus.PROCESSING
    assert StatementLine.objects.count() == 0
    message = next(m for m in sent if m["task"] == JOB)
    steps: list[tuple[int, int | None]] = []
    from numo9.jobs import runtime

    original = runtime.report_progress

    def spy(done: int, total: int | None = None, message: str = "") -> None:
        steps.append((done, total))
        original(done, total, message)

    with mock.patch("numo9.banking.tasks.report_progress", spy):
        result = deliver(commit_statement_import, message)
    assert result["counts"] == {"total": 2500, "new": 2500, "duplicate": 0, "error": 0}
    finished = JobRun.platform_runs.get(pk=run.pk)
    assert finished.status == JobStatus.SUCCEEDED
    assert finished.progress_done == finished.progress_total == 5000  # read + inserted
    assert [done for done, _ in steps] == sorted(done for done, _ in steps)  # only forward
    assert len(steps) >= 3 and finished.result_url.endswith(f"?import={pending.public_id}")
    queued.refresh_from_db()
    assert queued.status == StatementImportStatus.COMMITTED and queued.lines_new == 2500
    assert StatementLine.objects.filter(statement_import=queued).count() == 2500


def test_a_refused_job_marks_the_import_failed(
    org: Organisation, bank: BankAccount, s3: str, sent: list[dict[str, Any]]
) -> None:
    data = big_csv(2100) + b"not a date,BROKEN,1.00\n"
    with mock.patch("numo9.files.services.queue_scan"):
        document = store_received(org, "big.csv", data, source=DocumentSource.UPLOAD)
    pending = batch(bank, file=document, lines_total=2101)
    _queued, run = start_commit(pending, generic_source(org, data))
    assert run is not None
    message = next(m for m in sent if m["task"] == JOB)
    commit_statement_import.apply(kwargs=message["kwargs"], task_id=message["task_id"])
    pending.refresh_from_db()
    assert pending.status == StatementImportStatus.FAILED
    failed = JobRun.platform_runs.get(pk=run.pk)
    assert failed.status == JobStatus.FAILED and failed.error_code == "banking.import.has_errors"
    assert StatementLine.objects.count() == 0


def test_a_50000_line_file_imports_in_under_60_seconds(
    org: Organisation, bank: BankAccount, capsys: pytest.CaptureFixture[str]
) -> None:
    data = big_csv(50_000)
    started = time.perf_counter()
    source = generic_source(org, data)
    done = commit_import(batch(bank), source)
    elapsed = time.perf_counter() - started
    assert done.lines_new == 50_000
    assert StatementLine.objects.filter(bank_account=bank).count() == 50_000
    with capsys.disabled():
        print(f"\n[F-02-T09] 50,000-line CSV parsed, checked and committed in {elapsed:.1f} s")
    assert elapsed < 60
    started = time.perf_counter()
    again = commit_import(batch(bank), generic_source(org, data))
    reimport = time.perf_counter() - started
    assert again.lines_new == 0 and again.lines_duplicate == 50_000
    with capsys.disabled():
        print(f"[F-02-T09] the same 50,000 lines re-imported (all duplicates) in {reimport:.1f} s")
    assert reimport < 60


def test_the_job_is_registered() -> None:
    from celery import current_app

    assert JOB in current_app.tasks
    assert service.ASYNC_THRESHOLD == 2000
