"""Test-session setup."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from django.db import transaction

from tools.compile_messages import main as compile_messages


def pytest_configure(config: pytest.Config) -> None:
    # Translations need compiled .mo files (build output, not committed) — A-10-T14.
    compile_messages(["--quiet"])


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Rate-limit counters and lockouts live in the cache (A-02): no test inherits another's."""
    from django.core.cache import cache

    cache.clear()


# ---- background jobs (A-08) --------------------------------------------------------------------


@pytest.fixture
def sent_on_commit() -> Iterator[list[dict[str, Any]]]:
    """Messages sent by start_job (captured instead of reaching the broker)."""
    messages: list[dict[str, Any]] = []

    def capture(self: Any, args: Any = None, kwargs: Any = None, **options: Any) -> None:
        messages.append({"task": self.name, "kwargs": kwargs, **options})

    with mock.patch("celery.app.task.Task.apply_async", capture):
        yield messages


@pytest.fixture
def sent(sent_on_commit: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    """As ``sent_on_commit``, with commit callbacks run at once: the test transaction never
    commits, while in production start_job runs in autocommit or a request that commits."""

    def now(func: Any, using: Any = None, robust: bool = False) -> None:
        func()

    with mock.patch.object(transaction, "on_commit", now):
        yield sent_on_commit


# ---- object storage (A-06): an S3 API (moto server) for the file tests ------------------------


@pytest.fixture(scope="session")
def _s3_server() -> Iterator[str]:
    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


@pytest.fixture
def s3(_s3_server: str, settings: Any) -> Iterator[str]:
    """Empty ``files`` and ``quarantine`` buckets on a local S3 API, wired into the settings."""
    import boto3

    from numo9.files.storage import reset_storages

    settings.NUMO9_FILES_S3_ENDPOINT_URL = _s3_server
    settings.NUMO9_FILES_S3_REGION = "us-east-1"
    settings.NUMO9_FILES_S3_ACCESS_KEY = "test-access"
    settings.NUMO9_FILES_S3_SECRET_KEY = "test-secret"  # noqa: S105 (local fake S3)
    settings.NUMO9_FILES_BUCKET = "numo9-files"
    settings.NUMO9_FILES_QUARANTINE_BUCKET = "numo9-quarantine"
    reset_storages()
    s3 = boto3.client(
        "s3",
        endpoint_url=_s3_server,
        aws_access_key_id="test-access",
        aws_secret_access_key="test-secret",  # noqa: S106 (local fake S3)
        region_name="us-east-1",
    )
    for bucket in ("numo9-files", "numo9-quarantine"):
        with contextlib.suppress(s3.exceptions.BucketAlreadyOwnedByYou):
            s3.create_bucket(Bucket=bucket)
        for item in s3.list_objects_v2(Bucket=bucket).get("Contents", []):
            s3.delete_object(Bucket=bucket, Key=item["Key"])
    yield _s3_server
    reset_storages()


@pytest.fixture
def clamd(settings: Any) -> Iterator[Any]:
    """A local fake clamd (INSTREAM): EICAR → FOUND, anything else → OK."""
    from tests.files_helpers import FakeClamd

    fake = FakeClamd()
    settings.NUMO9_CLAMD_HOST = "127.0.0.1"
    settings.NUMO9_CLAMD_PORT = fake.port
    settings.NUMO9_CLAMD_TIMEOUT = 5
    yield fake
    fake.close()
