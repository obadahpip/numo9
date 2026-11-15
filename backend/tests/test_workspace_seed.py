"""V-01-T06 — performance fixture ``manage.py seed_practice --orgs N``.

Acceptance: the command creates the data in < 2 minutes for 2,000 organisations (the full-size run
is ``test_two_thousand_organisations_in_under_two_minutes``).
"""

from __future__ import annotations

import time
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from numo9.orgsettings.validators import luhn_valid
from numo9.tenancy.models import Practice, PracticeMember, PracticeRole
from numo9.workspace.models import OrgDirectorySummary
from numo9.workspace.search import DirectoryParams, DirectoryQuery

pytestmark = pytest.mark.django_db


def seed(*args: str) -> str:
    out = StringIO()
    call_command("seed_practice", *args, "--force", stdout=out)
    return out.getvalue()


def test_seed_creates_a_realistic_practice() -> None:
    output = seed("--orgs", "60", "--staff", "3", "--seed", "7")
    practice = Practice.objects.get(name="Seed Practice")
    assert "60 organisations, 3 staff" in output and str(practice.public_id) in output
    rows = OrgDirectorySummary.objects.filter(practice=practice)
    assert rows.count() == 60
    assert len(set(rows.values_list("name", flat=True))) == 60
    assert all(luhn_valid(bn) for bn in rows.exclude(bn="").values_list("bn", flat=True))
    assert rows.exclude(bn="").count() >= 45
    assert set(rows.values_list("status", flat=True)) >= {"paid", "trial"}
    assert rows.filter(status="trial", trial_ends_at__isnull=False).exists()
    assert set(rows.values_list("package", flat=True)) <= {
        "seed_books",
        "seed_growth",
        "seed_complete",
    }
    assert rows.exclude(owner_name="").count() == 60
    assert rows.exclude(gst_cycle="").count() == 60  # sample counts on by default
    admin = PracticeMember.objects.get(practice=practice, role=PracticeRole.PRACTICE_ADMIN).user
    assert not admin.has_usable_password()
    # each accountant has a share of the clients: their directory is a third of the admin's
    staff = PracticeMember.objects.filter(practice=practice, role=PracticeRole.ACCOUNTANT).first()
    assert staff is not None
    _rows, mine = DirectoryQuery(
        staff.user, practice, DirectoryParams(include_archived=True)
    ).page()
    assert mine == 20


def test_same_seed_same_data_and_reruns_add_more() -> None:
    seed("--orgs", "10", "--seed", "3", "--no-sample-counts")
    first = sorted(OrgDirectorySummary.objects.values_list("name", flat=True))
    assert OrgDirectorySummary.objects.filter(gst_cycle="").count() == 10
    seed("--orgs", "10", "--seed", "3")
    assert OrgDirectorySummary.objects.count() == 20
    names = list(OrgDirectorySummary.objects.values_list("name", flat=True))
    assert len(set(names)) == 20  # a rerun never duplicates a name in the practice
    assert set(first) <= set(names)


def test_password_makes_admin_and_staff_able_to_sign_in() -> None:
    from allauth.account.models import EmailAddress

    seed("--orgs", "1", "--staff", "1", "--password", "seed pass 2026", "--admin", "a@seed.test")
    for email in ("a@seed.test", "a+staff1@seed.test"):
        address = EmailAddress.objects.get(email=email)
        assert address.verified and address.user.check_password("seed pass 2026")


def test_refused_outside_dev_and_bad_counts() -> None:
    with pytest.raises(CommandError, match="dev/staging only"):
        call_command("seed_practice", "--orgs", "1", stdout=StringIO())
    with pytest.raises(CommandError, match="between 1 and 20,000"):
        seed("--orgs", "0")


def test_two_thousand_organisations_in_under_two_minutes() -> None:
    started = time.monotonic()
    seed("--orgs", "2000")
    elapsed = time.monotonic() - started
    assert OrgDirectorySummary.objects.count() == 2000
    assert elapsed < 120, elapsed
    # V-01-T07 in-process guard (the k6 run measures it over HTTP): the queries of one directory
    # request over the 2,000 organisations stay far below the 300 ms p95 budget.
    practice = Practice.objects.get(name="Seed Practice")
    admin = PracticeMember.objects.get(practice=practice, role=PracticeRole.PRACTICE_ADMIN).user
    timings = []
    for params in [
        DirectoryParams(page_size=50),
        DirectoryParams(q="maple", page_size=50),
        DirectoryParams(q="123 4", page_size=50),
        DirectoryParams(filters={"province": ["ON"], "status": ["paid"]}, page_size=50),
        DirectoryParams(sort=["-overdue"], page_size=50),
    ] * 4:
        started = time.monotonic()
        query = DirectoryQuery(admin, practice, params)
        query.page()
        query.facets()
        query.total()
        timings.append(time.monotonic() - started)
    timings.sort()
    assert timings[int(len(timings) * 0.95) - 1] < 0.3, timings
