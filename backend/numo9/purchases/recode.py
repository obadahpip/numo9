"""Find & recode (C-07-T03): the entries of void bills are excluded."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.ledger.recode_exclusions import register_exclusion, voided_documents

from .models import Bill

VOID_BILLS = voided_documents("purchases.bill", Bill, _("Bill"))


def register_recode_exclusions() -> None:
    register_exclusion(VOID_BILLS)
