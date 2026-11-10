"""check_security_headers — securityheaders.com-style grade of HTTP response headers (S-03-T10).

    python tools/ci/check_security_headers.py URL [URL ...] [--hsts] [--header "Name: value"]

Requests every URL (GET, redirects not followed) and checks the response headers:

- ``Content-Security-Policy`` present (not only ``-Report-Only``), with ``frame-ancestors`` and
  ``object-src`` or ``default-src``; no ``'unsafe-eval'``, no ``'unsafe-inline'`` script without
  a nonce or hash;
- ``Strict-Transport-Security`` (with ``--hsts``): ``max-age`` >= 1 year and
  ``includeSubDomains``;
- ``X-Frame-Options``: ``DENY`` or ``SAMEORIGIN``;
- ``X-Content-Type-Options``: ``nosniff``;
- ``Referrer-Policy``: ``no-referrer``, ``same-origin``, ``strict-origin`` or
  ``strict-origin-when-cross-origin``;
- ``Permissions-Policy``: ``camera``, ``microphone``, ``geolocation`` disabled (``=()``);
- ``Cross-Origin-Opener-Policy``: ``same-origin``;
- no framework banner (``X-Powered-By``) and no version number in ``Server``.

``--allow-report-only`` accepts ``Content-Security-Policy-Report-Only`` (first week on a new
environment). Exit 1 when any URL misses a header; the grade table is printed either way.
The same rules are used by the backend tests (``backend/tests/test_security_headers.py``).
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

ONE_YEAR = 31_536_000
SAFE_REFERRER = {"no-referrer", "same-origin", "strict-origin", "strict-origin-when-cross-origin"}
DISABLED_FEATURES = ("camera", "microphone", "geolocation")
VERSION = re.compile(r"\d+\.\d+")


@dataclass(frozen=True)
class Check:
    header: str
    ok: bool
    detail: str


Headers = Mapping[str, str]


def _get(headers: Headers, name: str) -> str | None:
    lowered = {k.lower(): v for k, v in headers.items()}
    return lowered.get(name.lower())


def csp_directives(policy: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for part in policy.split(";"):
        tokens = part.split()
        if tokens:
            directives.setdefault(tokens[0].lower(), tokens[1:])
    return directives


def check_csp(headers: Headers, allow_report_only: bool = False) -> Check:
    name = "Content-Security-Policy"
    policy = _get(headers, name)
    if policy is None and allow_report_only:
        policy = _get(headers, "Content-Security-Policy-Report-Only")
        name = "Content-Security-Policy-Report-Only"
    if policy is None:
        return Check("Content-Security-Policy", False, "missing")
    directives = csp_directives(policy)
    problems: list[str] = []
    if "frame-ancestors" not in directives:
        problems.append("no frame-ancestors")
    if "object-src" not in directives and "default-src" not in directives:
        problems.append("no object-src/default-src")
    script = directives.get("script-src", directives.get("default-src", []))
    if "'unsafe-eval'" in script:
        problems.append("script-src allows 'unsafe-eval'")
    has_nonce = any(t.startswith("'nonce-") or t.startswith("'sha") for t in script)
    if "'unsafe-inline'" in script and not has_nonce:
        problems.append("script-src allows 'unsafe-inline'")
    return Check("Content-Security-Policy", not problems, "; ".join(problems) or name)


def check_hsts(headers: Headers) -> Check:
    value = _get(headers, "Strict-Transport-Security")
    if value is None:
        return Check("Strict-Transport-Security", False, "missing")
    match = re.search(r"max-age\s*=\s*\"?(\d+)", value, re.IGNORECASE)
    problems = []
    if not match or int(match.group(1)) < ONE_YEAR:
        problems.append(f"max-age below {ONE_YEAR}")
    if "includesubdomains" not in value.lower():
        problems.append("no includeSubDomains")
    return Check("Strict-Transport-Security", not problems, "; ".join(problems) or value)


def check_equals(header: str, allowed: set[str]) -> Callable[[Headers], Check]:
    def check(headers: Headers) -> Check:
        value = _get(headers, header)
        if value is None:
            return Check(header, False, "missing")
        # Referrer-Policy may list fallbacks; the browser uses the last one it knows.
        last = value.split(",")[-1].strip().lower()
        return Check(header, last in allowed, value if last in allowed else f"weak value {value!r}")

    return check


def check_permissions_policy(headers: Headers) -> Check:
    value = _get(headers, "Permissions-Policy")
    if value is None:
        return Check("Permissions-Policy", False, "missing")
    features = {}
    for part in value.split(","):
        feature, _, allow = part.strip().partition("=")
        features[feature.strip().lower()] = allow.strip()
    open_features = [f for f in DISABLED_FEATURES if features.get(f) != "()"]
    if open_features:
        return Check("Permissions-Policy", False, f"not disabled: {', '.join(open_features)}")
    return Check("Permissions-Policy", True, f"{len(features)} features restricted")


def check_banners(headers: Headers) -> Check:
    problems = []
    if _get(headers, "X-Powered-By") is not None:
        problems.append(f"X-Powered-By: {_get(headers, 'X-Powered-By')}")
    server = _get(headers, "Server")
    if server is not None and VERSION.search(server):
        problems.append(f"Server reveals a version: {server}")
    return Check("No server banners", not problems, "; ".join(problems) or "none")


def grade(headers: Headers, *, hsts: bool = False, allow_report_only: bool = False) -> list[Check]:
    checks = [
        check_csp(headers, allow_report_only),
        check_equals("X-Frame-Options", {"deny", "sameorigin"})(headers),
        check_equals("X-Content-Type-Options", {"nosniff"})(headers),
        check_equals("Referrer-Policy", SAFE_REFERRER)(headers),
        check_permissions_policy(headers),
        check_equals("Cross-Origin-Opener-Policy", {"same-origin"})(headers),
        check_banners(headers),
    ]
    if hsts:
        checks.insert(1, check_hsts(headers))
    return checks


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def fetch(url: str, extra: Mapping[str, str]) -> tuple[int, dict[str, str]]:
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"not an http(s) URL: {url}")
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers=dict(extra))  # noqa: S310 — scheme checked
    try:
        with opener.open(request, timeout=30) as response:
            return response.status, dict(response.headers.items())
    except urllib.error.HTTPError as error:  # 3xx/4xx/5xx still carry headers to grade
        return error.code, dict(error.headers.items())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_security_headers")
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--hsts", action="store_true", help="require Strict-Transport-Security")
    parser.add_argument("--allow-report-only", action="store_true")
    parser.add_argument("--header", action="append", default=[], help='extra "Name: value"')
    args = parser.parse_args(argv)
    extra = dict(h.split(":", 1) for h in args.header)
    extra = {k.strip(): v.strip() for k, v in extra.items()}

    failed = False
    for url in args.urls:
        try:
            status, headers = fetch(url, extra)
        except (OSError, ValueError) as exc:
            print(f"::error::check_security_headers: {url}: request failed ({exc})")
            failed = True
            continue
        checks = grade(headers, hsts=args.hsts, allow_report_only=args.allow_report_only)
        passed = sum(c.ok for c in checks)
        print(f"\n{url} — HTTP {status} — {passed}/{len(checks)} headers")
        for check in checks:
            print(f"  {'PASS' if check.ok else 'FAIL'}  {check.header:<28} {check.detail}")
            if not check.ok:
                print(f"::error::check_security_headers: {url}: {check.header} {check.detail}")
        failed = failed or passed != len(checks)
    print(f"\ncheck_security_headers: {'FAILED' if failed else 'OK'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
