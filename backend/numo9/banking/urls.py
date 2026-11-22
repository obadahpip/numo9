"""Banking routes (F-01-T07), under /api/v1/."""

from django.urls import path

from . import api

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
        f"{ORG}bank-transactions",
        api.BankTransactionListView.as_view(),
        name="bank-transactions",
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
