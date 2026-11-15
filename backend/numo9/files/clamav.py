"""ClamAV daemon client (A-06-T04): the ``INSTREAM`` command over TCP.

    scan(chunks)  →  ScanResult(clean=True)  |  ScanResult(clean=False, signature="Eicar-…")

Protocol (clamd(8)): send ``zINSTREAM\\0``, then the file as chunks — each a 4-byte big-endian
length followed by the bytes — and a zero-length chunk to end; clamd answers one line ending in
``\\0``: ``stream: OK``, ``stream: <signature> FOUND`` or ``… ERROR``. The daemon is the ``clamav``
service of the stack (``NUMO9_CLAMD_HOST`` / ``NUMO9_CLAMD_PORT``). Any connection problem or
``ERROR`` answer raises ``ScannerUnavailable``: the scan job retries it later (a file is never
treated as clean because the scanner was down).
"""

from __future__ import annotations

import socket
import struct
from collections.abc import Iterable
from dataclasses import dataclass

from django.conf import settings

#: clamd's default StreamMaxLength is 25 MB too; chunks stay well under it.
CHUNK = 64 * 1024


class ScannerUnavailable(RuntimeError):
    """clamd can't be reached or couldn't scan the stream (retry later)."""


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    signature: str = ""


def scan(chunks: Iterable[bytes]) -> ScanResult:
    try:
        with socket.create_connection(
            (settings.NUMO9_CLAMD_HOST, settings.NUMO9_CLAMD_PORT),
            timeout=settings.NUMO9_CLAMD_TIMEOUT,
        ) as conn:
            conn.sendall(b"zINSTREAM\0")
            for chunk in chunks:
                for start in range(0, len(chunk), CHUNK):
                    part = chunk[start : start + CHUNK]
                    conn.sendall(struct.pack(">I", len(part)) + part)
            conn.sendall(struct.pack(">I", 0))
            answer = b""
            while not answer.endswith(b"\0"):
                data = conn.recv(4096)
                if not data:
                    break
                answer += data
    except OSError as exc:
        raise ScannerUnavailable(f"clamd unreachable: {exc}") from exc
    return parse(answer.rstrip(b"\0").decode("utf-8", "replace").strip())


def parse(line: str) -> ScanResult:
    """``stream: OK`` / ``stream: Win.Test.EICAR_HDB-1 FOUND`` / ``… ERROR``."""
    _, _, verdict = line.partition(": ")
    if verdict == "OK":
        return ScanResult(clean=True)
    if verdict.endswith(" FOUND"):
        return ScanResult(clean=False, signature=verdict[: -len(" FOUND")].strip())
    raise ScannerUnavailable(f"clamd answered {line!r}")
