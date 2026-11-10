"""Envelope encryption for sensitive fields (S-03-T04): AES-256-GCM, key id stored with the
ciphertext.

Each value gets its own random 256-bit data key (DEK). The value is encrypted with the DEK; the
DEK is encrypted ("wrapped") with a key-encryption key (KEK) from the key ring. Hetzner has no
KMS (ADR-0002), so the KEKs come from the SOPS-encrypted environment (S-03-T03):

    NUMO9_FIELD_ENCRYPTION_KEYS={"2026-11": "<base64 of 32 random bytes>"}
    NUMO9_FIELD_ENCRYPTION_ACTIVE_KEY=2026-11

Stored form (text, ASCII):
``n9e1:<key id>:<b64 wrap nonce + wrapped DEK>:<b64 nonce + ciphertext>``

Both encryptions authenticate the *context* (``app_label.Model.field``) as associated data, so a
ciphertext copied into another column does not decrypt. Rotating the KEK only re-wraps the DEK
(``rewrap``); the value's ciphertext is unchanged.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PREFIX = "n9e1"
KEY_ID = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
_NONCE = 12
_KEY_BYTES = 32


class Ciphertext(str):
    """A value that is already encrypted: stored as is (the rotation command writes these)."""

    __slots__ = ()


class DecryptionError(Exception):
    """The value is not a valid Numo9 ciphertext, or no key in the ring can open it."""


@dataclass(frozen=True)
class KeyRing:
    keys: dict[str, bytes]
    active: str

    @property
    def active_key(self) -> bytes:
        return self.keys[self.active]


def parse_key_ring(keys: Any, active: str) -> KeyRing:
    """Validate a key ring: JSON object (or dict) of key id → base64 32-byte key, plus the
    active id."""
    if isinstance(keys, str):
        if not keys.strip():
            raise ImproperlyConfigured(
                "Field encryption keys are not configured (NUMO9_FIELD_ENCRYPTION_KEYS)."
            )
        try:
            keys = json.loads(keys)
        except json.JSONDecodeError as error:
            raise ImproperlyConfigured(
                "NUMO9_FIELD_ENCRYPTION_KEYS must be a JSON object."
            ) from error
    if not isinstance(keys, dict) or not keys:
        raise ImproperlyConfigured("NUMO9_FIELD_ENCRYPTION_KEYS must be a non-empty JSON object.")
    ring: dict[str, bytes] = {}
    for key_id, encoded in keys.items():
        if not isinstance(key_id, str) or not KEY_ID.match(key_id):
            raise ImproperlyConfigured(f"Invalid field-encryption key id {key_id!r}.")
        try:
            raw = base64.b64decode(str(encoded), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ImproperlyConfigured(f"Field-encryption key {key_id!r} is not base64.") from error
        if len(raw) != _KEY_BYTES:
            raise ImproperlyConfigured(
                f"Field-encryption key {key_id!r} must be {_KEY_BYTES} bytes (AES-256)."
            )
        ring[key_id] = raw
    if active not in ring:
        raise ImproperlyConfigured(
            f"NUMO9_FIELD_ENCRYPTION_ACTIVE_KEY {active!r} is not in the key ring."
        )
    return KeyRing(keys=ring, active=active)


@lru_cache(maxsize=4)
def _ring_from(keys: str, active: str) -> KeyRing:
    return parse_key_ring(keys, active)


def key_ring() -> KeyRing:
    """The configured key ring (settings ``FIELD_ENCRYPTION_KEYS`` / ``_ACTIVE_KEY``)."""
    keys = getattr(settings, "FIELD_ENCRYPTION_KEYS", "")
    active = getattr(settings, "FIELD_ENCRYPTION_ACTIVE_KEY", "")
    serialised = keys if isinstance(keys, str) else json.dumps(keys, sort_keys=True)
    return _ring_from(serialised, active)


def generate_key() -> str:
    """A new base64 AES-256 key for the ring (``manage.py generate_field_key``)."""
    return base64.b64encode(os.urandom(_KEY_BYTES)).decode("ascii")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def is_ciphertext(value: object) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX + ":") and value.count(":") == 3


def key_id_of(ciphertext: str) -> str:
    if not is_ciphertext(ciphertext):
        raise DecryptionError("Not a Numo9 ciphertext.")
    return ciphertext.split(":")[1]


def encrypt(plaintext: str, context: str, ring: KeyRing | None = None) -> Ciphertext:
    ring = ring or key_ring()
    aad = context.encode("utf-8")
    dek = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(_NONCE)
    body = AESGCM(dek).encrypt(nonce, plaintext.encode("utf-8"), aad)
    wrap_nonce = os.urandom(_NONCE)
    wrapped = AESGCM(ring.active_key).encrypt(wrap_nonce, dek, aad)
    return Ciphertext(f"{PREFIX}:{ring.active}:{_b64(wrap_nonce + wrapped)}:{_b64(nonce + body)}")


def _parts(ciphertext: str, ring: KeyRing) -> tuple[str, bytes, bytes, bytes]:
    if not is_ciphertext(ciphertext):
        raise DecryptionError("Not a Numo9 ciphertext.")
    _, key_id, wrapped_part, body_part = ciphertext.split(":")
    if key_id not in ring.keys:
        raise DecryptionError(f"Field-encryption key {key_id!r} is not in the key ring.")
    try:
        wrapped, body = _unb64(wrapped_part), _unb64(body_part)
    except (binascii.Error, ValueError) as error:
        raise DecryptionError("Malformed ciphertext.") from error
    return key_id, ring.keys[key_id], wrapped, body


def _unwrap(kek: bytes, wrapped: bytes, aad: bytes) -> bytes:
    try:
        return AESGCM(kek).decrypt(wrapped[:_NONCE], wrapped[_NONCE:], aad)
    except (InvalidTag, ValueError) as error:
        raise DecryptionError("Data key does not open (wrong key or context).") from error


def decrypt(ciphertext: str, context: str, ring: KeyRing | None = None) -> str:
    ring = ring or key_ring()
    aad = context.encode("utf-8")
    _, kek, wrapped, body = _parts(ciphertext, ring)
    dek = _unwrap(kek, wrapped, aad)
    try:
        return AESGCM(dek).decrypt(body[:_NONCE], body[_NONCE:], aad).decode("utf-8")
    except (InvalidTag, ValueError) as error:
        raise DecryptionError("Value does not decrypt (tampered or wrong context).") from error


def rewrap(ciphertext: str, context: str, ring: KeyRing | None = None) -> Ciphertext:
    """The same value with its data key wrapped by the active key (value ciphertext unchanged)."""
    ring = ring or key_ring()
    aad = context.encode("utf-8")
    _, kek, wrapped, body = _parts(ciphertext, ring)
    dek = _unwrap(kek, wrapped, aad)
    wrap_nonce = os.urandom(_NONCE)
    new_wrapped = AESGCM(ring.active_key).encrypt(wrap_nonce, dek, aad)
    return Ciphertext(f"{PREFIX}:{ring.active}:{_b64(wrap_nonce + new_wrapped)}:{_b64(body)}")
