from django.apps import AppConfig


class BankingConfig(AppConfig):
    """Banking (F): bank, credit-card, loan, cash and clearing accounts that work the moment they
    exist — no feed, import, reconciliation or plan upgrade (F-01)."""

    name = "numo9.banking"
    label = "banking"
    verbose_name = "Banking"
