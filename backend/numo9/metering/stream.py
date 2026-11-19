"""The metering event stream: Redis Streams in staging/prod, in-process in tests and dev.

Entries are ``{"org": <organisation pk>, "key": <meter>, "qty": <int>, "day": <YYYY-MM-DD>}``
with Redis-style ids ``<ms>-<seq>``. The aggregator reads after its saved offset and trims what it
has summed; there are no consumer groups (one aggregator at a time, under a database lock).
"""

from __future__ import annotations

import itertools
import threading
import time
from typing import Any, Protocol

from django.conf import settings

STREAM = "numo9:metering"

Entry = tuple[str, dict[str, str]]


def _id_key(entry_id: str) -> tuple[int, int]:
    ms, _, seq = entry_id.partition("-")
    return int(ms), int(seq or 0)


class Stream(Protocol):
    def add(self, fields: dict[str, str]) -> str: ...

    def read_after(self, last_id: str, count: int) -> list[Entry]: ...

    def trim_through(self, last_id: str) -> None: ...

    def length(self) -> int: ...


class RedisStream:
    """``XADD`` (approximate cap), ``XRANGE (last_id +``, ``XTRIM MINID``."""

    def __init__(self, url: str, name: str = STREAM, max_len: int = 5_000_000) -> None:
        import redis

        # Short timeouts: metering must never hold a request (S-06 business rule).
        self.client = redis.Redis.from_url(
            url, socket_timeout=0.25, socket_connect_timeout=0.25, decode_responses=True
        )
        self.name = name
        self.max_len = max_len

    def add(self, fields: dict[str, str]) -> str:
        values: Any = fields
        return str(self.client.xadd(self.name, values, maxlen=self.max_len, approximate=True))

    def read_after(self, last_id: str, count: int) -> list[Entry]:
        rows: Any = self.client.xrange(self.name, min=f"({last_id}", max="+", count=count)
        return [(str(entry_id), dict(fields)) for entry_id, fields in rows]

    def trim_through(self, last_id: str) -> None:
        ms, seq = _id_key(last_id)
        self.client.xtrim(self.name, minid=f"{ms}-{seq + 1}")

    def length(self) -> int:
        return int(self.client.xlen(self.name))


class MemoryStream:
    """Process-local stream with the same semantics (tests, dev without Redis)."""

    def __init__(self) -> None:
        self._entries: list[Entry] = []
        self._lock = threading.Lock()
        self._seq = itertools.count()

    def add(self, fields: dict[str, str]) -> str:
        with self._lock:
            entry_id = f"{int(time.time() * 1000)}-{next(self._seq)}"
            self._entries.append((entry_id, dict(fields)))
            return entry_id

    def read_after(self, last_id: str, count: int) -> list[Entry]:
        after = _id_key(last_id)
        with self._lock:
            return [e for e in self._entries if _id_key(e[0]) > after][:count]

    def trim_through(self, last_id: str) -> None:
        through = _id_key(last_id)
        with self._lock:
            self._entries = [e for e in self._entries if _id_key(e[0]) > through]

    def length(self) -> int:
        with self._lock:
            return len(self._entries)


_stream: Stream | None = None
_lock = threading.Lock()


def get_stream() -> Stream:
    """The configured stream: ``METERING_REDIS_URL`` (empty → in-process)."""
    global _stream
    with _lock:
        if _stream is None:
            url = getattr(settings, "METERING_REDIS_URL", "")
            _stream = RedisStream(url) if url else MemoryStream()
        return _stream


def set_stream(stream: Stream | None) -> None:
    """Replace the stream (tests)."""
    global _stream
    with _lock:
        _stream = stream
