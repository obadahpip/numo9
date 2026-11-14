"""Promo-code redemption (U-02-T06) — what checkout (U-04) calls.

``redeem(code, organisation, package)`` takes the code case-insensitively and, in one
transaction:

1. locks the promo code's row (``SELECT … FOR UPDATE``) — concurrent redemptions of the same
   code queue behind each other, so each sees the counter the previous one left;
2. refuses an unknown (404), expired, used-up, wrong-package or already-used code (409, a
   message naming the code);
3. increments ``redemptions_count`` and records the ``PromoRedemption`` (the organisation's audit
   log shows it).

So 50 simultaneous redemptions of a code with ``max_redemptions = 10`` give exactly 10. The
database backs it up: the counter can't pass the maximum (``packages_promo_max_redemptions``)
and an organisation redeems a code once (``packages_promoredemption_once_per_org``).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from numo9.audit.service import record
from numo9.i18n import errors
from numo9.i18n.errors import api_error, error_detail
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import (
    Package,
    PackageError,
    PromoCode,
    PromoRedemption,
    PromoStatus,
    normalise_promo_code,
)
from .services import field_errors


def redeem(
    code: str, organisation: Organisation, package: Package | None = None, *, actor: Any = None
) -> PromoRedemption:
    normal = normalise_promo_code(code)
    with transaction.atomic():
        promo = PromoCode.objects.select_for_update().filter(code=normal).first()
        if promo is None:
            raise api_error(errors.PROMO_NOT_FOUND)
        status = promo.status_at(timezone.now())
        if status == PromoStatus.EXPIRED:
            raise api_error(errors.PROMO_EXPIRED, code=promo.code)
        if status == PromoStatus.USED_UP:
            raise api_error(errors.PROMO_USED_UP, code=promo.code)
        restricted = list(promo.packages.values_list("pk", flat=True))
        if restricted and (package is None or package.pk not in restricted):
            raise api_error(
                errors.PROMO_NOT_FOR_PACKAGE,
                code=promo.code,
                package=package.name() if package is not None else "—",
            )
        with org_context(organisation):
            if PromoRedemption.objects.filter(promo=promo).exists():
                raise api_error(errors.PROMO_ALREADY_REDEEMED, code=promo.code)
            promo.redemptions_count += 1
            promo.save(update_fields=["redemptions_count", "updated_at"])
            redemption: PromoRedemption = PromoRedemption.objects.create(
                organisation=organisation,
                promo=promo,
                package=package,
                created_by=actor if getattr(actor, "is_authenticated", False) else None,
            )
    return redemption


def expire(promo: PromoCode, *, actor: Any = None) -> PromoCode:
    """End an active code now; redemptions already made are kept."""
    with transaction.atomic():
        locked = PromoCode.objects.select_for_update().get(pk=promo.pk)
        now = timezone.now()
        if locked.expires_at is None or locked.expires_at > now:
            locked.expires_at = now
            locked.save(update_fields=["expires_at", "updated_at"])
    return locked


# ---- console (U-02-T07) -----------------------------------------------------------------------


def _packages(codes: list[str]) -> list[Package]:
    wanted = list(dict.fromkeys(codes))
    found = {p.code: p for p in Package.objects.filter(code__in=wanted)}
    missing = [code for code in wanted if code not in found]
    if missing:
        raise serializers.ValidationError(
            {"packages": [error_detail(errors.PACKAGE_NOT_FOUND) for _code in missing]}
        )
    return [found[code] for code in wanted]


EDITABLE = ("description", "max_redemptions", "expires_at")
TERMS = ("kind", "percent_off", "amount_off_cents", "duration", "duration_months")


def create_promo(data: dict[str, Any], *, actor: Any = None) -> PromoCode:
    code = normalise_promo_code(data["code"])
    if PromoCode.objects.filter(code=code).exists():
        raise serializers.ValidationError(
            {"code": [error_detail(errors.PROMO_CODE_TAKEN, code=code)]}
        )
    packages = _packages(data.get("packages", []))
    with transaction.atomic():
        promo = PromoCode(code=code)
        for field in (*EDITABLE, *TERMS):
            if field in data:
                setattr(promo, field, data[field])
        try:
            promo.save()
        except PackageError as refused:
            raise field_errors(refused) from refused
        promo.packages.set(packages)
        if packages:
            _record_packages(promo, [], [p.code for p in packages], actor)
    return promo


def _record_packages(promo: PromoCode, before: list[str], after: list[str], actor: Any) -> None:
    """The package restriction is a many-to-many: saved apart, so recorded apart (U-02-T13)."""
    record(
        "packages.promocode.packages_changed",
        obj=promo,
        organisation=None,
        changes={"packages": [sorted(before), sorted(after)]},
        actor=actor,
    )


def update_promo(promo: PromoCode, data: dict[str, Any], *, actor: Any = None) -> PromoCode:
    """Change the description, maximum, expiry or packages (the discount terms never change:
    organisations may already have them — create a new code instead)."""
    packages = _packages(data["packages"]) if "packages" in data else None
    with transaction.atomic():
        promo = PromoCode.objects.select_for_update().get(pk=promo.pk)
        for field in EDITABLE:
            if field in data:
                setattr(promo, field, data[field])
        try:
            promo.save()
        except PackageError as refused:
            raise field_errors(refused) from refused
        if packages is not None:
            before = sorted(promo.packages.values_list("code", flat=True))
            after = sorted(p.code for p in packages)
            if before != after:
                promo.packages.set(packages)
                _record_packages(promo, before, after, actor)
    return promo
