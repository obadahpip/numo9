"""PromoCode + redeem() (U-02-T06): percent or fixed, duration, max redemptions, expiry, package
restriction; the counter is incremented under ``SELECT … FOR UPDATE``. Acceptance: 50 concurrent
redemptions of a code with max = 10 → exactly 10."""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, connections, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from numo9.audit.models import AuditEvent
from numo9.catalogue.models import Product
from numo9.packages.models import (
    Package,
    PackageError,
    PackageProduct,
    PromoCode,
    PromoDuration,
    PromoKind,
    PromoRedemption,
    PromoStatus,
)
from numo9.packages.promos import expire, redeem
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def promo(code: str = "LAUNCH20", **fields: object) -> PromoCode:
    values: dict[str, object] = {
        "kind": PromoKind.PERCENT,
        "percent_off": 20,
        "duration": PromoDuration.ONCE,
    }
    values.update(fields)
    return PromoCode.objects.create(code=code, **values)


def org(name: str = "Maple Leaf Supply Ltd.") -> Organisation:
    return Organisation.objects.create(name=name)


def package(code: str = "growth") -> Package:
    created = Package.objects.create(code=code, name_i18n={"en-CA": code.title()})
    PackageProduct.objects.create(package=created, product=Product.objects.get(code="accounting"))
    return created


def code_of(error: pytest.ExceptionInfo[APIException]) -> str:
    return str(error.value.get_codes())


# ---- acceptance: concurrency ------------------------------------------------------------------

THREADS = 50
MAX = 10


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(connection.vendor != "postgresql", reason="row locks need PostgreSQL")
def test_50_concurrent_redemptions_on_max_10_give_exactly_10() -> None:
    code = promo("LAST10", max_redemptions=MAX)
    organisations = [org(f"Shop {i:02d} Ltd.") for i in range(THREADS)]
    won: list[str] = []
    refused: list[str] = []
    unexpected: list[BaseException] = []
    lock = threading.Lock()
    start = threading.Barrier(THREADS)

    def worker(organisation: Organisation) -> None:
        try:
            start.wait()
            redeem("last10", organisation)
            with lock:
                won.append(organisation.name)
        except APIException as error:
            with lock:
                refused.append(str(error.get_codes()))
        except BaseException as error:  # reported below
            unexpected.append(error)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(o,)) for o in organisations]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert unexpected == []
    assert len(won) == MAX
    assert refused == ["packages.promo_used_up"] * (THREADS - MAX)
    code.refresh_from_db()
    assert code.redemptions_count == MAX
    assert code.status_at(timezone.now()) == PromoStatus.USED_UP
    redeemed = PromoRedemption.objects.unscoped(reason="test: count across organisations")
    assert redeemed.filter(promo=code).count() == MAX


# ---- redeem -----------------------------------------------------------------------------------


def test_redeem_is_case_insensitive_and_counts() -> None:
    code = promo()
    organisation = org()
    redemption = redeem("  launch20 ", organisation)
    code.refresh_from_db()
    assert code.redemptions_count == 1
    assert redemption.promo == code and redemption.organisation == organisation
    with org_context(organisation):
        assert list(PromoRedemption.objects.all()) == [redemption]


def test_unknown_code() -> None:
    with pytest.raises(APIException) as refused:
        redeem("NOPE", org())
    assert code_of(refused) == "packages.promo_not_found"
    assert refused.value.status_code == 404


def test_expired_code_is_refused() -> None:
    promo(expires_at=timezone.now() - timedelta(minutes=1))
    with pytest.raises(APIException) as refused:
        redeem("LAUNCH20", org())
    assert code_of(refused) == "packages.promo_expired"
    assert "LAUNCH20" in str(refused.value.detail)


def test_an_organisation_redeems_a_code_once() -> None:
    code = promo()
    organisation = org()
    redeem("LAUNCH20", organisation)
    with pytest.raises(APIException) as refused:
        redeem("LAUNCH20", organisation)
    assert code_of(refused) == "packages.promo_already_redeemed"
    code.refresh_from_db()
    assert code.redemptions_count == 1
    with pytest.raises(IntegrityError), transaction.atomic(), org_context(organisation):
        PromoRedemption.objects.create(organisation=organisation, promo=code)


