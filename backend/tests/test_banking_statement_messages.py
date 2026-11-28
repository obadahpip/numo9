"""F-02-T15 — i18n keys, audit hooks (import, undo), error-message catalogue.

Acceptance: i18n lint passes — every gettext string of banking (statement import included) is in
the en_CA and fr_CA catalogues with a real French translation, and every catalogue message of
the import reads in French; messages name the row and the fix ("Row 14: date '13/25/2026'
doesn't match DD/MM/YYYY. Choose the date format…"), file messages name the file; an API refusal
answers in the person's language (their locale). Committing and undoing an import write audit events
attributed to the person, with the file, the counts and the lines removed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import translation

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.audit.presenter import action_label
from numo9.banking.services import create_bank_account
from numo9.banking.statements import errors
from numo9.banking.statements.errors import LineProblem
from numo9.i18n.errors import CATALOGUE
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.statement_helpers import fixture
from tools.i18n_catalogs import load_po

BANKING = Path(__file__).resolve().parents[1] / "numo9" / "banking"
LOCALE = Path(__file__).resolve().parents[1] / "locale"
GETTEXT = {"_", "gettext", "gettext_lazy", "pgettext", "ngettext"}
FIX_WORDS = re.compile(
    r"\b(Choose|Fill|Map|Verify|Review|Correct|Keep|Download|Open|Fix|Upload|Undo|Remove|Split"
    r"|turn on)\b",
    re.IGNORECASE,
)
#: Messages that report a fact rather than ask for something.
INFORMATIVE = {
    "banking.statement.row.duplicate",
    "banking.statement.file.several_accounts",
    "banking.import.not_committed",
}
STATEMENT_CODES = sorted(
    c for c in CATALOGUE if c.startswith(("banking.statement.", "banking.import."))
)


def msgids() -> set[str]:
    found: set[str] = set()
    for path in BANKING.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and node.args:
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                first = node.args[0]
                if (
                    name in GETTEXT
                    and isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                ):
                    found.add(first.value)
    return found


def test_every_banking_string_is_in_both_catalogues_with_french() -> None:
    en = {e.msgid for e in load_po(LOCALE / "en_CA" / "LC_MESSAGES" / "django.po")}
    fr = {e.msgid: e.msgstr[0] for e in load_po(LOCALE / "fr_CA" / "LC_MESSAGES" / "django.po")}
    strings = msgids()
    assert len(strings) > 80
    missing = sorted(s for s in strings if s not in en or s not in fr)
    assert missing == []
    untranslated = sorted(
        s for s in strings if "import" in s.lower() or "row" in s.lower() if not fr.get(s)
    )
    assert untranslated == []


def test_the_catalogue_has_every_statement_message() -> None:
    assert len(STATEMENT_CODES) >= 27
    for code in (
        "banking.statement.row.date_format",
        "banking.statement.row.duplicate",
        "banking.statement.file.empty",
        "banking.statement.layout.no_date",
        "banking.import.has_errors",
        "banking.import.in_use",
    ):
        assert code in CATALOGUE


def test_the_example_message_names_the_row_and_the_fix() -> None:
    problem = LineProblem(
        errors.ROW_DATE_FORMAT, {"row": 14, "value": "13/25/2026", "format": "DD/MM/YYYY"}
    )
    assert problem.message() == (
        "Row 14: date '13/25/2026' doesn't match DD/MM/YYYY. Choose the date format your bank "
        "uses on the Map step, or correct the row."
    )
    with translation.override("fr-ca"):
        assert problem.message() == (
            "Ligne 14 : la date « 13/25/2026 » ne correspond pas au format DD/MM/YYYY. Choisissez "
            "le format de date de votre banque à l’étape Correspondance, ou corrigez la ligne."
        )


@pytest.mark.parametrize("code", STATEMENT_CODES)
def test_each_message_says_what_to_do_in_english_and_french(code: str) -> None:
    error = CATALOGUE[code]
    params: dict[str, Any] = {
        "row": 7,
        "value": "x",
        "format": "DD/MM/YYYY",
        "debit": "1.00",
        "credit": "2.00",
        "name": "june.csv",
        "reason": "bad quote",
        "max": 25,
        "count": 3,
        "account": "•••• 4321",
    }
    with translation.override("en-ca"):
        english = error.text(**params)
    with translation.override("fr-ca"):
        french = error.text(**params)
    assert french != english, f"{code}: no French"
    if ".row." in code:
        assert english.startswith("Row 7") and french.startswith(("Ligne 7", "La ligne 7"))
    if ".file." in code and "several_accounts" not in code:
        assert "june.csv" in english and "june.csv" in french
    if code not in INFORMATIVE:
        assert FIX_WORDS.search(english), f"{code}: the message doesn't say what to do: {english}"


@pytest.mark.django_db
def test_api_refusals_answer_in_the_persons_language(s3: str) -> None:
    org = Organisation.objects.create(name="Érable inc.")
    with org_context(org):
        bank = create_bank_account(org, type="chequing", display_name="Chèques")
    user = User.objects.create_user("lea@erable.ca", name="Léa", locale="fr-ca")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    client = Client()
    client.force_login(user)
    refused = client.post(
        f"/api/v1/o/{org.public_id}/bank-accounts/{bank.public_id}/imports",
        {"file": SimpleUploadedFile("vide.ofx", b"OFXHEADER:100\n\n")},
    )
    assert refused.status_code == 400
    assert refused.json()["code"] == "banking.statement.file.no_statement"
    assert refused.json()["detail"].startswith("vide.ofx ne contient aucun relevé bancaire")


@pytest.mark.django_db
def test_import_and_undo_are_audited_with_the_person(s3: str) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        bank = create_bank_account(org, type="chequing", display_name="RBC Chequing")
    user = User.objects.create_user("dana@refined.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    client = Client()
    client.force_login(user)
    base = f"/api/v1/o/{org.public_id}/bank-accounts/{bank.public_id}/imports"
    created = client.post(
        base, {"file": SimpleUploadedFile("rbc.csv", fixture("rbc_chequing.csv"))}
    )
    one = f"{base}/{created.json()['import']['id']}"
    assert client.post(f"{one}/commit", {}, content_type="application/json").status_code == 200
    assert client.post(f"{one}/undo", {}, content_type="application/json").status_code == 200
    with org_context(org):
        committed = AuditEvent.objects.get(action="banking.statementimport.committed")
        undone = AuditEvent.objects.get(action="banking.statementimport.undone")
    assert committed.actor_user_id == undone.actor_user_id == user.pk
    assert committed.meta["file_name"] == "rbc.csv"
    assert committed.meta["lines"] == {"total": 5, "new": 5, "duplicate": 0, "error": 0}
    assert committed.meta["mapping"] == "RBC Royal Bank"
    assert undone.meta["lines_removed"] == 5
    assert action_label("banking.statementimport.committed") == "Statement imported"
    with translation.override("fr-ca"):
        assert action_label("banking.statementimport.undone") == "Importation de relevé annulée"
