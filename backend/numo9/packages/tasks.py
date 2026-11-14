"""Celery tasks of the packages app — found by ``app.autodiscover_tasks()`` (A-08).

The Stripe price sync job lives with its gateway in ``stripe_sync`` (U-02-T12).
"""

from .stripe_sync import sync_stripe_prices

__all__ = ["sync_stripe_prices"]
