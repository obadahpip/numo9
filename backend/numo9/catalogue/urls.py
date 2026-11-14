"""Product catalogue routes (U-01-T09, T10), under /api/v1/."""

from django.urls import path

from . import api

urlpatterns = [
    path("catalogue/products", api.ProductListView.as_view(), name="catalogue-products"),
    path(
        "catalogue/feature-matrix", api.FeatureMatrixView.as_view(), name="catalogue-feature-matrix"
    ),
    path(
        "o/<uuid:org>/package-features",
        api.OrganisationMatrixView.as_view(),
        name="organisation-package-features",
    ),
    path(
        "platform/catalogue/products",
        api.PlatformProductListView.as_view(),
        name="platform-catalogue-products",
    ),
    path(
        "platform/catalogue/feature-matrix/export/<str:kind>",
        api.FeatureMatrixExportView.as_view(),
        name="platform-catalogue-feature-matrix-export",
    ),
]
