"""S-03-T04 — EncryptedField: AES-256-GCM envelope encryption, key id stored with the
ciphertext; values unreadable in the database; `rotate_field_encryption` re-wraps them."""

from __future__ import annotations

import base64
import io
import json
import os
from collections.abc import Iterator

import pytest
from django.core.exceptions import FieldError, ImproperlyConfigured, ValidationError
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import override_settings

from numo9.security import crypto
from numo9.security.checks import check_field_encryption_keys
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.testapp.models import Payee

SIN = "046454286"
ACCOUNT = "003-12345-6789012"


def _key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


KEY_A, KEY_B = _key(), _key()
RING_A = {"FIELD_ENCRYPTION_KEYS": json.dumps({"a": KEY_A}), "FIELD_ENCRYPTION_ACTIVE_KEY": "a"}
RING_AB = {
    "FIELD_ENCRYPTION_KEYS": json.dumps({"a": KEY_A, "b": KEY_B}),
    "FIELD_ENCRYPTION_ACTIVE_KEY": "b",
}
RING_B = {"FIELD_ENCRYPTION_KEYS": json.dumps({"b": KEY_B}), "FIELD_ENCRYPTION_ACTIVE_KEY": "b"}


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery")


@pytest.fixture
def ctx(org: Organisation) -> Iterator[Organisation]:
    with org_context(org):
        yield org


def raw(pk: int) -> tuple[str | None, str | None]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT sin, bank_account FROM {Payee._meta.db_table} WHERE id = %s",  # noqa: S608
            [pk],
        )
        row = cursor.fetchone()
    return row[0], row[1]


def write_raw(pk: int, column: str, value: str) -> None:
    assert column in {"sin", "bank_account"}
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {Payee._meta.db_table} SET {column} = %s WHERE id = %s",  # noqa: S608
            [value, pk],
        )


# ---- Storage ------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_value_is_unreadable_in_the_database(ctx: Organisation) -> None:
    payee = Payee.objects.create(name="Dana", sin=SIN, bank_account=ACCOUNT)
    stored_sin, stored_account = raw(payee.pk)
    for stored, plain in ((stored_sin, SIN), (stored_account, ACCOUNT)):
        assert stored is not None
        assert stored.startswith("n9e1:test-local:")
        assert plain not in stored
        assert base64.b64encode(plain.encode()).decode()[:8] not in stored
    loaded = Payee.objects.get(pk=payee.pk)
    assert (loaded.sin, loaded.bank_account) == (SIN, ACCOUNT)


@pytest.mark.django_db
def test_each_encryption_is_randomised(ctx: Organisation) -> None:
    first = Payee.objects.create(name="A", sin=SIN)
    second = Payee.objects.create(name="B", sin=SIN)
    assert raw(first.pk)[0] != raw(second.pk)[0]


@pytest.mark.django_db
def test_blank_and_null_are_kept_as_is(ctx: Organisation) -> None:
    payee = Payee.objects.create(name="Dana", sin="", bank_account=None)
    assert raw(payee.pk) == ("", None)
    assert Payee.objects.filter(bank_account__isnull=True).count() == 1


@pytest.mark.django_db
def test_ciphertext_moved_to_another_column_does_not_decrypt(ctx: Organisation) -> None:
    payee = Payee.objects.create(name="Dana", sin=SIN, bank_account=ACCOUNT)
    write_raw(payee.pk, "bank_account", raw(payee.pk)[0] or "")
    with pytest.raises(crypto.DecryptionError):
        Payee.objects.get(pk=payee.pk)


@pytest.mark.django_db
def test_tampered_ciphertext_is_rejected(ctx: Organisation) -> None:
    payee = Payee.objects.create(name="Dana", sin=SIN)
    stored = raw(payee.pk)[0] or ""
    body = stored.rsplit(":", 1)[1]
    flipped = ("A" if body[5] != "A" else "B").join([body[:5], body[6:]])
    write_raw(payee.pk, "sin", stored.rsplit(":", 1)[0] + ":" + flipped)
    with pytest.raises(crypto.DecryptionError):
        Payee.objects.get(pk=payee.pk)


@pytest.mark.django_db
def test_plain_max_length_is_validated(ctx: Organisation) -> None:
    payee = Payee(name="Dana", sin="0464542860")
    with pytest.raises(ValidationError) as excinfo:
        payee.full_clean(exclude=["organisation", "created_by"])
    assert "sin" in excinfo.value.message_dict


@pytest.mark.django_db
def test_only_isnull_lookups(ctx: Organisation) -> None:
    Payee.objects.create(name="Dana", sin=SIN)
    with pytest.raises(FieldError, match="encrypted; only 'isnull'"):
        list(Payee.objects.filter(sin=SIN))
    with pytest.raises(FieldError):
        list(Payee.objects.filter(sin__startswith="046"))
    assert Payee.objects.filter(sin__isnull=False).count() == 1


def test_cannot_be_indexed_or_unique() -> None:
    from numo9.security.fields import EncryptedField

    for option in ("db_index", "unique"):
        with pytest.raises(ValueError, match="cannot be indexed"):
            EncryptedField(**{option: True})


