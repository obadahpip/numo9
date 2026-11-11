"""Celery application (A-08-T01).

Configuration lives in Django settings under the ``CELERY_`` namespace
(``numo9/settings/base.py`` § Background jobs); tasks are discovered in every installed app's
``tasks`` module. Start a worker with:

    celery -A numo9 worker -Q high,default,io,reports --loglevel INFO

One worker process may serve every queue; production runs separate workers per queue group so
a long report never delays a high-priority job (docs/architecture/jobs.md).
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "numo9.settings.dev")

app = Celery("numo9")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
