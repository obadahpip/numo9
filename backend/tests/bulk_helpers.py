"""Shared world for the bulk action tests (V-03): a practice, its admin and an accountant, client
organisations in the directory."""

from __future__ import annotations

from typing import Any

from django.test import Client

from numo9.tenancy.models import PracticeRole
from numo9.workspace.summary import rebuild_all
from tests.workspace_helpers import client_org, member, practice, user


def bulk_world(count: int = 3, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    firm = practice("Abuodeh CPA")
    admin = user("admin@cpa.ca", name="Ada Admin")
    member(firm, admin, role=PracticeRole.PRACTICE_ADMIN)
    accountant_user = user("sam@cpa.ca", name="Sam Patel")
    accountant = member(firm, accountant_user)
    owners = [user(f"owner{i}@client.ca", name=f"Owner {i}") for i in range(count)]
    orgs = [
        client_org(firm, f"Client {i:03d}", settings=settings or {}, owner=owners[i])
        for i in range(count)
    ]
    stranger = client_org(None, "Not a client", settings={})
    rebuild_all()
    browser = Client()
    browser.force_login(admin)
    return {
        "practice": firm,
        "admin": admin,
        "accountant": accountant,
        "accountant_user": accountant_user,
        "orgs": orgs,
        "owners": owners,
        "stranger": stranger,
        "browser": browser,
    }
