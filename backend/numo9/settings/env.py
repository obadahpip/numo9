"""Helpers for reading configuration from environment variables."""

import os

from django.core.exceptions import ImproperlyConfigured

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


def env_str(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        if required:
            raise ImproperlyConfigured(f"Environment variable {name} is required.")
        if default is None:
            raise ImproperlyConfigured(
                f"Environment variable {name} is not set and has no default."
            )
        return default
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalised = value.strip().lower()
    if normalised in _TRUE:
        return True
    if normalised in _FALSE:
        return False
    raise ImproperlyConfigured(f"Environment variable {name} must be a boolean, got {value!r}.")


def env_list(name: str, default: list[str] | None = None, *, required: bool = False) -> list[str]:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        if required:
            raise ImproperlyConfigured(f"Environment variable {name} is required.")
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]
