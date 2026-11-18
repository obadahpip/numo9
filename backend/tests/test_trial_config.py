"""U-05-T01 — TrialConfig singleton model (+ the console's admin field arrives with U-06).

Acceptance: one active config. ``TrialConfig.current()`` creates the default once (30 days, no
package) and always answers the same row; saving any instance writes row 1; a second row is
refused by the database; days outside 1–90 and a draft package are refused by ``clean``.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from numo9.entitlements.models import TrialConfig
from numo9.packages.models import PackageStatus
from tests.entitlement_helpers import package

pytestmark = pytest.mark.django_db


def test_one_config() -> None:
    config = TrialConfig.current()
    assert (config.pk, config.days, config.package) == (1, 30, None)
    assert TrialConfig.current().pk == config.pk
    other = TrialConfig(days=14)
    other.save()  # always the one row
    assert TrialConfig.objects.count() == 1 and TrialConfig.current().days == 14
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO entitlements_trialconfig (id, days, updated_at) VALUES (2, 30, now())"
        )


def test_rules() -> None:
    config = TrialConfig.current()
    config.days = 0
    with pytest.raises(ValidationError):
        config.full_clean()
    config.days = 30
    config.package = package("draft", ["accounting"])
    config.package.status = PackageStatus.DRAFT
    with pytest.raises(ValidationError):
        config.clean()
    config.package = package("growth", ["accounting", "payroll"])
    config.full_clean()
    config.save()
    assert TrialConfig.current().package is not None
