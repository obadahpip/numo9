"""Concrete models used only by tests (never installed outside numo9.settings.test)."""

from django.db import models

from numo9.audit.mixins import AuditedModel
from numo9.security.fields import EncryptedField
from numo9.tenancy.models import OrgOwnedModel


class Widget(OrgOwnedModel):
    label = models.CharField(max_length=50)


class Gadget(OrgOwnedModel):
    """Second subclass: proves several business models can inherit without accessor clashes."""

    label = models.CharField(max_length=50)


class Payee(OrgOwnedModel):
    """Encrypted fields under test (S-03-T04): SIN and bank account as M-01 will store them."""

    name = models.CharField(max_length=50)
    sin = EncryptedField(max_length=9, blank=True)
    bank_account = EncryptedField(max_length=20, null=True, blank=True)


class AuditedInvoice(AuditedModel, OrgOwnedModel):
    """A business record with the audit mixin (A-04-T03): amount, related record, masked SIN."""

    number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    customer = models.ForeignKey(Widget, on_delete=models.PROTECT, null=True, blank=True)
    notes = models.TextField(blank=True)
    payee_sin = EncryptedField(max_length=9, blank=True)
    bank_account = models.CharField(max_length=20, blank=True)  # masked by name
    internal_code = models.CharField(max_length=20, blank=True)  # masked by audit_masked
    search_text = models.TextField(blank=True)  # excluded

    audit_masked = frozenset({"internal_code"})
    audit_exclude = frozenset({"search_text"})

    def __str__(self) -> str:
        return f"Invoice {self.number}"


class AccountDefault(OrgOwnedModel):
    """Refers to an account by foreign key as items, bank accounts and journal lines will
    (C-01-T07): renumbering the account must leave the reference unchanged."""

    label = models.CharField(max_length=50)
    account = models.ForeignKey("ledger.Account", on_delete=models.PROTECT, related_name="+")


class SubscriptionStandIn(OrgOwnedModel):
    """Stand-in for U-03's Subscription (U-02-T05, T10): an organisation on a package and
    interval, with a status and the grandfathered flag — what the package guards ask about."""

    package = models.ForeignKey("packages.Package", on_delete=models.PROTECT, related_name="+")
    interval = models.CharField(max_length=8, default="month")
    status = models.CharField(max_length=16, default="active")
    grandfathered = models.BooleanField(default=False)
