"""Background jobs of banking (discovered by Celery): commit a large statement import (F-02-T09).

``commit_statement_import`` — started by ``statements.service.start_commit`` for files of more
than 2,000 lines; one run per import (idempotency key ``statement-import:<import id>``). It reads
the uploaded file again from the document store and commits it with the layout and saved mapping
stored on the import, reporting progress to the job tray. Not ``atomic`` as a job: reading and
checking report progress outside the commit's own transaction, which inserts all lines or none.
A refusal (lines with errors, the import already committed) or a crash marks the import
``failed`` with the message; nothing is inserted, so the person can upload the file again.
"""

from __future__ import annotations

from typing import Any

from numo9.jobs.queues import REPORTS
from numo9.jobs.runtime import JobError, org_job, report_progress, set_result_url

from .models import StatementImport, StatementImportStatus
from .statements.errors import StatementError

JOB = "numo9.banking.commit_statement_import"


@org_job(name=JOB, queue=REPORTS, max_retries=0, atomic=False)
def commit_statement_import(
    *, org_id: str, import_id: str, skip_errors: bool = False, user_id: int | None = None
) -> dict[str, Any]:
    from numo9.accounts.models import User

    from .statements.service import commit_import, source_for

    batch = StatementImport.objects.select_related("bank_account", "file", "statement_mapping").get(
        public_id=import_id
    )
    user = User.objects.filter(pk=user_id).first() if user_id else None
    report_progress(0, None, "")
    try:
        done = commit_import(
            batch,
            source_for(batch),
            skip_errors=skip_errors,
            mapping=batch.statement_mapping,
            user=user,
            progress=lambda step, total: report_progress(step, total, ""),
        )
    except StatementError as error:
        StatementImport.objects.filter(pk=batch.pk).update(status=StatementImportStatus.FAILED)
        raise JobError(error.error, **error.error_params) from error
    except Exception:
        StatementImport.objects.filter(pk=batch.pk).update(status=StatementImportStatus.FAILED)
        raise
    set_result_url(f"/o/{org_id}/banking/{batch.bank_account.public_id}?import={import_id}")
    return {
        "import": import_id,
        "counts": {
            "total": done.lines_total,
            "new": done.lines_new,
            "duplicate": done.lines_duplicate,
            "error": done.lines_error,
        },
    }
