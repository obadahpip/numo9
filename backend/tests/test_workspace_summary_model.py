"""V-01-T02 — ``OrgDirectorySummary``: one denormalised directory row per practice × organisation.

Acceptance: migration; GIN index on the search vector, trigram index on the BN.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from numo9.tenancy.checks import models_violating_org_ownership
from numo9.workspace.models import DirectoryStatus, OrgDirectorySummary
from tests.workspace_helpers import client_org, practice

pytestmark = pytest.mark.django_db


def _row(**fields: Any) -> OrgDirectorySummary:
    firm = fields.pop("practice", None) or practice()
    organisation = fields.pop("organisation", None) or client_org(None, "Maple Leaf Supply Ltd.")
    defaults: dict[str, Any] = {
        "name": "Maple Leaf Supply Ltd.",
        "status": DirectoryStatus.PAID,
        "refreshed_at": timezone.now(),
    }
    defaults.update(fields)
    return OrgDirectorySummary.objects.create(practice=firm, organisation=organisation, **defaults)


def test_row_holds_every_directory_fact_with_safe_defaults() -> None:
    row = _row(bn="123456782", province="ON", package="growth", tags=["Retail"])
    row.refresh_from_db()
    assert (row.fye_month, row.fye_day, row.gst_cycle) == (12, 31, "")
    assert (row.payroll_enabled, row.overdue_count, row.unfiled_count) == (False, 0, 0)
    assert row.tags == ["Retail"]
    assert str(row) == "Abuodeh CPA → Maple Leaf Supply Ltd."


def test_one_row_per_practice_and_organisation() -> None:
    row = _row()
    with pytest.raises(IntegrityError), transaction.atomic():
        _row(practice=row.practice, organisation=row.organisation)
    # the same organisation in another practice is another row (tags are per practice)
    _row(practice=practice("Other CPA"), organisation=row.organisation)
    assert OrgDirectorySummary.objects.filter(organisation=row.organisation).count() == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "active"), ("gst_cycle", "weekly"), ("fye_month", 13), ("fye_month", 0)],
)
def test_database_refuses_invalid_values(field: str, value: object) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _row(**{field: value})


def test_search_and_bn_indexes_exist() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'workspace_orgdirectorysummary'"
        )
        indexes = dict(cursor.fetchall())
    assert "USING gin (search_vector)" in indexes["workspace_summary_search_idx"]
    assert "USING gin (bn gin_trgm_ops)" in indexes["workspace_summary_bn_trgm_idx"]
    with connection.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension")
        assert {"unaccent", "pg_trgm"} <= {name for (name,) in cursor.fetchall()}


def test_rows_go_with_their_practice_or_organisation() -> None:
    row = _row()
    row.practice.delete()  # derived data: no PROTECT
    assert not OrgDirectorySummary.objects.exists()


def test_allow_listed_as_a_platform_read_model() -> None:
    from django.apps import apps

    assert OrgDirectorySummary not in models_violating_org_ownership(
        [apps.get_app_config("workspace")], ["numo9."]
    )
