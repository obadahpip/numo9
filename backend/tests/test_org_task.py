"""Organisation-scoped Celery task base class (A-01-T07).

Acceptance: a task without ``org_id`` is rejected — at enqueue time in the caller, and at run
time when a message arrives without one; with ``org_id`` the task runs in that organisation's
tenant context (managers scoped, context restored afterwards).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from celery import Task
from celery.contrib.testing.worker import start_worker

from numo9 import celery_app
from numo9.jobs.queues import QUEUE_NAMES
from numo9.tenancy.context import TenantContextMissing, acting_practice, current_org
from numo9.tenancy.models import Organisation, Practice
from numo9.tenancy.tasks import OrgIdRequired, OrgTask, UnknownOrganisation, org_task
from tests.testapp.models import Widget


@org_task(name="tests.org_task.count_widgets")
def count_widgets(*, org_id: str, label: str | None = None) -> dict[str, Any]:
    organisation = current_org()
    practice = acting_practice()
    queryset = Widget.objects.all()  # OrgScopedManager: needs the context
    if label is not None:
        queryset = queryset.filter(label=label)
    return {
        "org_id": org_id,
        "current": str(organisation.public_id) if organisation else None,
        "practice": str(practice.public_id) if practice else None,
        "widgets": queryset.count(),
    }


@org_task(name="tests.org_task.boom")
def boom(*, org_id: str) -> None:
    raise ValueError("boom")


def _org(name: str = "Maple Leaf Supply Ltd.") -> Organisation:
    return Organisation.objects.create(name=name)


def test_org_task_uses_the_org_base_class() -> None:
    assert isinstance(count_widgets, OrgTask)
    with pytest.raises(TypeError):
        org_task(base=Task)


# ---- refused without org_id -------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda: count_widgets.delay(),
        lambda: count_widgets.apply_async(),
        lambda: count_widgets.apply_async(kwargs={"label": "x"}),
        lambda: count_widgets.apply_async(args=["7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6"]),
        lambda: count_widgets.delay(org_id=""),
        lambda: count_widgets.delay(org_id="not-a-uuid"),
        lambda: count_widgets.s().apply_async(),
    ],
    ids=["delay", "apply_async", "other-kwargs", "positional", "empty", "not-uuid", "signature"],
)
def test_enqueue_without_org_id_is_refused_and_nothing_is_sent(call: Any) -> None:
    with mock.patch.object(Task, "apply_async") as send, pytest.raises(OrgIdRequired):
        call()
    send.assert_not_called()


def test_org_id_required_is_a_tenant_context_error() -> None:
    assert issubclass(OrgIdRequired, TenantContextMissing)


def test_enqueue_normalises_the_org_id_to_a_string() -> None:
    org_id = uuid.uuid4()
    with mock.patch.object(Task, "apply_async") as send:
        count_widgets.apply_async(kwargs={"org_id": org_id, "label": "a"}, queue="io")
    args, kwargs, options = send.call_args[0][0], send.call_args[0][1], send.call_args[1]
    assert args is None
    assert kwargs == {"org_id": str(org_id), "label": "a"}
    assert options == {"queue": "io"}


@pytest.mark.django_db
def test_run_without_org_id_is_refused() -> None:
    result = count_widgets.apply(kwargs={})  # a message that skipped apply_async
    assert result.failed()
    assert isinstance(result.result, OrgIdRequired)


@pytest.mark.django_db
def test_unknown_organisation_is_refused() -> None:
    result = count_widgets.apply(kwargs={"org_id": str(uuid.uuid4())})
    assert result.failed()
    assert isinstance(result.result, UnknownOrganisation)


# ---- runs in the organisation's context --------------------------------------------------------


@pytest.mark.django_db
def test_runs_in_the_organisation_context_and_restores_it() -> None:
    maple, other = _org(), _org("Northern Lights Bakery Inc.")
    Widget.objects.unscoped(reason="test setup").bulk_create(
        [
            Widget(organisation=maple, label="a"),
            Widget(organisation=maple, label="b"),
            Widget(organisation=other, label="a"),
        ]
    )
    assert current_org() is None
    result = count_widgets.apply(kwargs={"org_id": str(maple.public_id)}).get()
    assert result == {
        "org_id": str(maple.public_id),
        "current": str(maple.public_id),
        "practice": None,
        "widgets": 2,  # only Maple Leaf's rows
    }
    other_result = count_widgets.apply(kwargs={"org_id": other.public_id, "label": "a"}).get()
    assert other_result["widgets"] == 1
    assert current_org() is None  # nothing leaks out of the task


@pytest.mark.django_db
def test_practice_id_sets_the_acting_practice() -> None:
    maple = _org()
    practice = Practice.objects.create(name="Profitex")
    result = count_widgets.apply(
        kwargs={"org_id": str(maple.public_id), "practice_id": str(practice.public_id)}
    ).get()
    assert result["practice"] == str(practice.public_id)
    unknown = count_widgets.apply(
        kwargs={"org_id": str(maple.public_id), "practice_id": str(uuid.uuid4())}
    )
    assert isinstance(unknown.result, UnknownOrganisation)


@pytest.mark.django_db
def test_context_is_restored_when_the_task_fails() -> None:
    result = boom.apply(kwargs={"org_id": str(_org().public_id)})
    assert isinstance(result.result, ValueError)
    assert current_org() is None


# ---- through a real worker -------------------------------------------------------------------


@pytest.fixture(scope="module")
def worker() -> Iterator[Any]:
    with start_worker(
        celery_app,
        queues=list(QUEUE_NAMES),
        perform_ping_check=False,
        shutdown_timeout=10,
        loglevel="WARNING",
    ) as running:
        yield running


@pytest.mark.django_db(transaction=True)
def test_worker_runs_org_task_in_context_and_rejects_a_message_without_org_id(
    worker: Any,
) -> None:
    maple = _org()
    Widget.objects.unscoped(reason="test setup").create(organisation=maple, label="a")
    answer = count_widgets.delay(org_id=str(maple.public_id)).get(timeout=10)
    assert answer["current"] == str(maple.public_id)
    assert answer["widgets"] == 1

    # A message sent by name, without org_id, reaches the worker and is refused there.
    raw = celery_app.send_task("tests.org_task.count_widgets", kwargs={}, queue="default")
    with pytest.raises(OrgIdRequired):
        raw.get(timeout=10)
