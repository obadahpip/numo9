"""Job tasks used by the worker-restart test (A-08-T09); found by the worker's autodiscovery.

Only installed with the test settings (``tests.testapp`` is a test-only app).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import org_job

from .models import Widget


@org_job(name="tests.worker_restart.write_widget", queue=DEFAULT, max_retries=3)
def write_widget(*, org_id: str, label: str, control_dir: str) -> dict[str, str]:
    """The effect (one Widget), then wait mid-task until the test lets it finish.

    Writes ``started-<n>`` (the worker process id) when it reaches the middle of its work, and
    finishes once ``go`` exists — the test kills the worker in between.
    """
    Widget.objects.create(label=label)  # atomic job: rolled back if the worker dies now
    control = Path(control_dir)
    tries = len(list(control.glob("started-*"))) + 1
    (control / f"started-{tries}").write_text(str(os.getpid()))
    deadline = time.monotonic() + 60
    while not (control / "go").exists():
        if time.monotonic() > deadline:
            raise TimeoutError("the test never let the job finish")
        time.sleep(0.05)
    return {"label": label}
