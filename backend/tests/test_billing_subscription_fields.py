"""U-04-T02 — Billing fields on ``Subscription``. Acceptance: the migration applies.

Covers: defaults (monthly, not cancelling, no Stripe ids, no method), the database defaults of the
new columns (rows inserted by code that doesn't know them), one local subscription per Stripe
subscription id (blank ids repeat freely), interval and payment method checks, the migration
rolls back and forward.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from numo9.entitlements.models import PaymentMethodType, Subscription
from numo9.tenancy.models import Organisation
from tests.entitlement_helpers import subscribe

pytestmark = pytest.mark.django_db


def _sub(name: str, **fields: object) -> Subscription:
    return subscribe(Organisation.objects.create(name=name), None, **fields)


def test_defaults() -> None:
    sub = _sub("Maple Bakery Inc.")
    sub.refresh_from_db()
    assert (sub.interval, sub.cancel_at_period_end) == ("month", False)
    assert sub.stripe_customer_id == sub.stripe_subscription_id == sub.payment_method_type == ""


def test_database_defaults_for_old_code() -> None:
    org = Organisation.objects.create(name="Old Code Inc.")
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO entitlements_subscription (organisation_id, public_id, status, founding,"
            " override, status_changed_at, status_reason, created_at, updated_at)"
            " VALUES (%s, gen_random_uuid(), 'active', false, '{}', now(), '', now(), now())"
            " RETURNING interval, cancel_at_period_end, stripe_customer_id, payment_method_type",
            [org.pk],
        )
        assert cursor.fetchone() == ("month", False, "", "")


def test_stripe_subscription_id_is_unique_blanks_repeat() -> None:
    _sub("A Inc.", stripe_subscription_id="sub_123", stripe_customer_id="cus_A")
    _sub("B Inc.")
    _sub("C Inc.")
    with pytest.raises(IntegrityError), transaction.atomic():
        _sub("D Inc.", stripe_subscription_id="sub_123")


@pytest.mark.parametrize(
    ("column", "value"), [("interval", "week"), ("payment_method_type", "bitcoin")]
)
def test_checks(column: str, value: str) -> None:
    sub = _sub("Maple Bakery Inc.", payment_method_type=PaymentMethodType.CARD)
    with pytest.raises(IntegrityError), transaction.atomic():
        Subscription._base_manager.filter(pk=sub.pk).update(**{column: value})


@pytest.mark.django_db(transaction=True)
def test_migration_rolls_back_and_forward() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("entitlements", "0003_product_history")])
    columns = [
        c.name
        for c in connection.introspection.get_table_description(
            connection.cursor(), "entitlements_subscription"
        )
    ]
    assert "stripe_customer_id" not in columns
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())
    columns = [
        c.name
        for c in connection.introspection.get_table_description(
            connection.cursor(), "entitlements_subscription"
        )
    ]
    assert {"stripe_customer_id", "stripe_subscription_id", "interval"} <= set(columns)
