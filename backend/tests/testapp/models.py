"""Concrete models used only by tests (never installed outside numo9.settings.test)."""

from django.db import models

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
