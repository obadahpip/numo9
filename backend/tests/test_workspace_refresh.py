"""V-01-T03 — directory summary refresh service, signals and the nightly full rebuild.

Acceptance: a change is reflected in the directory in < 5 s (integration: the source record is
saved and committed, then the directory row is read back).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.db import connection
from django.utils import timezone

from numo9.entitlements.models import Subscription, SubscriptionStatus
from numo9.orgsettings.models import OrganisationSettings, RegistrationType, TaxRegistration
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationStatus,
    PracticeAssignment,
)
from numo9.workspace import summary
from numo9.workspace.models import DirectoryStatus, OrgDirectorySummary
from numo9.workspace.tasks import REBUILD_DIRECTORY, rebuild_directory
from tests.entitlement_helpers import package, subscribe
from tests.job_helpers import deliver
from tests.workspace_helpers import client_org, practice, user, valid_bn

pytestmark = pytest.mark.django_db

Commit = Callable[..., Any]


@pytest.fixture
def commit(django_capture_on_commit_callbacks: Any) -> Commit:
    """``with commit():`` runs the block, then its on-commit callbacks — as a real commit would."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


def row(organisation: Organisation, firm: Any = None) -> OrgDirectorySummary:
    rows = OrgDirectorySummary.objects.filter(organisation=organisation)
    if firm is not None:
        rows = rows.filter(practice=firm)
    return rows.get()


