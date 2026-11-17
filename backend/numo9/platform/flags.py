"""Feature flags (U-06-T12): the console's flag editor and ``/me/flags``.

A flag (``FeatureFlag``, django-waffle's model) is **on for everyone**, **off for everyone** or
**by rule** (``everyone`` null): on for the listed organisations, practices and users, and for a
stable percentage of organisations. ``active_flags(request)`` answers every flag for the request
(the organisation from the URL or ``X-Numo9-Org``, the acting practice, the user) — what the
front end reads from ``GET /api/v1/me/flags``. Each change is audited (platform event) and
flushes waffle's cache on commit, so the next ``/me/flags`` reflects it.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from numo9.audit.service import record
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.models import Organisation, Practice

from .models import FeatureFlag

NAME = re.compile(r"^[a-z][a-z0-9_.-]{1,99}$")


def _mode(flag: FeatureFlag) -> str:
    return "on" if flag.everyone is True else "off" if flag.everyone is False else "rules"


def flag_data(flag: FeatureFlag) -> dict[str, Any]:
    return {
        "name": flag.name,
        "note": flag.note,
        "mode": _mode(flag),
        "percent": str(flag.percent) if flag.percent is not None else None,
        "organisations": [
            {"id": org.public_id, "name": org.name} for org in flag.organisations.order_by("name")
        ],
        "practices": [{"id": p.public_id, "name": p.name} for p in flag.practices.order_by("name")],
        "users": [{"id": u.public_id, "name": u.name, "email": u.email} for u in flag.users.all()],
        "updated_at": flag.modified,
    }


def _percent(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise api_error(errors.FLAG_BAD_PERCENT) from None
    if (
        not number.is_finite()
        or not 0 <= number <= Decimal("99.9")
        or number != number.quantize(Decimal("0.1"))
    ):
        raise api_error(errors.FLAG_BAD_PERCENT)
    return number.quantize(Decimal("0.1"))


def _targets(model: Any, ids: Any, name: str) -> list[Any]:
    wanted = [str(value) for value in (ids or [])]
    found = {
        str(row.public_id): row for row in model.objects.filter(public_id__in=_uuids(wanted, name))
    }
    for value in wanted:
        if value not in found:
            raise api_error(errors.FLAG_UNKNOWN_TARGET, name=name, value=value[:100])
    return list(found.values())


def _uuids(values: list[str], name: str) -> list[str]:
    import uuid

    for value in values:
        try:
            uuid.UUID(value)
        except ValueError:
            raise api_error(errors.FLAG_UNKNOWN_TARGET, name=name, value=value[:100]) from None
    return values


def _snapshot(flag: FeatureFlag) -> dict[str, Any]:
    data = flag_data(flag)
    return {
        "mode": data["mode"],
        "percent": data["percent"],
        "note": data["note"],
        "organisations": sorted(str(o["id"]) for o in data["organisations"]),
        "practices": sorted(str(p["id"]) for p in data["practices"]),
    }


def _audit(action: str, flag: FeatureFlag, before: dict[str, Any], actor: Any) -> None:
    after = _snapshot(flag) if action != "platform.flag.deleted" else {}
    changes = {
        key: [before.get(key), after.get(key)]
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    }
    record(
        action,
        organisation=None,
        object_type="platform.FeatureFlag",
        object_id=flag.name,
        object_label=flag.name,
        changes=changes,
        actor=actor,
    )


def create(name: str, note: str = "", *, actor: Any = None) -> FeatureFlag:
    name = (name or "").strip()
    if not NAME.match(name):
        raise api_error(errors.FLAG_BAD_NAME)
    with transaction.atomic():
        if FeatureFlag.objects.filter(name=name).exists():
            raise api_error(errors.FLAG_EXISTS, name=name)
        flag = FeatureFlag.objects.create(name=name, note=note or "", everyone=False)
        _audit("platform.flag.created", flag, {}, actor)
    return flag


def update(flag: FeatureFlag, data: dict[str, Any], *, actor: Any = None) -> FeatureFlag:
    before = _snapshot(flag)
    with transaction.atomic():
        if "mode" in data:
            flag.everyone = {"on": True, "off": False, "rules": None}[data["mode"]]
        if "percent" in data:
            flag.percent = _percent(data["percent"])
        if "note" in data:
            flag.note = data["note"] or ""
        flag.save()
        if "organisations" in data:
            flag.organisations.set(_targets(Organisation, data["organisations"], "organisation"))
        if "practices" in data:
            flag.practices.set(_targets(Practice, data["practices"], "practice"))
        _audit("platform.flag.updated", flag, before, actor)
        transaction.on_commit(flag.flush)
    return flag


def delete(flag: FeatureFlag, *, actor: Any = None) -> None:
    before = _snapshot(flag)
    with transaction.atomic():
        _audit("platform.flag.deleted", flag, before, actor)
        flag.delete()


def active_flags(request: Any) -> dict[str, bool]:
    """Every flag, on or off for this request (unknown names are simply absent: off)."""
    return {flag.name: bool(flag.is_active(request)) for flag in FeatureFlag.get_all()}
