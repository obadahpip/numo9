"""Response security headers Django does not set by itself (S-03-T10).

``SecurityMiddleware`` already sends ``X-Content-Type-Options``, ``Referrer-Policy``,
``Cross-Origin-Opener-Policy`` and, on HTTPS in staging/prod, ``Strict-Transport-Security``;
``XFrameOptionsMiddleware`` sends ``X-Frame-Options: DENY`` (S-03-T01). This middleware adds:

- ``Permissions-Policy`` — every powerful browser feature off, ``payment`` only for Stripe;
- ``Content-Security-Policy`` — the API serves data, never pages: JSON and other non-HTML
  responses get ``default-src 'none'``. HTML responses (Django admin, the DRF browsable API in
  dev) get a policy without script restrictions (they use Django's own inline scripts) that still
  forbids framing, plugins, ``<base>`` hijacking and posting forms elsewhere.

A view that sets its own header keeps it. The web app's pages get their nonce-based CSP and the
same headers from Next.js (``frontend/next.config.ts``, S-03-T02/T10).
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

PERMISSIONS_POLICY = ", ".join(
    [
        "accelerometer=()",
        "camera=()",
        "display-capture=()",
        "geolocation=()",
        "gyroscope=()",
        "magnetometer=()",
        "microphone=()",
        'payment=(self "https://js.stripe.com")',
        "usb=()",
    ]
)
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
HTML_CSP = "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"


class SecurityHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        content_type = response.headers.get("Content-Type", "")
        is_html = content_type.split(";", 1)[0].strip().lower() == "text/html"
        response.headers.setdefault("Content-Security-Policy", HTML_CSP if is_html else API_CSP)
        return response
