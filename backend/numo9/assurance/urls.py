"""Assurance routes (K-09-T20), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/assurance/"
FINDING = f"{ORG}findings/<uuid:public_id>"

urlpatterns = [
    path(ORG, api.SummaryView.as_view(), name="assurance-summary"),
    path(f"{ORG}findings", api.FindingListView.as_view(), name="assurance-findings"),
    path(FINDING, api.FindingDetailView.as_view(), name="assurance-finding"),
    path(f"{FINDING}/acknowledge", api.AcknowledgeView.as_view(), name="assurance-acknowledge"),
    path(
        f"{FINDING}/false-positive",
        api.FalsePositiveView.as_view(),
        name="assurance-false-positive",
    ),
    path(f"{FINDING}/reopen", api.ReopenView.as_view(), name="assurance-reopen"),
    path(f"{FINDING}/fix", api.FixView.as_view(), name="assurance-fix"),
    path(f"{ORG}run", api.RunView.as_view(), name="assurance-run"),
    path(f"{ORG}runs", api.RunListView.as_view(), name="assurance-runs"),
    path(f"{ORG}rules", api.RuleListView.as_view(), name="assurance-rules"),
    path(f"{ORG}rules/<str:code>", api.RuleDetailView.as_view(), name="assurance-rule"),
    path(f"{ORG}heatmap", api.HeatmapView.as_view(), name="assurance-heatmap"),
]
