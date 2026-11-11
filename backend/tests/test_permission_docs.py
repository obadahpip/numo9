"""Permission catalogue docs page generated into MkDocs (A-03-T16). Acceptance: the page builds.

CI: the backend job runs ``permcat_docs --check`` (the committed page equals the code) and the
docs job runs ``mkdocs build --strict`` with the page in the nav. These tests prove the check
catches a stale page and that the page carries every permission, both languages and the roles.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from numo9.rbac.catalogue import Permission, Risk, catalogue
from numo9.rbac.management.commands.permcat_docs import DEFAULT_OUTPUT, render

REPO = Path(__file__).resolve().parents[2]


def test_committed_page_is_up_to_date() -> None:
    out = StringIO()
    call_command("permcat_docs", "--check", stdout=out)
    assert "is up to date" in out.getvalue()
    assert DEFAULT_OUTPUT == REPO / "docs" / "reference" / "permission-catalogue.md"


def test_page_lists_every_permission_in_both_languages_with_roles() -> None:
    page = render()
    for permission in catalogue:
        assert f"| `{permission.key}` |" in page
    assert (
        "| `organisation.close` | Close the organisation *(owner only)* | Fermer l’organisation |"
        in page
    )
    row = next(line for line in page.splitlines() if line.startswith("| `roles.role.manage`"))
    assert row.endswith("| critical | organisation | Practice admin, Owner, Admin |")
    assert "## Users and roles { #users }" in page
    assert "| organisation | Owner | `owner` |" in page
    assert page.count("\n## ") == 5  # 4 modules + system roles


def test_stale_page_fails_the_check(tmp_path: Path) -> None:
    page = tmp_path / "permission-catalogue.md"
    call_command("permcat_docs", "--output", str(page), stdout=StringIO())
    call_command("permcat_docs", "--check", "--output", str(page), stdout=StringIO())
    added = Permission("organisation.docs.test", "Docs test permission", "settings", Risk.LOW)
    catalogue.register(added)
    try:
        with pytest.raises(CommandError, match="out of date"):
            call_command("permcat_docs", "--check", "--output", str(page), stdout=StringIO())
    finally:
        catalogue.unregister(added.key)
    page.write_text(page.read_text(encoding="utf-8").replace("\n", "\r\n"), encoding="utf-8")
    call_command("permcat_docs", "--check", "--output", str(page), stdout=StringIO())  # CRLF ok


def test_missing_page_fails_the_check(tmp_path: Path) -> None:
    with pytest.raises(CommandError):
        call_command("permcat_docs", "--check", "--output", str(tmp_path / "nope.md"))


@pytest.mark.skipif(not (REPO / "mkdocs.yml").exists(), reason="docs not in this checkout")
def test_page_is_in_the_docs_nav_and_checked_by_ci() -> None:
    assert "reference/permission-catalogue.md" in (REPO / "mkdocs.yml").read_text(encoding="utf-8")
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python manage.py permcat_docs --check" in workflow
