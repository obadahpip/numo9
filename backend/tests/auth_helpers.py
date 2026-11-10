"""Shared helpers for the authentication tests (A-02)."""

from __future__ import annotations

import json
from typing import Any

from allauth.account.models import EmailAddress
from django.test import Client

from numo9.accounts.models import User

API = "/_allauth/browser/v1"
PASSWORD = "correct horse battery 42"  # noqa: S105 — test credential


def post(client: Client, path: str, body: dict[str, Any], **extra: Any) -> Any:
    return client.post(f"{API}{path}", json.dumps(body), content_type="application/json", **extra)


def make_user(email: str = "dana@maple.ca", password: str = PASSWORD, **fields: Any) -> User:
    """A user with a verified email address, as after sign-up + verification."""
    fields.setdefault("name", "Dana Lee")
    user = User.objects.create_user(email=email, password=password, **fields)
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


def login(client: Client, email: str = "dana@maple.ca", password: str = PASSWORD) -> Any:
    return post(client, "/auth/login", {"email": email, "password": password})


def codes(response: Any) -> list[str]:
    return [e["code"] for e in response.json().get("errors", [])]
