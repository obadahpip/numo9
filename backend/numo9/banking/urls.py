"""Banking routes (F-01-T07; statement imports F-02-T11), under /api/v1/."""

from django.urls import path

from . import api, imports_api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}bank-accounts", api.BankAccountListView.as_view(), name="bank-accounts"),
    path(
        f"{ORG}bank-accounts/<uuid:public_id>",
        api.BankAccountDetailView.as_view(),
        name="bank-account",
    ),
    path(
        f"{ORG}bank-accounts/<uuid:public_id>/archive",
        api.BankAccountArchiveView.as_view(),
        name="bank-account-archive",
    ),
    path(
        f"{ORG}bank-accounts/<uuid:public_id>/restore",
        api.BankAccountRestoreView.as_view(),
        name="bank-account-restore",
    ),
    path(
        f"{ORG}bank-accounts/<uuid:public_id>/register",
        api.BankAccountRegisterView.as_view(),
        name="bank-account-register",
    ),
    path(
        f"{ORG}bank-accounts/<uuid:public_id>/imports",
        imports_api.StatementImportListView.as_view(),
        name="bank-account-imports",
    ),
    path(
        f"{ORG}bank-accounts/<uuid:account_public_id>/imports/<uuid:public_id>",
        imports_api.StatementImportDetailView.as_view(),
        name="bank-account-import",
    ),
    path(
        f"{ORG}bank-accounts/<uuid:account_public_id>/imports/<uuid:public_id>/preview",
        imports_api.StatementImportPreviewView.as_view(),
        name="bank-account-import-preview",
    ),
    path(
        f"{ORG}bank-accounts/<uuid:account_public_id>/imports/<uuid:public_id>/commit",
        imports_api.StatementImportCommitView.as_view(),
        name="bank-account-import-commit",
    ),
    path(
        f"{ORG}bank-accounts/<uuid:account_public_id>/imports/<uuid:public_id>/undo",
        imports_api.StatementImportUndoView.as_view(),
        name="bank-account-import-undo",
    ),
    path(
        f"{ORG}bank-accounts/<uuid:public_id>/statement-lines",
        imports_api.StatementLineListView.as_view(),
        name="bank-account-statement-lines",
    ),
    path(
        f"{ORG}bank-transactions",
        api.BankTransactionListView.as_view(),
        name="bank-transactions",
    ),
    path(
        f"{ORG}bank-transactions/tax-default",
        api.BankTransactionTaxDefaultView.as_view(),
        name="bank-transactions-tax-default",
    ),
    path(
        f"{ORG}bank-transactions/<uuid:public_id>",
        api.BankTransactionDetailView.as_view(),
        name="bank-transaction",
    ),
    path(
        f"{ORG}bank-transactions/<uuid:public_id>/void",
        api.BankTransactionVoidView.as_view(),
        name="bank-transaction-void",
    ),
]
