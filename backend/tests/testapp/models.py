"""Concrete models used only by tests (never installed outside numo9.settings.test)."""

from django.db import models

from numo9.tenancy.models import OrgOwnedModel


class Widget(OrgOwnedModel):
    label = models.CharField(max_length=50)


class Gadget(OrgOwnedModel):
    """Second subclass: proves several business models can inherit without accessor clashes."""

    label = models.CharField(max_length=50)
