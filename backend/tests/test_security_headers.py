"""S-03-T10 — every backend response carries the securityheaders.com set: CSP, HSTS (HTTPS),
X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, COOP, no banners.

Graded with the same rules as the CI check against the running services
(``tools/ci/check_security_headers.py``)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client, override_settings

from numo9.security.headers import API_CSP, HTML_CSP, SecurityHeadersMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "ci"))

import check_security_headers as grader  # noqa: E402

HTTPS = {
    "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
    "SECURE_HSTS_SECONDS": 31_536_000,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_HSTS_PRELOAD": True,
}
ROUTES = [
    ("/healthz", "application/json"),
    ("/api/v1/auth/csrf", "application/json"),
    ("/api/v1/me/organisations", "application/json"),  # 403 for anonymous: still graded
    ("/api/v1/no-such-endpoint", "text/html"),  # Django 404 page
    ("/admin/login/", "text/html"),
]


def failures(headers: dict[str, str], *, hsts: bool) -> list[str]:
    return [f"{c.header}: {c.detail}" for c in grader.grade(headers, hsts=hsts) if not c.ok]


@pytest.mark.django_db
@pytest.mark.parametrize(("path", "content_type"), ROUTES)
@override_settings(**HTTPS)
def test_every_route_has_all_security_headers_over_https(path: str, content_type: str) -> None:
    response = Client().get(path, headers={"X-Forwarded-Proto": "https"})
    headers = dict(response.headers.items())
    assert failures(headers, hsts=True) == []
    assert response.headers["Content-Type"].startswith(content_type)


@pytest.mark.django_db
def test_json_gets_data_only_csp_and_html_gets_framing_policy() -> None:
    assert Client().get("/healthz").headers["Content-Security-Policy"] == API_CSP
    assert Client().get("/admin/login/").headers["Content-Security-Policy"] == HTML_CSP


def test_view_header_is_kept() -> None:
    def view(request: HttpRequest) -> HttpResponse:
        response = HttpResponse("x", content_type="text/plain")
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    response = SecurityHeadersMiddleware(view)(HttpRequest())
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


# ---- the grader itself: a missing or weak header fails --------------------------------------

GOOD = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def test_grader_passes_the_full_set() -> None:
    assert failures(GOOD, hsts=True) == []


@pytest.mark.parametrize("missing", sorted(GOOD))
def test_grader_fails_on_each_missing_header(missing: str) -> None:
    headers = {k: v for k, v in GOOD.items() if k != missing}
    assert any(f.startswith(missing) for f in failures(headers, hsts=True))


@pytest.mark.parametrize(
    ("header", "value"),
    [
        ("Content-Security-Policy", "default-src 'self'"),  # no frame-ancestors
        ("Content-Security-Policy", "frame-ancestors 'none'; script-src 'self' 'unsafe-eval'"),
        ("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; frame-ancestors 'none'"),
        ("Strict-Transport-Security", "max-age=86400; includeSubDomains"),
        ("Strict-Transport-Security", "max-age=31536000"),
        ("X-Frame-Options", "ALLOW-FROM https://evil.example"),
        ("X-Content-Type-Options", "sniff"),
        ("Referrer-Policy", "unsafe-url"),
        ("Permissions-Policy", "camera=(self), microphone=(), geolocation=()"),
        ("Cross-Origin-Opener-Policy", "unsafe-none"),
    ],
)
def test_grader_fails_on_weak_values(header: str, value: str) -> None:
    assert any(f.startswith(header) for f in failures({**GOOD, header: value}, hsts=True))


def test_grader_flags_server_banners() -> None:
    assert failures({**GOOD, "X-Powered-By": "Next.js"}, hsts=True)
    assert failures({**GOOD, "Server": "gunicorn/26.2.0"}, hsts=True)
    assert failures({**GOOD, "Server": "cloudflare"}, hsts=True) == []


def test_grader_accepts_nonce_scripts_and_report_only_when_allowed() -> None:
    nonce = (
        "script-src 'self' 'nonce-abc' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'"
    )
    assert failures({**GOOD, "Content-Security-Policy": nonce}, hsts=True) == []
    report_only = {k: v for k, v in GOOD.items() if k != "Content-Security-Policy"}
    report_only["Content-Security-Policy-Report-Only"] = GOOD["Content-Security-Policy"]
    assert failures(report_only, hsts=True)
    checks = grader.grade(report_only, hsts=True, allow_report_only=True)
    assert all(c.ok for c in checks)
