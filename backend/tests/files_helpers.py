"""Shared helpers for the documents tests (A-06): sample files, upload through the API."""

from __future__ import annotations

import io
import zipfile
from typing import Any

import requests
from PIL import Image
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole

PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n"
    b"0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n164\n%%EOF\n"
)
EXE = (
    b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    + b"\x00" * 44
    + (b"\x80\x00\x00\x00" + b"\x00" * 64 + b"PE\x00\x00L\x01\x03\x00" + b"\x00" * 200)
)
CSV = b"date,description,amount\n2026-10-01,Office supplies,45.20\n"
OFX = b"OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\n\n<OFX><BANKMSGSRSV1></BANKMSGSRSV1></OFX>\n"
#: The EICAR anti-virus test string (harmless; every scanner reports it).
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def png(size: tuple[int, int] = (40, 30)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (255, 209, 0)).save(out, "PNG")
    return out.getvalue()


def jpeg(size: tuple[int, int] = (40, 30)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (17, 17, 17)).save(out, "JPEG")
    return out.getvalue()


def office(kind: str) -> bytes:
    """A minimal Office Open XML package (``xlsx`` or ``docx``)."""
    part = {"xlsx": "xl/workbook.xml", "docx": "word/document.xml"}[kind]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("_rels/.rels", "<Relationships/>")
        package.writestr(part, "<root/>")
    return out.getvalue()


def plain_zip() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as package:
        package.writestr("notes.txt", "hello")
    return out.getvalue()


def owner_of(org: Organisation, email: str = "dana@maple.ca") -> User:
    user = User.objects.create_user(email=email, password="x" * 12, name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=user, role=OrganisationRole.OWNER)
    return user


def api(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def start_upload(client: APIClient, org: Organisation, name: str, size: int) -> Any:
    return client.post(
        f"/api/v1/o/{org.public_id}/files/uploads", {"name": name, "size": size}, format="json"
    )


def send_to_bucket(form: dict[str, Any], name: str, data: bytes) -> int:
    response = requests.post(
        form["url"], data=form["fields"], files={"file": (name, data)}, timeout=30
    )
    return response.status_code


def upload(client: APIClient, org: Organisation, name: str, data: bytes) -> Any:
    """Start, send and finalise an upload; returns the finalize response."""
    started = start_upload(client, org, name, len(data))
    assert started.status_code == 201, started.json()
    assert send_to_bucket(started.json()["upload"], name, data) in (200, 201, 204)
    document_id = started.json()["document"]["id"]
    return client.post(f"/api/v1/o/{org.public_id}/files/{document_id}/finalize")


class FakeClamd:
    """A clamd that speaks INSTREAM on a local port: FOUND for the EICAR string, OK otherwise
    (``mode="error"`` answers an ERROR line, ``mode="down"`` isn't started)."""

    def __init__(self, mode: str = "ok") -> None:
        import socket
        import threading

        self.mode = mode
        self.scanned: list[bytes] = []
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen()
        self.port = self.server.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        import struct

        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                buffer = b""
                while not buffer.startswith(b"zINSTREAM\0"):
                    buffer += conn.recv(4096)
                buffer = buffer[len(b"zINSTREAM\0") :]
                data = b""
                while True:
                    while len(buffer) < 4:
                        buffer += conn.recv(65536)
                    (size,) = struct.unpack(">I", buffer[:4])
                    buffer = buffer[4:]
                    if size == 0:
                        break
                    while len(buffer) < size:
                        buffer += conn.recv(65536)
                    data, buffer = data + buffer[:size], buffer[size:]
                self.scanned.append(data)
                if self.mode == "error":
                    conn.sendall(b"stream: INSTREAM size limit exceeded. ERROR\0")
                elif b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in data:
                    conn.sendall(b"stream: Eicar-Test-Signature FOUND\0")
                else:
                    conn.sendall(b"stream: OK\0")

    def close(self) -> None:
        import contextlib
        import socket

        with contextlib.suppress(OSError):
            self.server.shutdown(socket.SHUT_RDWR)  # wakes the accept() of the thread
        self.server.close()
