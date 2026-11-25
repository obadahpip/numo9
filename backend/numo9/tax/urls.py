"""Tax engine routes (G-01-T11) and filing cycles (G-03a-T16), under /api/v1/."""

from django.urls import path

from . import api, filing_api

ORG = "o/<uuid:org>/"
REG = f"{ORG}tax/registrations/<uuid:public_id>/"

urlpatterns = [
    path(f"{ORG}tax/components", api.TaxComponentListView.as_view(), name="tax-components"),
    path(
        f"{ORG}tax/components/<uuid:public_id>",
        api.TaxComponentDetailView.as_view(),
        name="tax-component",
    ),
    path(f"{ORG}tax/codes", api.TaxCodeListView.as_view(), name="tax-codes"),
    path(f"{ORG}tax/numbers/check", api.TaxNumberCheckView.as_view(), name="tax-number-check"),
    path(f"{ORG}tax/codes/<uuid:public_id>", api.TaxCodeDetailView.as_view(), name="tax-code"),
    path(
        f"{ORG}tax/codes/<uuid:public_id>/versions",
        api.TaxCodeVersionView.as_view(),
        name="tax-code-versions",
    ),
    path(
        f"{ORG}tax/codes/<uuid:public_id>/archive",
        api.TaxCodeArchiveView.as_view(),
        name="tax-code-archive",
    ),
    path(
        f"{ORG}tax/codes/<uuid:public_id>/restore",
        api.TaxCodeRestoreView.as_view(),
        name="tax-code-restore",
    ),
    path(f"{ORG}tax/calculate", api.TaxCalculateView.as_view(), name="tax-calculate"),
    path(f"{REG}cycles", filing_api.FilingCycleListView.as_view(), name="tax-filing-cycles"),
    path(f"{REG}periods", filing_api.FilingPeriodListView.as_view(), name="tax-filing-periods"),
    path(
        f"{REG}custom-periods",
        filing_api.FilingCustomPeriodListView.as_view(),
        name="tax-filing-custom-periods",
    ),
    path(
        f"{REG}custom-periods/<uuid:period_id>",
        filing_api.FilingCustomPeriodDetailView.as_view(),
        name="tax-filing-custom-period",
    ),
    path(f"{REG}preview", filing_api.FilingPreviewView.as_view(), name="tax-filing-preview"),
]
