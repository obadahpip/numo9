"""Custom user model (A-02-T01).

Created before the first migration so every later foreign key to the user (memberships, audit,
sessions, invitations) points at ``accounts.User`` from the start.

- The email address is the login identifier. It is stored lower-cased and trimmed, so it is
  unique regardless of case; a database check constraint keeps that true even for writes that
  bypass the model (``QuerySet.update``, raw SQL).
- ``name`` is a single full-name field (the 4-field sign-up form: name, email, password, path).
- ``locale`` drives UI, email and document language (en-CA / fr-CA, the project ``LANGUAGES``).
- ``time_format`` is the user's 12 h / 24 h display preference (gap-44, A-04-T12, A-10-T08).
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Locale(models.TextChoices):
    EN_CA = "en-ca", _("English (Canada)")
    FR_CA = "fr-ca", _("French (Canada)")


class TimeFormat(models.TextChoices):
    H12 = "12h", _("12-hour (1:30 p.m.)")
    H24 = "24h", _("24-hour (13:30)")


def normalise_email(email: str) -> str:
    """Trim and lower-case the whole address: one account per mailbox, whatever the casing."""
    return email.strip().lower()


def default_time_format(locale: str) -> str:
    """Default display preference for a locale: 24 h in French (Canada), 12 h in English."""
    return TimeFormat.H24 if locale == Locale.FR_CA else TimeFormat.H12


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def get_by_natural_key(self, username: str | None) -> User:
        # Login with any casing of the address finds the account.
        return self.get(email=normalise_email(username or ""))

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> User:
        if not email or not email.strip():
            raise ValueError("Users must have an email address.")
        locale = extra_fields.setdefault("locale", Locale.EN_CA)
        extra_fields.setdefault("time_format", default_time_format(locale))
        user = self.model(email=normalise_email(email), **extra_fields)
        user.set_password(password)  # None → unusable password (e.g. invited, not yet accepted)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    #: Random id used in APIs and URLs instead of the sequential primary key (A-03-T07/T09).
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(_("email address"), max_length=254, unique=True)
    name = models.CharField(_("name"), max_length=150)
    locale = models.CharField(
        _("language"), max_length=5, choices=Locale.choices, default=Locale.EN_CA
    )
    time_format = models.CharField(
        _("time format"), max_length=3, choices=TimeFormat.choices, default=TimeFormat.H12
    )
    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff status"), default=False)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects: ClassVar[UserManager] = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(email=Lower("email")),
                name="accounts_user_email_lowercase",
            ),
        ]

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        super().clean()
        self.email = normalise_email(self.email)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = normalise_email(self.email)
        super().save(*args, **kwargs)

    def get_full_name(self) -> str:
        return self.name

    def get_short_name(self) -> str:
        return self.name
