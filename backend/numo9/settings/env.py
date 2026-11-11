"""Helpers for reading configuration from environment variables."""

import os
from urllib.parse import urlsplit, urlunsplit

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


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be an integer, got {value!r}."
        ) from None


def redis_database(url: str, database: int) -> str:
    """``redis://host:6379/0`` → ``redis://host:6379/<database>`` (query string kept)."""
    parts = urlsplit(url)
    if parts.scheme not in ("redis", "rediss"):
        raise ImproperlyConfigured(f"Expected a redis:// or rediss:// URL, got {parts.scheme!r}.")
    return urlunsplit(parts._replace(path=f"/{database}"))
