"""A-06-T11 — "create from file" action registry (backend part).

The planned actions (bill E-02, expense claim E-04, asset I-01) are listed greyed with their
reason; a module registering an available action makes it a working action with its URL; a
document still being scanned or of a type the action can't read explains why. The rendering is
tested in frontend/src/files/CreateFromFile.test.tsx (Vitest, the task's acceptance).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from numo9.files import storage
from numo9.files.actions import FileAction, register_file_action, unregister_file_action
from numo9.files.models import Document, DocumentStatus
from numo9.tenancy.models import Organisation
from tests.files_helpers import api, owner_of

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def client(org: Organisation) -> Any:
    return api(owner_of(org))


def make(org: Organisation, name: str, mime: str, status: str = DocumentStatus.CLEAN) -> Document:
    from numo9.tenancy.context import org_context

    with org_context(org):
        item = Document(
            organisation=org,
            name=name,
            file_key=storage.new_key(org, name),
            mime=mime,
            size=10,
            status=status,
        )
        item.save()
        return item


def actions(client: Any, org: Organisation, item: Document) -> list[dict[str, Any]]:
    response = client.get(f"/api/v1/o/{org.public_id}/files/{item.public_id}/actions")
    assert response.status_code == 200
    results: list[dict[str, Any]] = response.json()["results"]
    return results


def test_planned_actions_are_listed_with_their_reason(client: Any, org: Organisation) -> None:
    listed = actions(client, org, make(org, "bill.pdf", "application/pdf"))
    assert [(a["key"], a["label"], a["available"], a["reason"]) for a in listed] == [
        ("bill", "Create a bill", False, "Bills arrive with Purchases in Phase 1."),
        (
            "expense",
            "Create an expense claim",
            False,
            "Expense claims arrive with Purchases in Phase 1.",
        ),
        ("asset", "Create a fixed asset", False, "The fixed asset register arrives in Phase 2."),
    ]


@pytest.fixture
def receipts_module() -> Iterator[None]:
    register_file_action(
        FileAction(
            key="receipt",
            label="Record a receipt",
            module="banking",
            deliverable="F-99",
            available=True,
            url="/o/{org}/banking/receipts/new?document={document}",
            mimes=frozenset({"application/pdf"}),
        )
    )
    yield
    unregister_file_action("receipt")


@pytest.mark.usefixtures("receipts_module")
def test_a_registered_module_action_works_and_explains_when_it_cant(
    client: Any, org: Organisation
) -> None:
    pdf = make(org, "receipt.pdf", "application/pdf")
    receipt = next(a for a in actions(client, org, pdf) if a["key"] == "receipt")
    assert receipt["available"] is True and receipt["reason"] == ""
    assert receipt["url"] == f"/o/{org.public_id}/banking/receipts/new?document={pdf.public_id}"
    sheet = make(org, "bank.csv", "text/csv")
    receipt = next(a for a in actions(client, org, sheet) if a["key"] == "receipt")
    assert receipt == {
        **receipt,
        "available": False,
        "url": "",
        "reason": "This action reads PDF files and images only.",
    }
    scanning = make(org, "new.pdf", "application/pdf", DocumentStatus.SCANNING)
    receipt = next(a for a in actions(client, org, scanning) if a["key"] == "receipt")
    assert receipt["reason"] == "Wait until the file has been checked for viruses."
