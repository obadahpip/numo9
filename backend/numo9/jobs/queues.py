"""Celery queues (A-08-T01).

Every task names its queue explicitly (``@shared_task(queue=...)`` or ``apply_async(queue=...)``);
a task that doesn't goes to ``default``.

- ``high`` — short jobs a person is waiting for: an email the user just triggered, new-device
  notices, webhooks to acknowledge;
- ``default`` — ordinary background work: trial reminders, recurring documents, usage metering;
- ``io`` — slow network or file work: virus scans, inbound email, OCR, bank feeds, exports;
- ``reports`` — long CPU/database work: report packs, bulk edits, imports, period-end runs.
"""

from __future__ import annotations

from kombu.entity import Exchange, Queue

HIGH = "high"
DEFAULT = "default"
IO = "io"
REPORTS = "reports"

QUEUE_NAMES: tuple[str, ...] = (HIGH, DEFAULT, IO, REPORTS)

_exchange = Exchange("numo9", type="direct")  # type: ignore[no-untyped-call]  # kombu untyped

#: kombu queues for ``CELERY_TASK_QUEUES``: one direct exchange, routing key = queue name.
QUEUES: tuple[Queue, ...] = tuple(
    Queue(name, _exchange, routing_key=name)  # type: ignore[no-untyped-call]  # kombu untyped
    for name in QUEUE_NAMES
)