# ---- Crypto primitives -------------------------------------------------------------------------


def test_round_trip_and_wrong_key() -> None:
    ring_a = crypto.parse_key_ring({"a": KEY_A}, "a")
    ring_b = crypto.parse_key_ring({"b": KEY_B}, "b")
    token = crypto.encrypt("é 123", "app.Model.field", ring_a)
    assert crypto.key_id_of(token) == "a"
    assert crypto.decrypt(token, "app.Model.field", ring_a) == "é 123"
    with pytest.raises(crypto.DecryptionError, match="not in the key ring"):
        crypto.decrypt(token, "app.Model.field", ring_b)
    forged = token.replace(":a:", ":b:")
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(forged, "app.Model.field", ring_b)
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt("plain text", "app.Model.field", ring_a)


def test_rewrap_keeps_the_value_ciphertext() -> None:
    ring_ab = crypto.parse_key_ring({"a": KEY_A, "b": KEY_B}, "b")
    ring_a = crypto.parse_key_ring({"a": KEY_A}, "a")
    token = crypto.encrypt(SIN, "ctx", ring_a)
    moved = crypto.rewrap(token, "ctx", ring_ab)
    assert crypto.key_id_of(moved) == "b"
    assert moved.rsplit(":", 1)[1] == token.rsplit(":", 1)[1]  # value ciphertext unchanged
    assert crypto.decrypt(moved, "ctx", crypto.parse_key_ring({"b": KEY_B}, "b")) == SIN


@pytest.mark.parametrize(
    ("keys", "active", "message"),
    [
        ("", "a", "not configured"),
        ("{not json", "a", "must be a JSON object"),
        ("[]", "a", "non-empty JSON object"),
        (json.dumps({"a": "not base64!"}), "a", "is not base64"),
        (json.dumps({"a": base64.b64encode(b"short").decode()}), "a", "must be 32 bytes"),
        (json.dumps({"bad id!": KEY_A}), "bad id!", "Invalid field-encryption key id"),
        (json.dumps({"a": KEY_A}), "b", "is not in the key ring"),
    ],
)
def test_key_ring_validation(keys: str, active: str, message: str) -> None:
    with pytest.raises(ImproperlyConfigured, match=message):
        crypto.parse_key_ring(keys, active)


# ---- Rotation command ---------------------------------------------------------------------------


def run(*args: str) -> str:
    out = io.StringIO()
    call_command("rotate_field_encryption", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_rotation_rewraps_every_value_for_every_organisation(org: Organisation) -> None:
    other = Organisation.objects.create(name="Cedar Studio")
    with override_settings(**RING_A):
        ids = []
        for owner in (org, other):
            with org_context(owner):
                ids.append(Payee.objects.create(name="X", sin=SIN, bank_account=ACCOUNT).pk)
                ids.append(Payee.objects.create(name="Y", sin="", bank_account=None).pk)
        before = {pk: raw(pk) for pk in ids}

    with override_settings(**RING_AB):
        with pytest.raises(CommandError, match="4 value\\(s\\) are not on the active key b"):
            run("--check")
        assert "4 value(s) would be re-wrapped" in run("--dry-run")
        assert {pk: raw(pk) for pk in ids} == before  # dry run changed nothing
        assert "re-wrapped 4 value(s) under b" in run()
        assert "check: every value is on the active key" in run("--check")

    for pk in ids:
        for old, new in zip(before[pk], raw(pk), strict=True):
            if old:
                assert crypto.key_id_of(new or "") == "b"
                assert (new or "").rsplit(":", 1)[1] == old.rsplit(":", 1)[1]
            else:
                assert new == old

    # The old key can now be removed: values still decrypt with key b alone.
    with override_settings(**RING_B), org_context(other):
        loaded = Payee.objects.get(pk=ids[2])
        assert (loaded.sin, loaded.bank_account) == (SIN, ACCOUNT)


@pytest.mark.django_db
def test_rotation_is_a_no_op_when_everything_is_current(ctx: Organisation) -> None:
    Payee.objects.create(name="Dana", sin=SIN)
    assert "re-wrapped 0 value(s)" in run()


# ---- Configuration checks ---------------------------------------------------------------------


def test_deploy_check_requires_keys() -> None:
    with override_settings(FIELD_ENCRYPTION_KEYS="", FIELD_ENCRYPTION_ACTIVE_KEY=""):
        assert [m.id for m in check_field_encryption_keys()] == ["security.E100"]
    with override_settings(**RING_A):
        assert check_field_encryption_keys() == []
    # The development key (test settings) must never reach a deployed environment.
    assert [m.id for m in check_field_encryption_keys()] == ["security.E102"]


def test_generate_field_key() -> None:
    out = io.StringIO()
    call_command("generate_field_key", "2026-11", stdout=out)
    entry = json.loads("{" + out.getvalue().strip() + "}")
    assert crypto.parse_key_ring(entry, "2026-11").active == "2026-11"
    with pytest.raises(CommandError):
        call_command("generate_field_key", "prod-local", stdout=io.StringIO())
