"""Duplicate receipt warning (E-04-T07): the same receipt image claimed twice.

A receipt document's ``sha256`` (A-06, the hash of its bytes) is compared with the receipts of
every other expense claim line in the organisation — any claimant, any status except deleted
claims — so a photo uploaded twice, or the same PDF on two claims, is flagged. A **warning**, not
a block: the approver decides (a split receipt can be legitimate).

- ``duplicates_of(line)`` → the other lines with the same receipt, oldest first;
- ``claim_warnings(claim)`` → one warning per line of ``claim`` whose receipt is a duplicate,
  naming the claim(s) where it was already used.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from django.utils.translation import gettext as _

from .models import ExpenseClaimLine


def duplicates_of(line: ExpenseClaimLine) -> QuerySet[ExpenseClaimLine]:
    receipt = line.receipt
    if receipt is None or not receipt.sha256:
        return ExpenseClaimLine.objects.none()
    return (
        ExpenseClaimLine.objects.filter(
            organisation_id=line.organisation_id,
            receipt__sha256=receipt.sha256,
            claim__deleted_at__isnull=True,
        )
        .exclude(pk=line.pk)
        .select_related("claim", "claim__claimant", "receipt")
        .order_by("claim__created_at", "pk")
    )


def _where(other: ExpenseClaimLine) -> str:
    claim = other.claim
    return f"{claim} ({claim.claimant.name or claim.claimant.email})"


def claim_warnings(claim: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in claim.lines.select_related("receipt").all():
        others = list(duplicates_of(line))
        if not others:
            continue
        out.append(
            {
                "code": "purchases.expense.duplicate_receipt",
                "line": str(line.public_id),
                "message": _("This receipt was already claimed on %(claims)s.")
                % {"claims": ", ".join(dict.fromkeys(_where(o) for o in others))},
                "claims": [str(o.claim.public_id) for o in others],
            }
        )
    return out
