"""``EncryptedField`` (S-03-T04): a text column whose value is stored envelope-encrypted.

    class Employee(OrgOwnedModel):
        sin = EncryptedField(max_length=9, blank=True)        # SIN (M-01)
        bank_account = EncryptedField(max_length=20, blank=True)

- Python sees the plain value; the database only holds ``n9e1:<key id>:…`` (unreadable without
  the key ring, which never reaches the database).
- ``max_length`` limits the *plain* value; the column itself is unbounded text.
- Only ``isnull`` lookups are allowed — filtering or ordering by an encrypted value is meaningless
  (every encryption is randomised), so other lookups raise ``FieldError``.
- ``manage.py rotate_field_encryption`` re-wraps every value under the active key.
"""

from __future__ import annotations

from typing import Any

from django.core import checks
from django.core.exceptions import FieldError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models.expressions import Expression
from django.db.models.lookups import IsNull

from . import crypto


class EncryptedField(models.TextField):  # type: ignore[type-arg]
    description = "Text stored envelope-encrypted (AES-256-GCM)"

    def __init__(self, *args: Any, max_length: int | None = None, **kwargs: Any) -> None:
        self.plain_max_length = max_length
        if kwargs.get("db_index") or kwargs.get("unique") or kwargs.get("primary_key"):
            raise ValueError("EncryptedField values cannot be indexed, unique or a primary key.")
        super().__init__(*args, **kwargs)
        if max_length is not None:
            self.validators.append(MaxLengthValidator(max_length))

    def deconstruct(self) -> Any:
        name, path, args, kwargs = super().deconstruct()
        if self.plain_max_length is not None:
            kwargs["max_length"] = self.plain_max_length
        return name, path, args, kwargs

    def check(self, **kwargs: Any) -> list[checks.CheckMessage]:
        problems = super().check(**kwargs)
        if self.default is not models.NOT_PROVIDED and self.default not in ("", None):
            problems.append(
                checks.Error(
                    "EncryptedField may not have a non-empty default (it would be stored in "
                    "migrations in plain text).",
                    obj=self,
                    id="security.E101",
                )
            )
        return problems

    @property
    def context(self) -> str:
        return f"{self.model._meta.label}.{self.name}"

    # Database ↔ Python ------------------------------------------------------------------------
    def from_db_value(
        self, value: str | None, expression: Expression, connection: BaseDatabaseWrapper
    ) -> str | None:
        if value is None or value == "":
            return value
        return crypto.decrypt(value, self.context)

    def to_python(self, value: Any) -> Any:
        return value

    def get_prep_value(self, value: Any) -> Any:
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value  # NULL and blank stay as they are (nothing to protect)
        if isinstance(value, crypto.Ciphertext):
            return str(value)  # already encrypted (written by the rotation command)
        return str(crypto.encrypt(str(value), self.context))

    def get_lookup(self, lookup_name: str) -> Any:
        if lookup_name == "isnull":
            return IsNull
        raise FieldError(
            f"{self.context} is encrypted; only 'isnull' lookups are possible, not '{lookup_name}'."
        )
