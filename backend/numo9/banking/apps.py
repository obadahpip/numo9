from django.apps import AppConfig


class BankingConfig(AppConfig):
    """Banking (F): bank, credit-card, loan, cash and clearing accounts that work the moment they
    exist — no feed, import, reconciliation or plan upgrade (F-01)."""

    name = "numo9.banking"
    label = "banking"
    verbose_name = "Banking"

    def ready(self) -> None:
        from numo9.ledger.services import ENTRY_WRITTEN

        from .balances import entry_written

        if entry_written not in ENTRY_WRITTEN:
            ENTRY_WRITTEN.append(entry_written)  # bust cached balances on every post (F-01-T06)
