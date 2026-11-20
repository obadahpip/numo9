"""General ledger routes (C-02), under /api/v1/."""

from django.urls import path

from . import accounts_api, api, journals_api

ORG = "o/<uuid:org>/"

urlpatterns = [
    # Chart of accounts (C-01-T09)
    path(f"{ORG}accounts", accounts_api.AccountListView.as_view(), name="accounts"),
    path(f"{ORG}accounts/tree", accounts_api.AccountTreeView.as_view(), name="accounts-tree"),
    path(f"{ORG}accounts/bulk", accounts_api.AccountBulkView.as_view(), name="accounts-bulk"),
    path(
        f"{ORG}accounts/<uuid:public_id>",
        accounts_api.AccountDetailView.as_view(),
        name="account",
    ),
    path(
        f"{ORG}accounts/<uuid:public_id>/renumber",
        accounts_api.AccountRenumberView.as_view(),
        name="account-renumber",
    ),
    path(
        f"{ORG}accounts/<uuid:public_id>/archive",
        accounts_api.AccountArchiveView.as_view(),
        name="account-archive",
    ),
    path(
        f"{ORG}accounts/<uuid:public_id>/restore",
        accounts_api.AccountRestoreView.as_view(),
        name="account-restore",
    ),
    path(f"{ORG}gifi", accounts_api.GifiSearchView.as_view(), name="gifi-search"),
    path(f"{ORG}journals", journals_api.JournalsView.as_view(), name="journals"),
    path(f"{ORG}journals/check", journals_api.JournalCheckView.as_view(), name="journals-check"),
    path(
        f"{ORG}journals/<uuid:public_id>/post",
        journals_api.JournalPostView.as_view(),
        name="journal-post",
    ),
    path(f"{ORG}journals/<uuid:public_id>", api.JournalDetailView.as_view(), name="journal"),
]
