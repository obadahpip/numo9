"""CAPTCHA verifier used by the brute-force tests (S-03-T07): the token "human" passes."""

from __future__ import annotations

CALLS: list[tuple[str, str | None]] = []


def verify(token: str, remote_ip: str | None) -> bool:
    CALLS.append((token, remote_ip))
    return token == "human"  # noqa: S105 — test token
