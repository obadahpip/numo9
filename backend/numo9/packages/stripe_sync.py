"""Stripe Product/Price sync of package prices (U-02-T12) — a stub until U-04 bills with it.

Stripe prices are **immutable**: an amount, currency or interval never changes once created. So
every ``PackagePrice`` version gets its own Stripe Price, created once and never modified; a
price change is a new version, hence a new Stripe Price, and the old one stays as it was (its
subscriptions keep it until they renew — U-04 moves them, using ``price_for`` at renewal).

``sync_stripe_prices`` (platform job, ``io`` queue, started by ``request_sync`` after a price is
scheduled or a package activated) walks the packages that are sold (active or retired; drafts
have never been sold):

1. a package without ``stripe_product_id`` gets a Stripe Product (id ``numo9_pkg_<code>``,
   metadata with the package code) — its id is stored on the package;
2. each price version without ``stripe_price_id`` gets a Stripe Price (CAD, ``unit_amount`` in
   cents, monthly or yearly recurring, ``tax_behavior=exclusive``, metadata with the version's
   public id and start date) — its id is stored once on the version.

Each Stripe call carries an idempotency key from the row's public id, so a retried job never
creates a duplicate; ids are stored step by step (``atomic=False``), so a job that stops half-way
continues where it stopped. Nothing ever calls Stripe's update endpoints.

The gateway: ``settings.NUMO9_STRIPE_GATEWAY`` (a class, for tests), else the Stripe API when
``STRIPE_SECRET_KEY`` is set (``STRIPE_API_BASE`` → stripe-mock in tests), else **off**: no job is
started and the job itself does nothing (``{"skipped": true}``).
"""

from __future__ import annotations

from typing import Any, Protocol

from django.conf import settings
from django.utils.module_loading import import_string

from numo9.jobs.queues import IO
from numo9.jobs.runtime import platform_job, start_job

from .models import Package, PackagePrice, PackageStatus

PRODUCT_ID = "numo9_pkg_{code}"


class StripeGateway(Protocol):
    def create_product(self, package: Package) -> str:
        """Create the package's Stripe Product; return its id."""
        ...

    def create_price(self, price: PackagePrice, product_id: str) -> str:
        """Create a Stripe Price for one price version; return its id."""
        ...


class StripeApi:
    """The Stripe API through the official client (``stripe`` package)."""

    def __init__(self) -> None:
        import stripe

        options: dict[str, Any] = {}
        if settings.STRIPE_API_BASE:
            options["base_addresses"] = {"api": settings.STRIPE_API_BASE}
        self.client = stripe.StripeClient(settings.STRIPE_SECRET_KEY, **options)

    def create_product(self, package: Package) -> str:
        product = self.client.v1.products.create(
            params={
                "id": PRODUCT_ID.format(code=package.code),
                "name": package.name(),
                "metadata": {"numo9_package": package.code},
            },
            options={"idempotency_key": f"numo9-product-{package.public_id}"},
        )
        return str(product.id)

    def create_price(self, price: PackagePrice, product_id: str) -> str:
        created = self.client.v1.prices.create(
            params={
                "product": product_id,
                "currency": price.currency.lower(),
                "unit_amount": price.amount_cents,
                "recurring": {"interval": price.interval},
                "tax_behavior": "exclusive",
                "metadata": {
                    "numo9_price": str(price.public_id),
                    "numo9_package": price.package.code,
                    "effective_from": price.effective_from.isoformat(),
                },
            },
            options={"idempotency_key": f"numo9-price-{price.public_id}"},
        )
        return str(created.id)


def get_gateway() -> StripeGateway | None:
    """The configured gateway, or None when Stripe sync is off."""
    path = getattr(settings, "NUMO9_STRIPE_GATEWAY", "")
    if path:
        gateway: StripeGateway = import_string(path)()
        return gateway
    if getattr(settings, "STRIPE_SECRET_KEY", ""):
        return StripeApi()
    return None


def sync_enabled() -> bool:
    return bool(getattr(settings, "NUMO9_STRIPE_GATEWAY", "")) or bool(
        getattr(settings, "STRIPE_SECRET_KEY", "")
    )


def sync(gateway: StripeGateway) -> dict[str, int]:
    """Create the missing Stripe Products and Prices; never touch existing ones."""
    products = prices = 0
    sold = Package.objects.filter(status__in=(PackageStatus.ACTIVE, PackageStatus.RETIRED))
    for package in sold.order_by("sort", "code"):
        missing = list(
            PackagePrice.objects.filter(package=package, stripe_price_id="").order_by(
                "interval", "effective_from"
            )
        )
        if not missing and package.stripe_product_id:
            continue
        if not package.stripe_product_id:
            package.stripe_product_id = gateway.create_product(package)
            Package.objects.filter(pk=package.pk).update(
                stripe_product_id=package.stripe_product_id
            )
            products += 1
        for price in missing:
            price.package = package
            price.stripe_price_id = gateway.create_price(price, package.stripe_product_id)
            price.save(update_fields=["stripe_price_id", "updated_at"])
            prices += 1
    return {"products_created": products, "prices_created": prices}


@platform_job(name="numo9.packages.sync_stripe_prices", queue=IO, atomic=False)
def sync_stripe_prices() -> dict[str, Any]:
    gateway = get_gateway()
    if gateway is None:
        return {"skipped": True, "products_created": 0, "prices_created": 0}
    return {"skipped": False, **sync(gateway)}


def request_sync(*, key: str | None = None, actor: Any = None) -> None:
    """Start the sync job (sent once the current transaction commits); no-op while sync is off."""
    if sync_enabled():
        start_job(sync_stripe_prices, key=key, created_by=_user(actor))


def _user(actor: Any) -> Any:
    return actor if getattr(actor, "is_authenticated", False) else None
