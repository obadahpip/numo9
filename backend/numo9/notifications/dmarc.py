"""DMARC pass test harness (A-07-T07): send a probe from a verified domain to a test mailbox
and read the receiver's verdict in ``Authentication-Results`` (RFC 8601).

    python manage.py dmarc_probe --org <public id> --to probe@test-mailbox.example \\
        --imap-host imap.example --imap-user probe@… --imap-password … [--timeout 180]

1. the organisation's **verified** sending domain gives the From address
   (``invoices@refined.ca``); the probe's subject carries a random token;
2. the probe is sent at once through the configured email backend (the provider in staging);
3. the test mailbox is polled over IMAP (SSL) until a message with the token arrives;
4. its ``Authentication-Results`` header is parsed: ``dmarc=pass`` with ``header.from`` equal to
   the domain is a pass; SPF and DKIM results are reported too (DMARC passes when either passes
   *aligned*). The command exits 1 on anything but a DMARC pass.

``parse_authentication_results`` is also used by tests and by support when a client forwards a
message that landed in spam.
"""

from __future__ import annotations

import contextlib
import email
import imaplib
import re
import secrets
import time
from dataclasses import dataclass, field
from email.message import Message
from typing import Any

#: method=result, e.g. ``dmarc=pass``, ``dkim=fail (bad signature)``.
_RESULT = re.compile(r"(?:^|;)\s*(spf|dkim|dmarc|arc)\s*=\s*([a-z]+)([^;]*)", re.I)
_PROPERTY = re.compile(r"\b([a-z]+\.[a-z0-9_-]+)\s*=\s*(\"[^\"]*\"|[^\s;()]+)", re.I)


@dataclass
class MethodResult:
    method: str
    result: str
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class AuthenticationResults:
    authserv_id: str
    results: list[MethodResult]

    def first(self, method: str) -> MethodResult | None:
        return next((r for r in self.results if r.method == method), None)

    def result(self, method: str) -> str:
        found = self.first(method)
        return found.result if found else "none"

    def dmarc_passes(self, domain: str) -> bool:
        dmarc = self.first("dmarc")
        if dmarc is None or dmarc.result != "pass":
            return False
        header_from = dmarc.properties.get("header.from", "").strip('"').lower()
        return header_from in ("", domain.lower())


def _strip_comments(value: str) -> str:
    depth, out = 0, []
    for char in value:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(char)
    return "".join(out)


def parse_authentication_results(header: str) -> AuthenticationResults:
    """Parse one ``Authentication-Results`` header value (folding and comments allowed)."""
    value = " ".join(header.split())
    authserv, _, rest = value.partition(";")
    results = []
    for match in _RESULT.finditer(";" + _strip_comments(rest)):
        properties = {k.lower(): v.strip('"') for k, v in _PROPERTY.findall(match.group(3))}
        results.append(MethodResult(match.group(1).lower(), match.group(2).lower(), properties))
    return AuthenticationResults(authserv.strip().split(" ")[0], results)


def results_of(message: Message) -> list[AuthenticationResults]:
    return [
        parse_authentication_results(str(h))
        for h in message.get_all("Authentication-Results") or []
    ]


def probe_token() -> str:
    return f"numo9-dmarc-{secrets.token_hex(8)}"


def wait_for_probe(
    token: str,
    *,
    host: str,
    user: str,
    password: str,
    timeout: float = 180.0,
    interval: float = 10.0,
    imap_factory: Any = imaplib.IMAP4_SSL,
) -> Message | None:
    """Poll the test mailbox until the probe with ``token`` in its subject arrives."""
    deadline = time.monotonic() + timeout
    while True:
        mailbox = imap_factory(host)
        try:
            mailbox.login(user, password)
            mailbox.select("INBOX")
            status, data = mailbox.search(None, "SUBJECT", f'"{token}"')
            ids = data[0].split() if status == "OK" and data and data[0] else []
            if ids:
                status, fetched = mailbox.fetch(ids[-1], "(RFC822)")
                raw = next(part[1] for part in fetched if isinstance(part, tuple))
                return email.message_from_bytes(raw)
        finally:
            with contextlib.suppress(Exception):  # closing a connection that already failed
                mailbox.logout()
        if time.monotonic() >= deadline:
            return None
        time.sleep(interval)
