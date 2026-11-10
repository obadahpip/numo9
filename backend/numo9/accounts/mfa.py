"""Two-factor authentication (A-02-T05) on django-allauth's MFA module.

allauth.mfa provides TOTP enrolment, the login challenge (pending flow ``mfa_authenticate``) and
the signed "trust this browser" cookie. Numo9 adds:

- **Encrypted TOTP secrets** — the MFA adapter stores secrets with the field-encryption key ring
  (AES-256-GCM envelope, ``numo9.security.crypto``, S-03-T04) instead of plain text.
- **Hashed recovery codes** — allauth derives its codes from a stored seed and can show them
  again; Numo9 stores only a password hash of each of the 10 codes (``make_password``: Argon2id
  in staging/prod). The codes exist in clear text only in the response that creates them
  (``MFA_RECOVERY_CODES_SHOW_ONCE``); each works once. ``HashedRecoveryCodes`` replaces allauth's
  ``RecoveryCodes`` wrapper at start-up (``install()``, called from ``AccountsConfig.ready``);
  ``tests/test_auth_totp.py`` fails if an allauth upgrade bypasses it.
"""

from __future__ import annotations

import base64
import secrets
from io import BytesIO
from typing import Any

from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal import auth as rc_auth
from allauth.mfa.recovery_codes.internal import flows as rc_flows
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction

from numo9.security import crypto

TOTP_SECRET_CONTEXT = "allauth.mfa.Authenticator.data"  # noqa: S105 — AAD label, not a secret
SCHEME = "numo9-hashed-v1"
# 10 characters from an unambiguous alphabet (no 0/o, 1/l/i), shown as "xxxxx-xxxxx": 50 bits.
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
CODE_LENGTH = 10
MASK = "•••••-•••••"


def normalise(code: str) -> str:
    return "".join(ch for ch in code.lower() if ch.isalnum())


def looks_like_recovery_code(code: str) -> bool:
    value = normalise(code)
    return len(value) == CODE_LENGTH and all(ch in ALPHABET for ch in value)


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
    return f"{raw[:5]}-{raw[5:]}"


class MFAAdapter(DefaultMFAAdapter):  # type: ignore[misc]  # allauth is untyped
    def encrypt(self, text: str) -> str:
        return str(crypto.encrypt(text, TOTP_SECRET_CONTEXT))

    def decrypt(self, encrypted_text: str) -> str:
        if not crypto.is_ciphertext(encrypted_text):  # created before encryption was enabled
            return encrypted_text
        return crypto.decrypt(encrypted_text, TOTP_SECRET_CONTEXT)

    def get_totp_issuer(self) -> str:
        return "Numo9"

    def qr_code_data_uri(self, url: str) -> str:
        """The otpauth:// URL as an SVG QR code, inline (the CSP allows ``data:`` images)."""
        import qrcode
        import qrcode.image.svg

        image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage)
        buffer = BytesIO()
        image.save(buffer)
        return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode()


class HashedRecoveryCodes(rc_auth.RecoveryCodes):  # type: ignore[misc]  # allauth is untyped
    """Recovery codes stored as password hashes, shown once, each usable once."""

    instance: Authenticator

    @classmethod
    def activate(cls, user: Any) -> HashedRecoveryCodes:
        instance = Authenticator.objects.filter(
            user_id=user.pk, type=Authenticator.Type.RECOVERY_CODES
        ).first()
        if instance:
            return cls(instance)
        count = int(getattr(settings, "MFA_RECOVERY_CODE_COUNT", 10))
        codes = [new_code() for _ in range(count)]
        instance = Authenticator(
            user=user,
            type=Authenticator.Type.RECOVERY_CODES,
            data={
                "scheme": SCHEME,
                "hashes": [make_password(normalise(code)) for code in codes],
                "used_mask": 0,
            },
        )
        instance.save()
        # Clear text only on this in-memory object, for the response that creates the codes.
        instance._numo9_plain_codes = codes
        return cls(instance)

    @property
    def _hashed(self) -> bool:
        return bool(self.instance.data.get("scheme") == SCHEME)

    def _plain(self) -> list[str] | None:
        codes: list[str] | None = getattr(self.instance, "_numo9_plain_codes", None)
        return codes

    def generate_codes(self) -> list[str]:
        if not self._hashed:
            return list(super().generate_codes())
        plain = self._plain()
        return list(plain) if plain else [MASK] * len(self.instance.data["hashes"])

    def get_unused_codes(self) -> list[str]:
        if not self._hashed:
            return list(super().get_unused_codes())
        codes = self.generate_codes()
        return [code for i, code in enumerate(codes) if not self._is_code_used(i)]

    @transaction.atomic
    def validate_code(self, code: str) -> bool:
        if not self._hashed:
            return bool(super().validate_code(code))
        if not looks_like_recovery_code(code):  # e.g. a TOTP code: no hashing work
            return False
        if self.instance.pk is not None:
            self.instance = Authenticator.objects.select_for_update().get(pk=self.instance.pk)
        value = normalise(code)
        for i, hashed in enumerate(self.instance.data["hashes"]):
            if not self._is_code_used(i) and check_password(value, hashed):
                self._mark_code_used(i)
                return True
        return False


def install() -> None:
    """Make allauth use the hashed recovery codes everywhere it builds the wrapper."""
    rc_auth.RecoveryCodes = HashedRecoveryCodes  # used by Authenticator.wrap()
    rc_flows.RecoveryCodes = HashedRecoveryCodes  # used to generate codes
