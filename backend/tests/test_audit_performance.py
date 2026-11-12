"""Audit log performance on 1,000,000 rows (A-04-T13).

Acceptance: listing the audit log of an organisation with 1M events answers in under one second
with the indexes — the viewer's first page (default 90 days), a page deep in the cursor, a user
filter, a record's history, the filter choices — and the planner uses the indexes (no sequential
scan of the table).

One million events of one organisation spread over two years, plus 200,000 of a second one, are
inserted with ``generate_series`` (hashes are not computed: the chain is not under test here).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest
from django.db import connection
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = pytest.mark.django_db

ROWS = 1_000_000
OTHER_ROWS = 200_000
BUDGET_SECONDS = 1.0

INSERT = """
INSERT INTO audit_event (id, created_at, public_id, organisation_id, actor_kind, actor_user_id,
    actor_label, action, object_type, object_id, object_label, changes, meta, user_agent,
    request_id, prev_hash, hash)
SELECT nextval('audit_event_id_seq'),
       now() - (n * interval '63 seconds'),
       md5(%(seed)s || n)::uuid,
       %(org)s,
       CASE WHEN n %% 10 = 0 THEN 'system' ELSE 'user' END,
       CASE WHEN n %% 10 = 0 THEN NULL WHEN n %% 3 = 0 THEN %(user_a)s ELSE %(user_b)s END,
       'Perf user',
       (ARRAY['tests.thing.created', 'tests.thing.updated', 'tests.thing.deleted'])[1 + n %% 3],
       (ARRAY['tests.Thing', 'tests.Other', 'rbac.Role'])[1 + n %% 3],
       'rec-' || (n %% 50000),
       'Record ' || (n %% 50000),
       jsonb_build_object('amount', jsonb_build_array((n %% 1000)::text, (n %% 997)::text)),
       '{}'::jsonb, 'perf', '', '', ''
FROM generate_series(1, %(rows)s) AS n
"""


def _user(email: str) -> User:
    return User.objects.create_user(email, password="x" * 12, name=email.split("@")[0])


@pytest.fixture
def big() -> dict[str, Any]:
    org = Organisation.objects.create(name="Big Ltd.")
    other = Organisation.objects.create(name="Other Ltd.")
    owner, user_a, user_b = _user("owner@big.ca"), _user("a@big.ca"), _user("b@big.ca")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    with connection.cursor() as cursor:
        common = {"user_a": user_a.pk, "user_b": user_b.pk}
        cursor.execute(INSERT, {**common, "seed": "big", "org": org.pk, "rows": ROWS})
        cursor.execute(INSERT, {**common, "seed": "other", "org": other.pk, "rows": OTHER_ROWS})
        cursor.execute("ANALYZE audit_event")
        cursor.execute("SELECT count(*) FROM audit_event WHERE organisation_id = %s", [org.pk])
        assert cursor.fetchone()[0] == ROWS
    client = APIClient()
    client.force_authenticate(owner)
    return {"org": org, "client": client, "user_a": user_a}


def timed(call: Callable[[], Any]) -> tuple[Any, float]:
    call()  # warm caches (plans, catalog), as a person paging through the screen would
    started = time.perf_counter()
    result = call()
    return result, time.perf_counter() - started


def url(org: Organisation, path: str) -> str:
    return f"/api/v1/o/{org.public_id}/audit/{path}"


def test_listing_one_million_rows_is_under_a_second_with_the_indexes(big: dict[str, Any]) -> None:
    org, client = big["org"], big["client"]
    timings: dict[str, float] = {}

    first, timings["first page (default 90 days)"] = timed(
        lambda: client.get(url(org, "events"), {"limit": 50})
    )
    assert first.status_code == 200 and len(first.json()["results"]) == 50
    assert first.json()["range"]["default"] is True

    # A page deep in the log: follow the cursor of the 2,000th newest event.
    deep_cursor = client.get(url(org, "events"), {"limit": 200}).json()["next"]
    for _ in range(9):
        deep_cursor = client.get(url(org, "events"), {"limit": 200, "cursor": deep_cursor}).json()[
            "next"
        ]
    deep, timings["page after 2,000 rows"] = timed(
        lambda: client.get(url(org, "events"), {"limit": 50, "cursor": deep_cursor})
    )
    assert deep.status_code == 200 and len(deep.json()["results"]) == 50

    whole_range = {"from": "2024-01-01", "limit": 50}
    _, timings["two years, first page"] = timed(lambda: client.get(url(org, "events"), whole_range))
    user = str(big["user_a"].public_id)
    by_user, timings["user filter"] = timed(
        lambda: client.get(url(org, "events"), {**whole_range, "user": user})
    )
    assert by_user.status_code == 200 and by_user.json()["results"]
    history, timings["record history"] = timed(
        lambda: client.get(url(org, "records/tests.Thing/rec-3"))
    )
    assert history.status_code == 200 and history.json()["results"]
    choices, timings["filter choices"] = timed(lambda: client.get(url(org, "filters")))
    assert len(choices.json()["types"]) == 3

    slow = {
        name: round(seconds, 3) for name, seconds in timings.items() if seconds >= BUDGET_SECONDS
    }
    assert slow == {}, f"over {BUDGET_SECONDS}s: {slow} (all: {timings})"
    print({name: round(seconds, 3) for name, seconds in timings.items()})  # noqa: T201 — report

    # The planner uses the viewer's index, never a scan of the table.
    with connection.cursor() as cursor:
        cursor.execute(
            "EXPLAIN SELECT * FROM audit_event WHERE organisation_id = %s "
            "AND created_at >= now() - interval '90 days' ORDER BY created_at DESC, id DESC "
            "LIMIT 51",
            [org.pk],
        )
        plan = "\n".join(row[0] for row in cursor.fetchall())
    assert "audit_org_time_idx" in plan, plan
    assert "Seq Scan" not in plan, plan
