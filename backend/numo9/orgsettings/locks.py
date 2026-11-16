"""Lock service (A-05-T05): may this person change something dated ``date`` in this module?

``check_lock(organisation, module, date, user) -> LockViolation | None`` and
``assert_not_locked(...)``, which raises ``LockedPeriod`` (HTTP 409, code ``lock.violation``)
whose message names the lock — "The Sales and accounts receivable lock date is 2026-03-31
(everyone): changes dated on or before it are refused." — and carries the ``LockViolation``
(module, level, date).

Rules (docs/architecture/organisation-settings.md § Lock dates):

- a change dated **on or before** a lock date is refused, comparing **organisation-local dates**
  (a date-time is first converted to the organisation's time zone);
- the ``everyone`` level stops everybody; the ``advisers_only`` level stops everybody except
  **advisers** — staff of a practice actively assigned to the organisation, with access to it,
  in an accountant role (practice admin, accountant, reviewer, payroll specialist; not read-only
  staff). System changes (no user) are stopped like everyone;
- a module's own lock **and** the general ledger lock apply (whatever posts to the ledger respects
  the GL lock): an AR invoice dated 2026-03-15 is refused by an AR lock of 2026-03-31 or by a GL
  lock of 2026-03-31. When both stop it, the module's own lock is named.

Every check reads the database (no caching): a lock set a moment ago applies at once.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.exceptions import APIException

from numo9.tenancy.access import can_access
from numo9.tenancy.models import Organisation, PracticeMember, PracticeRole

from .models import LockDate, LockLevel, LockModule

ADVISER_ROLES: frozenset[str] = frozenset(
    {
        PracticeRole.PRACTICE_ADMIN,
        PracticeRole.ACCOUNTANT,
        PracticeRole.REVIEWER,
        PracticeRole.PAYROLL_SPECIALIST,
    }
)


@dataclass(frozen=True)
class LockViolation:
    module: str
    level: str
    date: dt.date

    def message(self) -> str:
        return _(
            "The %(module)s lock date is %(date)s (%(level)s): changes dated on or before it are "
            "refused. Date it after %(date)s, or ask someone who manages lock dates."
        ) % {
            "module": LockModule(self.module).label,
            "date": self.date.isoformat(),
            "level": str(LockLevel(self.level).label).lower(),
        }

    def as_dict(self) -> dict[str, str]:
        return {"module": self.module, "level": self.level, "date": self.date.isoformat()}


class LockedPeriod(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "lock.violation"

    def __init__(self, violation: LockViolation) -> None:
        self.violation = violation
        super().__init__(
            detail={
                "detail": violation.message(),
                "code": "lock.violation",
                "lock": violation.as_dict(),
            }
        )


def local_date(organisation: Organisation, value: dt.date | dt.datetime) -> dt.date:
    """The organisation-local calendar date of ``value``."""
    if isinstance(value, dt.datetime):
        aware = value if timezone.is_aware(value) else timezone.make_aware(value)
        return aware.astimezone(ZoneInfo(organisation.time_zone)).date()
    return value


def is_adviser(user: Any, organisation: Organisation) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    adviser = PracticeMember.objects.filter(
        user=user,
        role__in=ADVISER_ROLES,
        practice__assignments__organisation=organisation,
        practice__assignments__active=True,
    ).exists()
    return adviser and can_access(user, organisation)


def check_lock(
    organisation: Organisation, module: str, date: dt.date | dt.datetime, user: Any = None
) -> LockViolation | None:
    """The lock that refuses the change, or None."""
    if module not in LockModule.values:
        raise ValueError(f"Unknown lock module {module!r}")
    day = local_date(organisation, date)
    modules = [module] if module == LockModule.GL else [module, LockModule.GL]
    levels = [LockLevel.EVERYONE]
    if not is_adviser(user, organisation):
        levels.append(LockLevel.ADVISERS_ONLY)
    locks = LockDate._base_manager.filter(
        organisation=organisation,
        module__in=modules,
        level__in=levels,
        deleted_at__isnull=True,
        date__isnull=False,
        date__gte=day,
    )
    found = sorted(
        locks, key=lambda lock: (modules.index(lock.module), lock.level != LockLevel.EVERYONE)
    )
    if not found:
        return None
    lock = found[0]
    return LockViolation(lock.module, lock.level, lock.date or day)


def assert_not_locked(
    organisation: Organisation, module: str, date: dt.date | dt.datetime, user: Any = None
) -> None:
    violation = check_lock(organisation, module, date, user)
    if violation is not None:
        raise LockedPeriod(violation)