def matches(organisation: Organisation, query: str) -> bool:
    """The row's search vector matches the tsquery ``query`` (simple configuration)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT search_vector @@ to_tsquery('simple', unaccent(%s)) "
            "FROM workspace_orgdirectorysummary WHERE organisation_id = %s",
            [query, organisation.pk],
        )
        return bool(cursor.fetchone()[0])


def test_new_client_appears_with_its_facts(commit: Commit) -> None:
    firm = practice()
    owner = user("dana@erable.ca", "Dana Tremblay")
    with commit():
        organisation = client_org(
            firm,
            "Érable Bakery Inc.",
            settings={
                "legal_name": "Érable Bakery Incorporated",
                "industry": "Bakery",
                "mailing_province": "QC",
                "mailing_postal_code": "H2X 1Y4",
                "fye_month": 3,
                "fye_day": 31,
            },
            bn=valid_bn(87451299),
            owner=owner,
        )
    got = row(organisation, firm)
    assert (got.name, got.legal_name, got.industry, got.province) == (
        "Érable Bakery Inc.",
        "Érable Bakery Incorporated",
        "Bakery",
        "QC",
    )
    assert (got.bn, got.fye_month, got.fye_day) == (valid_bn(87451299), 3, 31)
    assert (got.owner_name, got.owner_email) == ("Dana Tremblay", "dana@erable.ca")
    assert got.status == DirectoryStatus.PAID
    # accent-insensitive, prefix, BN, owner, province names (English and French)
    assert matches(organisation, "erable:* & bakery:*")
    assert matches(organisation, valid_bn(87451299)[:5] + ":*")
    assert matches(organisation, "tremblay")
    assert matches(organisation, "dana:*")
    assert matches(organisation, "quebec") and matches(organisation, "QC")


@pytest.mark.parametrize(
    "change",
    ["settings", "registration", "subscription", "owner", "owner_renamed", "status"],
)
def test_change_is_reflected_in_under_5_seconds(commit: Commit, change: str) -> None:
    firm = practice()
    owner = user("sam@maple.ca", "Sam Patel")
    with commit():
        organisation = client_org(firm, "Maple Leaf Supply Ltd.", settings={}, owner=owner)
    started = time.monotonic()
    with commit(), org_context(organisation):
        if change == "settings":
            settings = OrganisationSettings.objects.get()
            settings.display_name = "Maple Leaf Supply Co."
            settings.mailing_province = "ON"
            settings.mailing_postal_code = "M5V 2T6"
            settings.save()
        elif change == "registration":
            TaxRegistration(
                organisation=organisation, type=RegistrationType.BN, number=valid_bn(12345678)
            ).save()
        elif change == "subscription":
            subscribe(organisation, package("growth", ["accounting", "payroll"]))
        elif change == "owner":
            OrganisationMember.objects.filter(organisation=organisation).delete()
        elif change == "owner_renamed":
            owner.name = "Samira Patel"
            owner.save(update_fields=["name"])
        else:
            organisation.status = OrganisationStatus.CANCELLED
            organisation.save()
    got = row(organisation)
    elapsed = time.monotonic() - started
    expected = {
        "settings": ("name", "Maple Leaf Supply Co."),
        "registration": ("bn", valid_bn(12345678)),
        "subscription": ("package", "growth"),
        "owner": ("owner_name", ""),
        "owner_renamed": ("owner_name", "Samira Patel"),
        "status": ("status", DirectoryStatus.ARCHIVED),
    }[change]
    assert getattr(got, expected[0]) == expected[1]
    assert elapsed < 5


def test_subscription_facts_package_payroll_and_trial_end(commit: Commit) -> None:
    firm = practice()
    with commit():
        organisation = client_org(firm, "North Shore Movers", status=OrganisationStatus.TRIAL)
    assert row(organisation).status == DirectoryStatus.TRIAL
    ends = timezone.now() + timedelta(days=12)
    with commit():
        subscribe(
            organisation,
            package("payroll_plus", ["accounting", "payroll"]),
            status=SubscriptionStatus.TRIALING,
            current_period_end=ends,
        )
    got = row(organisation)
    assert (got.package, got.payroll_enabled, got.trial_ends_at) == ("payroll_plus", True, ends)
    with commit(), org_context(organisation):
        subscription = Subscription.objects.get()
        subscription.package = package("books", ["accounting"])
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.save()
    got = row(organisation)
    assert (got.package, got.payroll_enabled, got.status, got.trial_ends_at) == (
        "books",
        False,
        DirectoryStatus.PAID,
        None,
    )


def test_assignment_off_removes_the_row_and_back_on_restores_it(commit: Commit) -> None:
    firm, other = practice(), practice("Second CPA")
    with commit():
        organisation = client_org(firm, "Toronto Tile Co.")
        PracticeAssignment.objects.create(practice=other, organisation=organisation)
    assert OrgDirectorySummary.objects.filter(organisation=organisation).count() == 2
    assignment = PracticeAssignment.objects.get(practice=firm, organisation=organisation)
    with commit():
        assignment.active = False
        assignment.save()
    assert list(OrgDirectorySummary.objects.values_list("practice", flat=True)) == [other.pk]
    with commit():
        assignment.active = True
        assignment.save()
    assert OrgDirectorySummary.objects.filter(organisation=organisation).count() == 2


def test_self_managed_organisation_has_no_directory_row(commit: Commit) -> None:
    with commit():
        organisation = client_org(None, "Solo Ltd.", owner=user("solo@solo.ca"))
    assert not OrgDirectorySummary.objects.filter(organisation=organisation).exists()


def test_one_refresh_per_organisation_per_transaction(
    django_capture_on_commit_callbacks: Any,
) -> None:
    firm = practice()
    with django_capture_on_commit_callbacks() as callbacks:
        organisation = client_org(firm, "Maple", settings={}, bn=valid_bn(1), owner=user("o@m.ca"))
        organisation.name = "Maple 2"
        organisation.save()
    refreshes = [c for c in callbacks if isinstance(c, summary._Refresh)]
    assert len(refreshes) == 1


def test_unrelated_user_save_schedules_nothing(django_capture_on_commit_callbacks: Any) -> None:
    owner = user("o@m.ca")
    client_org(practice(), "Maple", owner=owner)
    with django_capture_on_commit_callbacks() as callbacks:
        owner.save(update_fields=["last_login"])
    assert not [c for c in callbacks if isinstance(c, summary._Refresh)]


@pytest.fixture
def providers() -> Iterator[None]:
    yield
    summary.unregister_summary_provider("gst")
    summary.unregister_summary_provider("broken")
    summary.register_tags_provider(None)


def test_later_phases_plug_in_providers_and_tags(
    commit: Commit, providers: None, caplog: pytest.LogCaptureFixture
) -> None:
    firm = practice()
    summary.register_summary_provider(
        "gst",
        lambda org: {"gst_cycle": "quarterly", "overdue_count": 3, "unfiled_count": 1, "name": "x"},
    )
    summary.register_summary_provider("broken", lambda org: 1 / 0)  # type: ignore[arg-type,return-value]
    summary.register_tags_provider(lambda p, org: ["Retail", "Toronto office", "Retail"])
    caplog.set_level(logging.ERROR, logger="numo9.workspace")
    with commit():
        organisation = client_org(firm, "Maple Leaf Supply Ltd.")
    got = row(organisation)
    assert (got.gst_cycle, got.overdue_count, got.unfiled_count) == ("quarterly", 3, 1)
    assert got.name == "Maple Leaf Supply Ltd."  # providers can't overwrite core facts
    assert got.tags == ["Retail", "Toronto office"]
    assert matches(organisation, "toronto & office")
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "broken failed" in messages and "returned ['name']" in messages


def test_failing_refresh_never_fails_the_save(
    commit: Commit, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def explode(organisation: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(summary, "organisation_facts", explode)
    with commit():
        organisation = client_org(practice(), "Maple")
    assert not OrgDirectorySummary.objects.filter(organisation=organisation).exists()
    assert "Directory refresh of organisation" in caplog.text


def test_rebuild_all_repairs_drift_and_removes_orphans() -> None:
    firm = practice()
    kept = client_org(firm, "Kept Ltd.")  # no commit: signals' refreshes never ran
    gone = client_org(firm, "Gone Ltd.", active=False)
    OrgDirectorySummary.objects.create(
        practice=firm, organisation=gone, name="stale", status="paid", refreshed_at=timezone.now()
    )
    seen: list[tuple[int, int]] = []
    result = summary.rebuild_all(progress=lambda d, t: seen.append((d, t)))
    assert result == {"organisations": 1, "rows": 1, "removed": 1}
    assert row(kept).name == "Kept Ltd."
    assert seen == [(1, 1)]


def test_nightly_job_is_scheduled_and_runs(sent: list[dict[str, Any]]) -> None:
    from numo9.celery import app as celery_app
    from numo9.jobs.runtime import start_job

    entry = celery_app.conf.beat_schedule[REBUILD_DIRECTORY]
    assert entry["task"] == REBUILD_DIRECTORY
    client_org(practice(), "Maple")
    start_job(rebuild_directory, key="tonight")
    assert deliver(rebuild_directory, sent[0]) == {"organisations": 1, "rows": 1, "removed": 0}


def test_rebuild_command(capsys: pytest.CaptureFixture[str]) -> None:
    from django.core.management import call_command

    client_org(practice(), "Maple")
    call_command("rebuild_directory")
    assert "1 organisations, 1 directory rows (0 orphan rows removed)." in capsys.readouterr().out
