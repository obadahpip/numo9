"""A-07-T07 — DMARC pass test harness: send to a test mailbox, parse Authentication-Results.

Acceptance (harness): a verified domain's probe whose receiver reports ``dmarc=pass`` aligned
with the domain passes; ``dmarc=fail`` or a pass for another header.from domain fails. Parser
checked on real receivers' header formats (Google, Microsoft 365, Fastmail/Cyrus with ARC,
folded with comments). ``dmarc_probe`` end to end against a fake IMAP test mailbox: sent from
the verified domain, polled until it arrives, verdict printed, exit status. Also the sender rule:
verified domain → From the domain; otherwise Numo9's address with Reply-To the organisation.

The live run (real provider, real DNS, real mailbox) is ``test_live_dmarc_probe``: it runs only
when NUMO9_TEST_DMARC_ORG / _TO / _IMAP_HOST / _IMAP_USER / _IMAP_PASSWORD are set (staging).
"""

from __future__ import annotations

import os
from email.message import EmailMessage as Message
from io import StringIO
from typing import Any

import pytest
from django.core import mail
from django.core.management import CommandError, call_command

from numo9.notifications import dmarc, domains
from numo9.notifications.models import SendingDomain
from numo9.orgsettings.models import OrganisationSettings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db

GOOGLE = (
    "mx.google.com;\r\n       dkim=pass header.i=@refined.ca header.s=pm202611 header.b=Xy12;\r\n"
    "       spf=pass (google.com: domain of bounces@pm-bounces.refined.ca designates 50.31.156.6 as"
    " permitted sender) smtp.mailfrom=bounces@pm-bounces.refined.ca;\r\n"
    "       dmarc=pass (p=QUARANTINE sp=QUARANTINE dis=NONE) header.from=refined.ca"
)
MICROSOFT = (
    "spf=pass (sender IP is 50.31.156.6) smtp.mailfrom=pm-bounces.refined.ca; dkim=pass "
    "(signature was verified) header.d=refined.ca;dmarc=pass action=none "
    "header.from=refined.ca;compauth=pass reason=100"
)
FASTMAIL_FAIL = (
    "mx3.messagingengine.com; arc=none (no signatures found); dkim=fail (bad signature) "
    "header.d=refined.ca; spf=softfail smtp.mailfrom=refined.ca; dmarc=fail policy.published-"
    'domain-policy=quarantine header.from="refined.ca"'
)


def test_parser_reads_real_receivers() -> None:
    google = dmarc.parse_authentication_results(GOOGLE)
    assert google.authserv_id == "mx.google.com"
    assert (google.result("dkim"), google.result("spf"), google.result("dmarc")) == (
        "pass",
        "pass",
        "pass",
    )
    assert google.first("dkim").properties["header.s"] == "pm202611"  # type: ignore[union-attr]
    assert google.first("spf").properties["smtp.mailfrom"] == "bounces@pm-bounces.refined.ca"  # type: ignore[union-attr]
    assert google.dmarc_passes("refined.ca") and google.dmarc_passes("REFINED.CA")
    assert not google.dmarc_passes("other.ca")  # aligned with another domain: not ours

    microsoft = dmarc.parse_authentication_results(MICROSOFT)
    assert microsoft.result("dmarc") == "pass" and microsoft.dmarc_passes("refined.ca")

    fastmail = dmarc.parse_authentication_results(FASTMAIL_FAIL)
    assert fastmail.result("arc") == "none" and fastmail.result("dkim") == "fail"
    assert fastmail.result("spf") == "softfail"
    assert fastmail.result("dmarc") == "fail" and not fastmail.dmarc_passes("refined.ca")
    assert dmarc.parse_authentication_results("mx.example; none").result("dmarc") == "none"


class FakeMailbox:
    """IMAP test mailbox: the probe arrives on the ``arrive_after``-th poll."""

    polls = 0

    def __init__(self, inbox: list[bytes], arrive_after: int = 2) -> None:
        self.inbox, self.arrive_after = inbox, arrive_after

    def __call__(self, host: str) -> FakeMailbox:
        assert host == "imap.test.example"
        type(self).polls += 1
        return self

    def login(self, user: str, password: str) -> None:
        assert (user, password) == ("probe@test.example", "secret")

    def select(self, name: str) -> None: ...

    def search(self, charset: Any, *criteria: str) -> tuple[str, list[bytes]]:
        if type(self).polls < self.arrive_after:
            return "OK", [b""]
        token = criteria[1].strip('"')
        hits = [str(i + 1).encode() for i, raw in enumerate(self.inbox) if token.encode() in raw]
        return "OK", [b" ".join(hits)]

    def fetch(self, number: bytes, parts: str) -> tuple[str, list[Any]]:
        return "OK", [(b"1 (RFC822 {n}", self.inbox[int(number) - 1]), b")"]

    def logout(self) -> None: ...


