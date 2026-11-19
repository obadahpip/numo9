"""Demo visitors' accounts (U-07-T09/T11).

An anonymous visitor who opens the demo from the website gets a **limited demo user**: an
account with an unusable password and an address in the reserved ``demo.numo9.invalid`` domain
(it can't sign in again, receive mail or start a trial as itself). When its demo is purged and it
has no other organisation, the account is deleted.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from numo9.accounts.models import User
from numo9.tenancy.models import OrganisationMember, PracticeMember

DEMO_DOMAIN = "demo.numo9.invalid"


def is_demo_user(user: User) -> bool:
    return user.email.endswith("@" + DEMO_DOMAIN)


def make_demo_user() -> User:
    user = User.objects.create_user(
        email=f"visitor-{uuid.uuid4().hex[:16]}@{DEMO_DOMAIN}", password=None, name="Demo visitor"
    )
    return user


def forget_demo_users(user_ids: Iterable[int]) -> int:
    """Delete demo visitors that belong to nothing any more; the number deleted."""
    deleted = 0
    for user in User.objects.filter(pk__in=list(user_ids)):
        if not is_demo_user(user):
            continue
        if OrganisationMember.objects.filter(user=user).exists():
            continue
        if PracticeMember.objects.filter(user=user).exists():
            continue
        user.delete()
        deleted += 1
    return deleted
