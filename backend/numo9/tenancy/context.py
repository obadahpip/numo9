"""Tenant request context (A-01-T03).

The active organisation and the acting practice live in ``contextvars`` so that code deep in
the stack (managers, services, audit) can read them without passing the request around, and so
that concurrent requests, threads and async tasks never see each other's values.

- ``current_org()`` / ``acting_practice()`` read the context (``None`` when not set).
- ``org_context(org, practice)`` sets it for a block and always restores the previous values;
  the middleware uses it per request, background jobs will use it per task (A-01-T07).

This module only *identifies* the tenant. Whether the user may access it is decided by the
access resolver and the API permission (A-01-T05, A-01-T06).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # runtime import would be circular (models → managers → context)
    from .models import Organisation, Practice


class TenantContextMissing(RuntimeError):
    """An organisation-scoped query ran with no active organisation (A-01-T04)."""


_current_org: ContextVar[Organisation | None] = ContextVar("numo9_current_org", default=None)
_acting_practice: ContextVar[Practice | None] = ContextVar("numo9_acting_practice", default=None)


def current_org() -> Organisation | None:
    """The organisation the current request or job works in, if any."""
    return _current_org.get()


def acting_practice() -> Practice | None:
    """The practice the current user acts through in the active organisation, if any."""
    return _acting_practice.get()


@contextmanager
def org_context(
    organisation: Organisation | None, practice: Practice | None = None
) -> Iterator[None]:
    """Run a block with the given tenant context, then restore whatever was there before."""
    org_token = _current_org.set(organisation)
    practice_token = _acting_practice.set(practice)
    try:
        yield
    finally:
        _acting_practice.reset(practice_token)
        _current_org.reset(org_token)
