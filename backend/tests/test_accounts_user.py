"""A-02-T01 — custom User model: email as username, name, locale, time-format preference."""

from __future__ import annotations

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.migrations.loader import MigrationLoader
from django.test import Client

from numo9.accounts.models import Locale, TimeFormat, User

PASSWORD = "correct-horse-battery-staple"  # noqa: S105 (test fixture)


def test_auth_user_model_is_accounts_user() -> None:
    assert get_user_model() is User
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == ["name"]
    field_names = {f.name for f in User._meta.get_fields()}
    assert {"email", "name", "locale", "time_format", "is_active", "date_joined"} <= field_names
    assert not {"username", "first_name", "last_name"} & field_names


def test_accounts_migration_is_applied_before_any_user_dependent_migration() -> None:
    """'Created before first migration': from an empty database, accounts.0001 runs before admin."""
    graph = MigrationLoader(None, ignore_no_migrations=True).graph
    plan = graph.forwards_plan(("admin", "0001_initial"))
    assert plan.index(("accounts", "0001_initial")) < plan.index(("admin", "0001_initial"))
    assert graph.root_nodes("accounts") == [("accounts", "0001_initial")]


@pytest.mark.django_db
def test_models_and_migrations_are_in_sync() -> None:
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


@pytest.mark.django_db
def test_create_user_normalises_email_and_hashes_password() -> None:
    user = User.objects.create_user("  Jane.Doe@Example.COM ", PASSWORD, name="Jane Doe")
    assert user.email == "jane.doe@example.com"
    assert user.password != PASSWORD
    assert user.check_password(PASSWORD)
    assert user.is_active and not user.is_staff and not user.is_superuser
    assert str(user) == "jane.doe@example.com"
    assert user.get_full_name() == user.get_short_name() == "Jane Doe"


@pytest.mark.django_db
def test_defaults_english_and_12_hour_time() -> None:
    user = User.objects.create_user("a@example.com", PASSWORD, name="A")
    assert user.locale == Locale.EN_CA
    assert user.time_format == TimeFormat.H12


@pytest.mark.django_db
def test_french_locale_defaults_to_24_hour_time_unless_chosen() -> None:
    fr = User.objects.create_user("fr@example.com", PASSWORD, name="F", locale=Locale.FR_CA)
    assert fr.time_format == TimeFormat.H24
    chosen = User.objects.create_user(
        "fr12@example.com", PASSWORD, name="G", locale=Locale.FR_CA, time_format=TimeFormat.H12
    )
    assert chosen.time_format == TimeFormat.H12


@pytest.mark.django_db
def test_user_without_password_has_unusable_password() -> None:
    user = User.objects.create_user("invited@example.com", name="Invited")
    assert not user.has_usable_password()


@pytest.mark.parametrize("email", ["", "   "])
@pytest.mark.django_db
def test_email_is_required(email: str) -> None:
    with pytest.raises(ValueError, match="email address"):
        User.objects.create_user(email, PASSWORD, name="X")


@pytest.mark.django_db
def test_email_is_unique_regardless_of_case() -> None:
    User.objects.create_user("dup@example.com", PASSWORD, name="One")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("DUP@Example.com", PASSWORD, name="Two")


@pytest.mark.django_db
def test_database_rejects_mixed_case_email_written_around_the_model() -> None:
    user = User.objects.create_user("lower@example.com", PASSWORD, name="L")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=user.pk).update(email="Lower@Example.com")


@pytest.mark.django_db
def test_login_by_email_in_any_case() -> None:
    User.objects.create_user("login@example.com", PASSWORD, name="L")
    assert authenticate(username="LOGIN@example.com", password=PASSWORD) is not None
    assert authenticate(username="login@example.com", password="wrong-password") is None  # noqa: S106
    assert authenticate(username="nobody@example.com", password=PASSWORD) is None


@pytest.mark.django_db
def test_inactive_user_cannot_authenticate() -> None:
    User.objects.create_user("off@example.com", PASSWORD, name="Off", is_active=False)
    assert authenticate(username="off@example.com", password=PASSWORD) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("locale", "en-us"), ("time_format", "12"), ("email", "not-an-email"), ("name", "")],
)
@pytest.mark.django_db
def test_invalid_values_fail_validation(field: str, value: str) -> None:
    user = User(email="v@example.com", name="V", locale=Locale.EN_CA)
    user.set_password(PASSWORD)
    setattr(user, field, value)
    with pytest.raises(ValidationError) as exc:
        user.full_clean()
    assert field in exc.value.message_dict


@pytest.mark.django_db
def test_create_superuser_sets_flags_and_refuses_non_staff() -> None:
    admin = User.objects.create_superuser("root@example.com", PASSWORD, name="Root")
    assert admin.is_staff and admin.is_superuser
    with pytest.raises(ValueError, match="is_staff"):
        User.objects.create_superuser("x@example.com", PASSWORD, name="X", is_staff=False)
    with pytest.raises(ValueError, match="is_superuser"):
        User.objects.create_superuser("y@example.com", PASSWORD, name="Y", is_superuser=False)


@pytest.mark.django_db
def test_createsuperuser_command_non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", PASSWORD)
    call_command(
        "createsuperuser",
        "--noinput",
        "--email=Ops@Example.com",
        "--name=Ops",
        verbosity=0,
    )
    user = User.objects.get(email="ops@example.com")
    assert user.is_superuser and user.check_password(PASSWORD)


@pytest.mark.django_db
def test_admin_user_pages_render_for_superuser() -> None:
    admin = User.objects.create_superuser("root@example.com", PASSWORD, name="Root")
    client = Client()
    client.force_login(admin)
    assert client.get("/admin/accounts/user/").status_code == 200
    assert client.get("/admin/accounts/user/add/").status_code == 200
    assert client.get(f"/admin/accounts/user/{admin.pk}/change/").status_code == 200


@pytest.mark.django_db
def test_admin_add_user_normalises_email() -> None:
    admin = User.objects.create_superuser("root@example.com", PASSWORD, name="Root")
    client = Client()
    client.force_login(admin)
    response = client.post(
        "/admin/accounts/user/add/",
        {
            "email": "New.User@Example.com",
            "name": "New User",
            "usable_password": "true",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert response.status_code == 302, response.content[:2000]
    assert User.objects.get(email="new.user@example.com").check_password(PASSWORD)
