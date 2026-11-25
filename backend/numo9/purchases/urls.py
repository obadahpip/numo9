"""Purchases routes (E-02 bills), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"
BILL = f"{ORG}bills/<uuid:public_id>"

urlpatterns = [
    path(f"{ORG}bills", api.BillListView.as_view(), name="bills"),
    path(f"{ORG}bills/check-number", api.BillNumberCheckView.as_view(), name="bill-check-number"),
    path(f"{ORG}bills/duplicates", api.BillDuplicatesView.as_view(), name="bill-duplicates"),
    path(f"{ORG}bills/from-po", api.BillFromOrderView.as_view(), name="bill-from-po"),
    path(BILL, api.BillDetailView.as_view(), name="bill"),
    path(f"{BILL}/preview", api.BillPreviewView.as_view(), name="bill-preview"),
    path(f"{BILL}/submit", api.BillSubmitView.as_view(), name="bill-submit"),
    path(f"{BILL}/approve", api.BillApproveView.as_view(), name="bill-approve"),
    path(f"{BILL}/void", api.BillVoidView.as_view(), name="bill-void"),
    path(f"{BILL}/release-holdback", api.BillReleaseHoldbackView.as_view(), name="bill-release"),
]