def test_package_restriction() -> None:
    growth, complete = package("growth"), package("complete")
    code = promo()
    code.packages.add(complete)
    with pytest.raises(APIException) as refused:
        redeem("LAUNCH20", org("A Ltd."), growth)
    assert code_of(refused) == "packages.promo_not_for_package"
    assert "Growth" in str(refused.value.detail)
    with pytest.raises(APIException):
        redeem("LAUNCH20", org("B Ltd."))  # restricted: a package is needed
    assert redeem("LAUNCH20", org("C Ltd."), complete).package == complete
    promo("OPEN10")  # no restriction: any package
    assert redeem("OPEN10", org("D Ltd."), growth).package == growth


def test_used_up_code() -> None:
    promo(max_redemptions=1)
    redeem("LAUNCH20", org("A Ltd."))
    with pytest.raises(APIException) as refused:
        redeem("LAUNCH20", org("B Ltd."))
    assert code_of(refused) == "packages.promo_used_up"


def test_redemption_is_in_the_organisation_audit_log() -> None:
    promo()
    organisation = org()
    redeem("LAUNCH20", organisation)
    event = AuditEvent.platform_events.get(action="packages.promoredemption.created")
    assert event.organisation == organisation
    assert event.object_label == "LAUNCH20"
    # the counter is not a history line of the promo code
    assert not AuditEvent.platform_events.filter(action="packages.promocode.updated").exists()


def test_expire_ends_the_code_and_keeps_redemptions() -> None:
    code = promo()
    redeem("LAUNCH20", org())
    expired = expire(code)
    assert expired.status_at(timezone.now()) == PromoStatus.EXPIRED
    assert expired.redemptions_count == 1
    when = expired.expires_at
    assert expire(expired).expires_at == when  # already expired: unchanged


# ---- model rules ------------------------------------------------------------------------------


def test_code_stored_upper_case_unique_and_immutable() -> None:
    code = promo("launch-20")
    assert code.code == "LAUNCH-20"
    with pytest.raises(IntegrityError), transaction.atomic():
        promo("Launch-20")
    code.code = "OTHER"
    with pytest.raises(PackageError):
        code.save()


@pytest.mark.parametrize(
    ("fields", "field", "error"),
    [
        ({"code": "AB"}, "code", "packages.bad_promo_code"),
        ({"code": "BAD CODE"}, "code", "packages.bad_promo_code"),
        ({"percent_off": 0}, "percent_off", "packages.promo_percent"),
        ({"percent_off": 101}, "percent_off", "packages.promo_percent"),
        (
            {"kind": PromoKind.FIXED, "percent_off": None},
            "amount_off_cents",
            "packages.promo_amount",
        ),
        ({"duration": PromoDuration.REPEATING}, "duration_months", "packages.promo_months"),
        (
            {"duration": PromoDuration.REPEATING, "duration_months": 37},
            "duration_months",
            "packages.promo_months",
        ),
        ({"max_redemptions": 0}, "max_redemptions", "packages.promo_max"),
        ({"currency": "USD"}, "currency", "packages.currency_cad"),
        ({"kind": "bogo"}, "kind", "packages.promo_kind"),
    ],
)
def test_invalid_promo_codes_are_refused(fields: dict[str, object], field: str, error: str) -> None:
    values: dict[str, object] = {"code": "LAUNCH20"}
    values.update(fields)
    code = values.pop("code")
    with pytest.raises(PackageError) as refused:
        promo(str(code), **values)
    assert refused.value.error_dict[field][0].code == error


def test_fixed_amount_and_months() -> None:
    code = promo(
        "ACCT50",
        kind=PromoKind.FIXED,
        percent_off=None,
        amount_off_cents=5000,
        duration=PromoDuration.REPEATING,
        duration_months=3,
    )
    assert (code.amount_off_cents, code.percent_off, code.duration_months) == (5000, None, 3)
    assert code.currency == "CAD"


def test_database_refuses_a_counter_above_the_maximum() -> None:
    code = promo(max_redemptions=2)
    with pytest.raises(IntegrityError), transaction.atomic():
        PromoCode.objects.filter(pk=code.pk).update(redemptions_count=3)


def test_status() -> None:
    now = timezone.now()
    code = promo(max_redemptions=2)
    assert code.status_at(now) == PromoStatus.ACTIVE
    code.redemptions_count = 2
    assert code.status_at(now) == PromoStatus.USED_UP
    code.expires_at = now
    assert code.status_at(now) == PromoStatus.EXPIRED
