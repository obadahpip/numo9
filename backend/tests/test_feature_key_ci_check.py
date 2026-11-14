"""CI check `manage.py check_feature_keys` (U-01-T07): red on an undeclared business endpoint
fixture, green otherwise; unknown keys and unenforced declarations fail too."""

from __future__ import annotations

import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from numo9.catalogue.checks import check

pytestmark = pytest.mark.django_db

BACKEND = Path(__file__).resolve().parents[1]
CANARY = "tests.testapp.feature_urls_ci_canary"
CI_WORKFLOW = BACKEND.parent / ".github" / "workflows" / "ci.yml"


def run(*args: str) -> tuple[str, CommandError | None]:
    out = StringIO()
    try:
        call_command("check_feature_keys", *args, stdout=out)
    except CommandError as exc:
        return out.getvalue(), exc
    return out.getvalue(), None


def test_project_is_green_and_every_business_endpoint_declares() -> None:
    output, error = run()
    assert error is None, output
    assert "0 problem(s)" in output
    assert "* GET    /api/v1/o/<uuid:org>/audit/events" in output
    rows, found = check()
    assert found == []
    business = [r for r in rows if r.business]
    assert business and all(r.feature is not None and r.enforced for r in business)


def test_canary_with_an_undeclared_business_endpoint_is_red() -> None:
    output, error = run("--urlconf", CANARY)
    assert error is not None
    assert "* GET    /api/v1/o/<uuid:org>/ci-canary/" in output
    assert "FAIL feature.E001: /api/v1/o/<uuid:org>/ci-canary/: GET on " in output
    assert "tests.testapp.feature_api.CanaryUndeclared" in output
    assert "1 problem(s)" in output  # only the canary


def test_unknown_key_and_unenforced_declaration_fail() -> None:
    output, error = run("--urlconf", "tests.testapp.feature_urls_bad", "--quiet")
    assert error is not None
    assert "feature.E001" in output
    assert "unknown feature key 'accounting.sales_invoicez.read'" in output
    assert "unknown feature key 'tax.nothing_here.read'" in output  # outside business routes
    assert "feature.E003: /api/v1/o/<uuid:org>/not-enforced/" in output
    assert "4 problem(s)" in output
    assert "/api/v1/o/<uuid:org>/undeclared/" not in output.split("FAIL")[0]  # quiet: no table


def test_known_keys_come_from_the_catalogue_table() -> None:
    from numo9.catalogue.models import FeatureKey

    FeatureKey.objects.filter(key="accounting.sales_invoices.read").delete()
    output, error = run("--urlconf", "tests.testapp.feature_urls_bad", "--quiet")
    assert "unknown feature key 'accounting.sales_invoices.read'" in output


@pytest.mark.django_db(transaction=True)
def test_process_exit_code_is_non_zero_like_in_ci() -> None:
    db = connection.settings_dict
    if db["ENGINE"].endswith("sqlite3"):
        pytest.skip("needs a database the manage.py process can open (CI: PostgreSQL)")
    # The process reads the catalogue of this test database (migrated and seeded).
    url = f"postgres://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"
    env = {**os.environ, "DATABASE_URL": url}
    command = [sys.executable, "manage.py", "check_feature_keys", "--quiet"]
    ok = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True, check=False, env=env)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    red = subprocess.run(
        [*command, "--urlconf", CANARY],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert red.returncode == 1, red.stdout + red.stderr
    assert "feature.E001" in red.stdout


def test_ci_runs_the_check_and_the_canary() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "python manage.py check_feature_keys" in workflow
    assert f"check_feature_keys --quiet --urlconf {CANARY}" in workflow
