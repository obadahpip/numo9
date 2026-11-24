"""General ledger routes (C-02), under /api/v1/."""

from django.urls import path

from . import accounts_api, api, journals_api, workflow_api

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
    # Approval and recurring journals (C-04-T07)
    path(
        f"{ORG}journals/<uuid:public_id>/submit",
        workflow_api.JournalSubmitView.as_view(),
        name="journal-submit",
    ),
    path(
        f"{ORG}journals/<uuid:public_id>/approve",
        workflow_api.JournalApproveView.as_view(),
        name="journal-approve",
    ),
    path(
        f"{ORG}journals/<uuid:public_id>/reject",
        workflow_api.JournalRejectView.as_view(),
        name="journal-reject",
    ),
    path(
        f"{ORG}journals/<uuid:public_id>/withdraw",
        workflow_api.JournalWithdrawView.as_view(),
        name="journal-withdraw",
    ),
    path(
        f"{ORG}journals/<uuid:public_id>/reverse",
        workflow_api.JournalReverseView.as_view(),
        name="journal-reverse",
    ),
    path(
        f"{ORG}journals/recurring",
        workflow_api.RecurringListView.as_view(),
        name="recurring-journals",
    ),
    path(
        f"{ORG}journals/recurring/preview",
        workflow_api.RecurringSchedulePreviewView.as_view(),
        name="recurring-journals-preview",
    ),
    path(
        f"{ORG}journals/recurring/<uuid:public_id>",
        workflow_api.RecurringDetailView.as_view(),
        name="recurring-journal",
    ),
    path(
        f"{ORG}journals/recurring/<uuid:public_id>/preview",
        workflow_api.RecurringPreviewView.as_view(),
        name="recurring-journal-preview",
    ),
    path(f"{ORG}journals/<uuid:public_id>", api.JournalDetailView.as_view(), name="journal"),
]
