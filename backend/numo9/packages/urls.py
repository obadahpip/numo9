"""Packages routes (U-02-T07, T08), under /api/v1/."""

from django.urls import path

from . import api, public

PLATFORM = "platform/packages"

urlpatterns = [
    # Public pricing (U-02-T08): anyone, cached 60 s.
    path("public/pricing", public.PublicPricingView.as_view(), name="public-pricing"),
    path(PLATFORM, api.PackageListView.as_view(), name="platform-packages"),
    # promo codes before <code>: "promo-codes" is not a package code (no hyphens in codes)
    path(f"{PLATFORM}/promo-codes", api.PromoListView.as_view(), name="platform-promo-codes"),
    path(
        f"{PLATFORM}/promo-codes/<str:code>",
        api.PromoDetailView.as_view(),
        name="platform-promo-code",
    ),
    path(
        f"{PLATFORM}/promo-codes/<str:code>/expire",
        api.PromoExpireView.as_view(),
        name="platform-promo-code-expire",
    ),
    path(f"{PLATFORM}/<str:code>", api.PackageDetailView.as_view(), name="platform-package"),
    path(
        f"{PLATFORM}/<str:code>/activate",
        api.PackageActivateView.as_view(),
        name="platform-package-activate",
    ),
    path(
        f"{PLATFORM}/<str:code>/retire",
        api.PackageRetireView.as_view(),
        name="platform-package-retire",
    ),
    path(
        f"{PLATFORM}/<str:code>/prices", api.PriceListView.as_view(), name="platform-package-prices"
    ),
    path(
        f"{PLATFORM}/<str:code>/prices/impact",
        api.PriceImpactView.as_view(),
        name="platform-package-price-impact",
    ),
    path(
        f"{PLATFORM}/<str:code>/prices/<uuid:price_id>",
        api.PriceDetailView.as_view(),
        name="platform-package-price",
    ),
]
