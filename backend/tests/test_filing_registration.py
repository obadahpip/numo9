"""G-03a-T03 — the A-05 TaxRegistration is the filing registration: GST/HST (RT) and QST file
returns, with a start date, an optional stop date and a status; the other numbers don't."""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.orgsettings.models import FILING_TYPES, RegistrationStatus, TaxRegistration
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def test_gst_hst_and_qst_registrations_file_returns() -> None:
    org = Organisation.objects.create(name="Filing Ltd.")
    with org_context(org):
        gst = TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2026, 1, 15),
        )
        gst.save()
        qst = TaxRegistration(
            organisation=org,
            type="qst",
            number="1234567890TQ0001",
            effective_from=dt.date(2026, 1, 1),
            effective_to=dt.date(2026, 12, 31),
        )
        qst.save()
        payroll = TaxRegistration(organisation=org, type="rp", number="123456782RP0001")
        payroll.save()
    assert {"rt", "qst"} == FILING_TYPES
    assert gst.files_returns and qst.files_returns and not payroll.files_returns
    assert (gst.start_date, gst.stop_date) == (dt.date(2026, 1, 15), None)
    assert qst.stop_date == dt.date(2026, 12, 31)
    assert gst.status == RegistrationStatus.ACTIVE
