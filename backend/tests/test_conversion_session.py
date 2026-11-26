"""C-05-T01 — ConversionSession: one per organisation (a second active session is refused by
the service and by the database), draft until finalised (a finalised session is dated),
audited; another organisation's session doesn't count.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.conversion.models import ConversionSession
from numo9.conversion.services import current_session, start_conversion
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.conversion_helpers import posted_entry
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db
D = dt.date(2026, 4, 1)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def test_start_draft_audited(org: Organisation) -> None:
    owner = people(org)["owner"]
    session = start_conversion(org, D, user=owner)
    assert (session.status, session.conversion_date, session.created_by) == ("draft", D, owner)
    assert current_session(org) == session
    with org_context(org):
        assert AuditEvent.objects.filter(
            object_type="conversion.ConversionSession", object_id=str(session.public_id)
        ).exists()


def test_second_session_refused(org: Organisation) -> None:
    start_conversion(org, D, user=None)
    with pytest.raises(ValidationError) as caught:
        start_conversion(org, dt.date(2026, 5, 1), user=None)
    codes = {e.code for items in caught.value.error_dict.values() for e in items}
    assert "conversion.session.exists" in codes
    with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
        ConversionSession(organisation=org, conversion_date=D).save()


def test_other_organisations_do_not_count_and_finalised_needs_a_date(org: Organisation) -> None:
    other = Organisation.objects.create(name="Other Co.")
    start_conversion(other, D, user=None)
    session = start_conversion(org, D, user=None)
    with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
        ConversionSession._base_manager.filter(pk=session.pk).update(status="finalised")
    with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
        ConversionSession._base_manager.filter(pk=session.pk).update(  # C-05-T05: no journal
            status="finalised", finalised_at=timezone.now()
        )
    entry = posted_entry(org)
    with org_context(org):
        ConversionSession._base_manager.filter(pk=session.pk).update(
            status="finalised", finalised_at=timezone.now(), opening_entry=entry
        )
        session.refresh_from_db()
        assert session.is_finalised
