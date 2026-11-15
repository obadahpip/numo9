"""URLconf of the entitlement API tests: the project URLs plus gated test views (U-03)."""

from django.urls import path

from numo9.urls import urlpatterns as project

from . import entitlement_api as views

urlpatterns = [
    *project,
    path("api/v1/o/<uuid:org>/test/pay-runs", views.PayRuns.as_view()),
    path("api/v1/o/<uuid:org>/test/core", views.CoreSettings.as_view()),
    path("api/v1/o/<uuid:org>/test/export", views.Export.as_view()),
    path("api/v1/o/<uuid:org>/test/billing", views.Billing.as_view()),
]
