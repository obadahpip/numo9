"""Invoice numbers (D-03a-T02): allocated **at approval**, inside the posting transaction.

``assign_number(invoice)`` locks the invoice row, and when it has no number yet takes the next
one from the organisation's invoice sequence (A-05 ``allocate_number``: the pattern from the
settings — ``INV-0001`` by default, prefix and padding editable). Called in the transaction
that posts the invoice: if the posting fails, the number goes back to the sequence (gap-free);
two approvals at once wait for each other on the sequence row (unique). An invoice keeps its
number for ever — voided included; calling it again returns the number it has.
"""

from __future__ import annotations

from django.db import transaction

from numo9.orgsettings.models import DocType
from numo9.orgsettings.numbering import allocate_number
from numo9.tenancy.context import org_context

from .models import Invoice


def assign_number(invoice: Invoice) -> str:
    with org_context(invoice.organisation), transaction.atomic():
        locked = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
        if locked.number:
            invoice.number = locked.number
            return locked.number
        number = allocate_number(DocType.INVOICE, invoice.organisation)
        Invoice._base_manager.filter(pk=invoice.pk).update(number=number)
        invoice.number = number
        return number
