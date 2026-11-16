"""``manage.py dmarc_probe`` — DMARC pass test harness (A-07-T07); see numo9.notifications.dmarc."""

from __future__ import annotations

import os
from typing import Any

from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.notifications import dmarc
from numo9.notifications.domains import sender_for
from numo9.notifications.models import DomainStatus, SendingDomain
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation


class Command(BaseCommand):
    help = "Send a probe from the organisation's verified domain and check DMARC passes."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--org", required=True, help="Organisation public id")
        parser.add_argument("--to", required=True, help="Test mailbox address")
        parser.add_argument("--imap-host", default=os.environ.get("NUMO9_DMARC_IMAP_HOST", ""))
        parser.add_argument("--imap-user", default=os.environ.get("NUMO9_DMARC_IMAP_USER", ""))
        parser.add_argument(
            "--imap-password", default=os.environ.get("NUMO9_DMARC_IMAP_PASSWORD", "")
        )
        parser.add_argument("--timeout", type=float, default=180.0)
        parser.add_argument("--interval", type=float, default=10.0)

    def handle(self, *args: Any, **options: Any) -> None:
        organisation = Organisation.objects.filter(public_id=options["org"]).first()
        if organisation is None:
            raise CommandError("No such organisation.")
        with org_context(organisation):
            domain = SendingDomain.objects.filter(
                status=DomainStatus.VERIFIED, deleted_at__isnull=True
            ).first()
        if domain is None:
            raise CommandError("The organisation has no verified sending domain.")
        if not (options["imap_host"] and options["imap_user"] and options["imap_password"]):
            raise CommandError("Give the test mailbox's IMAP host, user and password.")
        token = dmarc.probe_token()
        from_email, reply_to = sender_for(organisation)
        EmailMessage(
            subject=f"Numo9 DMARC probe {token}",
            body=f"DMARC probe for {domain.domain}. Token: {token}",
            from_email=from_email,
            to=[options["to"]],
            reply_to=[reply_to] if reply_to else None,
        ).send()
        self.stdout.write(f"Probe sent from {from_email}; waiting for {options['to']}…")
        message = dmarc.wait_for_probe(
            token,
            host=options["imap_host"],
            user=options["imap_user"],
            password=options["imap_password"],
            timeout=options["timeout"],
            interval=options["interval"],
        )
        if message is None:
            raise CommandError("The probe did not arrive in time.")
        verdicts = dmarc.results_of(message)
        if not verdicts:
            raise CommandError("The message has no Authentication-Results header.")
        verdict = verdicts[0]
        self.stdout.write(
            f"{verdict.authserv_id}: dmarc={verdict.result('dmarc')} "
            f"spf={verdict.result('spf')} dkim={verdict.result('dkim')}"
        )
        if not verdict.dmarc_passes(domain.domain):
            raise CommandError(f"DMARC did not pass for {domain.domain}.")
        self.stdout.write(self.style.SUCCESS(f"DMARC passes for {domain.domain}."))
