"""Purchases routes (E-01 purchase orders and receipts, E-02 bills and the purchases overview,
E-04 expense claims), under /api/v1/."""

from django.urls import path

from . import api, expense_api, po_api

ORG = "o/<uuid:org>/"
PO = f"{ORG}purchase-orders/<uuid:public_id>"
GRN = f"{ORG}receipts/<uuid:public_id>"
BILL = f"{ORG}bills/<uuid:public_id>"
CLAIMS = f"{ORG}expense-claims"
CLAIM = f"{CLAIMS}/<uuid:public_id>"

urlpatterns = [
    path(f"{ORG}purchase-orders", po_api.PurchaseOrderListView.as_view(), name="purchase-orders"),
    path(
        f"{ORG}purchase-orders/approval-limit",
        po_api.ApprovalLimitView.as_view(),
        name="purchase-order-approval-limit",
    ),
    path(PO, po_api.PurchaseOrderDetailView.as_view(), name="purchase-order"),
    path(f"{PO}/submit", po_api.PurchaseOrderSubmitView.as_view(), name="purchase-order-submit"),
    path(f"{PO}/approve", po_api.PurchaseOrderApproveView.as_view(), name="purchase-order-approve"),
    path(f"{PO}/cancel", po_api.PurchaseOrderCancelView.as_view(), name="purchase-order-cancel"),
    path(f"{PO}/close", po_api.PurchaseOrderCloseView.as_view(), name="purchase-order-close"),
    path(f"{PO}/match", po_api.PurchaseOrderMatchView.as_view(), name="purchase-order-match"),
    path(f"{PO}/pdf", po_api.PurchaseOrderPdfView.as_view(), name="purchase-order-pdf"),
    path(f"{PO}/send", po_api.PurchaseOrderSendView.as_view(), name="purchase-order-send"),
    path(f"{ORG}receipts", po_api.ReceiptListView.as_view(), name="receipts"),
    path(GRN, po_api.ReceiptDetailView.as_view(), name="receipt"),
    path(f"{GRN}/reverse", po_api.ReceiptReverseView.as_view(), name="receipt-reverse"),
    path(f"{ORG}reports/commitments", po_api.CommitmentReportView.as_view(), name="commitments"),
    path(f"{ORG}bills", api.BillListView.as_view(), name="bills"),
    path(f"{ORG}bills/overview", api.BillOverviewView.as_view(), name="bills-overview"),
    path(f"{ORG}bills/check-number", api.BillNumberCheckView.as_view(), name="bill-check-number"),
    path(f"{ORG}bills/duplicates", api.BillDuplicatesView.as_view(), name="bill-duplicates"),
    path(f"{ORG}bills/from-po", api.BillFromOrderView.as_view(), name="bill-from-po"),
    path(BILL, api.BillDetailView.as_view(), name="bill"),
    path(f"{BILL}/preview", api.BillPreviewView.as_view(), name="bill-preview"),
    path(f"{BILL}/submit", api.BillSubmitView.as_view(), name="bill-submit"),
    path(f"{BILL}/approve", api.BillApproveView.as_view(), name="bill-approve"),
    path(f"{BILL}/void", api.BillVoidView.as_view(), name="bill-void"),
    path(f"{BILL}/release-holdback", api.BillReleaseHoldbackView.as_view(), name="bill-release"),
    path(CLAIMS, expense_api.ExpenseClaimListView.as_view(), name="expense-claims"),
    path(
        f"{CLAIMS}/categories",
        expense_api.ExpenseCategoriesView.as_view(),
        name="expense-categories",
    ),
    path(
        f"{CLAIMS}/mileage-rate", expense_api.MileageRateView.as_view(), name="expense-mileage-rate"
    ),
    path(f"{CLAIMS}/receipts", expense_api.ReceiptUploadView.as_view(), name="expense-receipts"),
    path(
        f"{CLAIMS}/receipts/<uuid:public_id>/finalize",
        expense_api.ReceiptFinalizeView.as_view(),
        name="expense-receipt-finalize",
    ),
    path(CLAIM, expense_api.ExpenseClaimDetailView.as_view(), name="expense-claim"),
    path(f"{CLAIM}/submit", expense_api.ExpenseClaimSubmitView.as_view(), name="expense-submit"),
    path(f"{CLAIM}/approve", expense_api.ExpenseClaimApproveView.as_view(), name="expense-approve"),
    path(f"{CLAIM}/reject", expense_api.ExpenseClaimRejectView.as_view(), name="expense-reject"),
]
