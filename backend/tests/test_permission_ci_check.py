"""CI check: an endpoint without a permission declaration fails (A-03-T06).

Acceptance: a fixture view without a key turns CI red. CI runs ``manage.py permission_check``
(must pass on the project URLconf) and the canary ``--urlconf tests.testapp.rbac_urls_ci_canary``
(must fail); these tests prove both outcomes, plus the plain-Django-view rule (``rbac.E005``).
"""

from __future__ import annotations

import subprocess
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from numo9.rbac.checks import check_permission_declarations, declarations

BACKEND = Path(__file__).resolve().parents[1]
CANARY = "tests.testapp.rbac_urls_ci_canary"
CI_WORKFLOW = BACKEND.parent / ".github" / "workflows" / "ci.yml"


def run(*args: str) -> tuple[str, CommandError | None]:
    out = StringIO()
    try:
        call_command("permission_check", *args, stdout=out)
    except CommandError as exc:
        return out.getvalue(), exc
    return out.getvalue(), None


def test_project_passes_and_lists_every_endpoint_method() -> None:
    output, error = run()
    assert error is None, output
    assert "GET    /api/v1/me/organisations" in output
    assert "@authenticated" in output and "@public" in output
    assert "0 problem(s)" in output
    assert "undeclared" not in output


def test_fixture_view_without_a_key_fails() -> None:
    output, error = run("--urlconf", CANARY)
    assert error is not None
    assert "GET    /api/v1/ci-canary/" in output and "— undeclared —" in output
    assert "FAIL rbac.E001: /api/v1/ci-canary/: GET on " in output
    assert "tests.testapp.rbac_api.CanaryUndeclared" in output
    assert "1 problem(s)" in output  # only the canary: the real endpoints are fine


def test_quiet_prints_only_problems() -> None:
    output, error = run("--urlconf", CANARY, "--quiet")
    assert error is not None
    assert "/api/v1/me/organisations" not in output
    assert "rbac.E001" in output


def test_process_exit_code_is_non_zero_like_in_ci() -> None:
    """The CI step relies on the exit status of ``manage.py`` itself, not on Python internals."""
    command = [sys.executable, "manage.py", "permission_check", "--quiet"]
    ok = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True, check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    red = subprocess.run(
        [*command, "--urlconf", CANARY], cwd=BACKEND, capture_output=True, text=True, check=False
    )
    assert red.returncode == 1, red.stdout + red.stderr
    assert "rbac.E001" in red.stdout


def test_plain_django_view_under_api_is_reported(settings: Any) -> None:
    messages = check_permission_declarations(urlconf="tests.testapp.rbac_urls_plain")
    assert [(m.id, m.obj) for m in messages] == [
        ("rbac.E005", "tests.testapp.rbac_api.plain_django_view")
    ]
    assert "/api/v1/plain/" in messages[0].msg  # the one outside /api/ is not reported
    settings.RBAC_EXEMPT_VIEWS = {
        **settings.RBAC_EXEMPT_VIEWS,
        "tests.testapp.rbac_api.plain_django_view": "test: reviewed",
    }
    assert check_permission_declarations(urlconf="tests.testapp.rbac_urls_plain") == []


def test_report_rows_match_the_system_check() -> None:
    rows = declarations(CANARY)
    undeclared = [r for r in rows if r.permission is None]
    assert [(r.route, r.method) for r in undeclared] == [("api/v1/ci-canary/", "GET")]
    assert all(r.view.startswith(("numo9.", "tests.")) for r in rows)


@pytest.mark.skipif(not CI_WORKFLOW.exists(), reason="workflow file not in this checkout")
def test_ci_runs_the_check_and_the_canary() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "python manage.py permission_check\n" in workflow
    assert f"python manage.py permission_check --quiet --urlconf {CANARY}" in workflow