@pytest.fixture
def verified_org() -> Organisation:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        SendingDomain.objects.create(
            organisation=org, domain="refined.ca", from_local_part="invoices",
            provider="local", status="verified",
        )  # fmt: skip
    return org


def _arrived(subject: str, authentication_results: str) -> bytes:
    message = Message()
    message["Subject"] = subject
    message["From"] = "Refined Interiors Inc. <invoices@refined.ca>"
    message["Authentication-Results"] = " ".join(authentication_results.split())
    message.set_content("probe")
    return message.as_bytes()


def _run_probe(org: Organisation, verdict: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Run dmarc_probe; the 'receiver' stamps ``verdict`` on whatever was sent."""
    inbox: list[bytes] = []
    FakeMailbox.polls = 0

    def wait(token: str, **kwargs: Any) -> Any:
        sent = mail.outbox[-1]
        inbox.append(_arrived(str(sent.subject), verdict))
        kwargs["imap_factory"] = FakeMailbox(inbox)
        kwargs["interval"] = 0
        return original(token, **kwargs)

    original = dmarc.wait_for_probe
    monkeypatch.setattr(dmarc, "wait_for_probe", wait)
    out = StringIO()
    call_command(
        "dmarc_probe", org=str(org.public_id), to="probe@test.example",
        imap_host="imap.test.example", imap_user="probe@test.example",
        imap_password="secret", timeout=5, stdout=out,  # noqa: S106 (fake mailbox)
    )  # fmt: skip
    return out.getvalue()


def test_probe_from_a_verified_domain_passes(
    verified_org: Organisation, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _run_probe(verified_org, GOOGLE, monkeypatch)
    [probe] = mail.outbox
    assert probe.from_email == '"Refined Interiors Inc." <invoices@refined.ca>'
    assert probe.subject.startswith("Numo9 DMARC probe numo9-dmarc-")
    assert FakeMailbox.polls == 2  # polled until it arrived
    assert "mx.google.com: dmarc=pass spf=pass dkim=pass" in out
    assert "DMARC passes for refined.ca." in out


def test_probe_fails_when_the_receiver_says_fail(
    verified_org: Organisation, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(CommandError, match="DMARC did not pass for refined.ca"):
        _run_probe(verified_org, FASTMAIL_FAIL, monkeypatch)


def test_probe_needs_a_verified_domain_and_a_mailbox() -> None:
    org = Organisation.objects.create(name="Maple Leaf Bakery")
    with pytest.raises(CommandError, match="no verified sending domain"):
        call_command("dmarc_probe", org=str(org.public_id), to="p@test.example")


def test_sender_rule(verified_org: Organisation) -> None:
    assert domains.sender_for(verified_org) == (
        '"Refined Interiors Inc." <invoices@refined.ca>',  # RFC 5322: a dot is quoted
        "",
    )
    other = Organisation.objects.create(name="Maple Leaf Bakery")
    with org_context(other):
        OrganisationSettings.objects.create(
            organisation=other,
            legal_name="Maple Leaf Bakery Ltd.",
            display_name="Maple Leaf Bakery",
            email="hello@mapleleaf.ca",
        )
    assert domains.sender_for(other) == (
        "Maple Leaf Bakery via Numo9 <no-reply@numo9.ca>",
        "hello@mapleleaf.ca",
    )


LIVE = ("ORG", "TO", "IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD")


@pytest.mark.skipif(
    not all(os.environ.get(f"NUMO9_TEST_DMARC_{name}") for name in LIVE),
    reason="live DMARC probe: set NUMO9_TEST_DMARC_* (staging, real provider and mailbox)",
)
@pytest.mark.django_db(databases=["default"])
def test_live_dmarc_probe() -> None:  # pragma: no cover - staging only
    env = {name: os.environ[f"NUMO9_TEST_DMARC_{name}"] for name in LIVE}
    call_command(
        "dmarc_probe", org=env["ORG"], to=env["TO"], imap_host=env["IMAP_HOST"],
        imap_user=env["IMAP_USER"], imap_password=env["IMAP_PASSWORD"],
    )  # fmt: skip
