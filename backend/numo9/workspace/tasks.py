"""Background jobs of the accountant workspace (V-01-T03)."""

from __future__ import annotations

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job, report_progress

from .summary import rebuild_all

REBUILD_DIRECTORY = "numo9.workspace.rebuild_directory"


@platform_job(name=REBUILD_DIRECTORY, queue=DEFAULT)
def rebuild_directory() -> dict[str, int]:
    """Nightly (beat): rebuild every organisation directory row from the source records, so a
    missed signal or a provider's late data never stays wrong for more than a day."""
    return rebuild_all(progress=lambda done, total: report_progress(done, total))
